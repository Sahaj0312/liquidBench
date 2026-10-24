"""Claude authors candidate training tasks; the container grader keeps or rejects each.

No held-out or development task content is sent: themes come from a curated list,
and leak/similarity filters run locally on what comes back. Spend is capped by
the shared ledger.
uv run --with anthropic python scripts/generate_training_tasks.py --calls 4 --cap 3
"""

import argparse
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import random

from liquidbench.claude_provider import FALLBACK_BETA, Ledger
from liquidbench.heldout import verify_frozen
from liquidbench.sandbox import Sandbox, image_id
from liquidbench.training_tasks import SPEC_SCHEMA, Rejected, build, known_families

THEMES = {
    "liquid-syntax": [
        "newsletter consent",
        "loyalty tier",
        "preorder notice",
        "subscription cadence",
        "age gate",
        "delivery window",
        "warranty status",
        "bundle eligibility",
        "membership renewal",
        "low-carbon shipping flag",
        "restock alert",
        "pickup availability",
        "tax-inclusive label",
        "event ticket status",
        "trial period banner",
    ],
    "rendering": [
        "product tags list",
        "variant swatch list",
        "order summary rows",
        "unit price label",
        "store locator entry",
        "blog post meta",
        "author byline",
        "recipe ingredient list",
        "comparison table rows",
        "shipping progress bar label",
        "wishlist count",
        "recently viewed list",
        "spec sheet",
        "address block",
        "cart line item",
    ],
    "section-schema": [
        "image with text",
        "newsletter section",
        "video section",
        "rich text",
        "contact form",
        "map section",
        "logo list",
        "multicolumn features",
        "announcement bar",
        "blog posts section",
        "featured product",
        "custom liquid section",
        "promo popup",
        "header menu",
        "brand story",
    ],
    "theme-references": [
        "icon sprite",
        "search form labels",
        "account page labels",
        "newsletter labels",
        "product media script",
        "font stylesheet",
        "share buttons",
        "language selector",
        "quantity input labels",
        "predictive search script",
        "social icons snippet",
        "shipping policy labels",
        "password page labels",
    ],
    "theme-modification": [
        "image banner",
        "rich text block",
        "multicolumn section",
        "contact section",
        "newsletter block",
        "video section",
        "collage section",
        "team member list",
        "store info section",
        "promo strip",
        "featured blog section",
        "brand list",
    ],
}

INSTRUCTIONS = """You write training tasks for a coding agent that edits Shopify Liquid theme
files with these tools only: read_file, write_file, render (strict core Ruby Liquid 5.8 with
strict_variables and strict_filters, only supplied variables, NO Shopify objects, filters or
tags), analyze (static AST/schema), check (Shopify Theme Check), finish.

Return {count} tasks as JSON matching the schema. Each task must be original, realistic,
self-contained and objectively gradable. Requirements:

- family: a new kebab-case id that names the theme (3-40 chars).
- path: sections/<family>.liquid for section-schema and theme-modification tasks,
  otherwise snippets/<family>.liquid.
- prompt: a precise specification that a careful developer could implement exactly.
  State every input with its full nesting (which inputs are top-level and which are under
  section.settings), its type and whether it can be null. State exact output text,
  elements, attributes, ordering and edge cases. Do not reveal the solution code.
- starter: the realistic broken or incomplete current file. reference: the correct file.
- wrong_solutions: at least 3 plausible but incorrect full files (edge-case bugs, not
  syntax errors), each of which the cases or contract must catch.
- Write the expected outputs from the specification, independently of your reference.

By category:
- liquid-syntax / rendering (snippets) and theme-modification (sections): rendered tasks.
  tags lists every HTML element the output may contain (paired tags only; never void
  elements such as img, br, input, meta). cases: 8-14 entries; variables_json is a JSON
  object supplying every variable the template reads; expected_html is exactly the HTML
  the specification requires (empty string when nothing is output). Include boundary,
  null, empty and escaping cases (text with < > & " characters). Use only core Liquid
  filters (escape, strip, default, split, join, size, plus, minus, times, divided_by,
  modulo, upcase, downcase, slice, append, prepend, replace, first, last, where, map...).
  theme-modification tasks: the starter is an existing working section ending in one
  {{% schema %}}...{{% endschema %}} block that the reference keeps byte-for-byte; the
  request adds or changes behavior.
- section-schema: starter and reference are identical markup followed by one top-level
  schema block; only the schema JSON differs. expected_schema_json is the exact required
  schema. The prompt states every required field and value. cases, tags: empty.
- theme-references: snippet whose literal operands (asset filenames for asset_url /
  stylesheet_tag, translation keys for t, snippet names for render) are wrong in the
  starter. extra_files supplies the real assets/, locales/*.json (en.default.json and one
  more locale, nested keys) and snippets/ the reference must point to. The starter must
  produce Theme Check errors (missing asset, translation key or snippet); the reference
  none. cases, tags, expected_schema_json: empty.
- Leave unused fields empty ("" or []).

This batch: category {category}, difficulty {difficulty}. Themes, one task each: {themes}.
Difficulty guide: easy = one condition or mapping; medium = several interacting rules or
loops; hard = subtle precedence, arithmetic, state across loop iterations, or several
coordinated edits."""


def author(client, ledger, model, category, difficulty, themes, effort):
    ledger.require(0.60)
    with client.beta.messages.stream(
        model=model,
        max_tokens=64000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": SPEC_SCHEMA}},
        messages=[
            {
                "role": "user",
                "content": INSTRUCTIONS.format(
                    count=len(themes),
                    category=category,
                    difficulty=difficulty,
                    themes="; ".join(themes),
                ),
            }
        ],
    ) as stream:
        response = stream.get_final_message()
    usd = ledger.record("task-authoring", model, response.usage.model_dump(exclude_none=True))
    if response.stop_reason != "end_turn":
        # A truncated structured response cannot be parsed; it is paid for and recorded.
        print(f"authoring call unusable: stop_reason={response.stop_reason}", flush=True)
        return [], usd
    text = "".join(b.text for b in response.content if b.type == "text")
    return json.loads(text)["tasks"], usd


def main():
    import anthropic

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", type=int, required=True)
    parser.add_argument("--per-call", type=int, default=3)
    parser.add_argument("--cap", type=float, required=True, help="total USD cap for the ledger")
    parser.add_argument("--model", default="claude-opus-5-5")
    parser.add_argument("--effort", default="medium")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--ledger", default="runs/training/ledger.jsonl")
    args = parser.parse_args()
    ledger = Ledger(args.ledger, args.cap)
    client = anthropic.Anthropic()
    image = image_id("liquidbench-runtime:0.1")
    heldout = verify_frozen()
    rng = random.Random(args.seed)
    plan = list(itertools.product(sorted(THEMES), ["easy", "medium", "hard"]))
    rng.shuffle(plan)
    log = Path("runs/training/authoring.jsonl")
    log.parent.mkdir(parents=True, exist_ok=True)
    out = Path("tasks/train")
    stamp = datetime.now(timezone.utc).date().isoformat()
    for category, difficulty in itertools.islice(itertools.cycle(plan), args.calls):
        themes = rng.sample(THEMES[category], args.per_call)
        specs, usd = author(client, ledger, args.model, category, difficulty, themes, args.effort)
        for spec in specs:
            provenance = (
                f"Claude-authored training task ({args.model}, {stamp}); kept only after "
                "container verification. Not development or held-out data."
            )
            try:
                root = build(
                    spec,
                    out,
                    sandbox_factory=Sandbox,
                    image=image,
                    heldout_tasks=heldout,
                    known_families=known_families(),
                    provenance=provenance,
                )
                verdict, reason = "kept", str(root)
            except Rejected as exc:
                verdict, reason = "rejected", str(exc)
            with log.open("a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "family": spec.get("family"),
                            "category": category,
                            "difficulty": difficulty,
                            "verdict": verdict,
                            "reason": reason,
                            "model": args.model,
                            "spec": spec,
                        }
                    )
                    + "\n"
                )
            print(f"{verdict:8} {spec.get('family')}: {reason}", flush=True)
        print(f"call ${usd:.4f}; ledger ${ledger.spent():.4f} of ${ledger.cap:.2f}", flush=True)


if __name__ == "__main__":
    main()
