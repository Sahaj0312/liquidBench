"""Build and verify Claude-authored training tasks; the container grader decides.

A spec is kept only when its reference passes (so the reference's real output
agrees with the author's independently predicted expectations), its starter and
every wrong solution fail, and nothing in it resembles a held-out task.
"""

import json
import re
import shutil
from pathlib import Path

from .evaluators.contracts import dom_value
from .evaluators.dom import fragment
from .grading import grade, validation_candidates
from .heldout import assert_not_heldout
from .task import Task, discover_tasks

CATEGORIES = {
    "liquid-syntax": "render",
    "rendering": "render",
    "theme-modification": "render",
    "section-schema": "schema",
    "theme-references": "reference",
}
DIFFICULTIES = {"easy", "medium", "hard"}
RENDER_RULES = (
    " Output only the specified elements/attributes; escape dynamic text and attributes."
    " Inter-element whitespace, comments and quote style may vary; leaf text is exact."
)
RUNTIME = (
    "Core Ruby Liquid with supplied hashes only; or static schema/reference contracts. "
    "No Shopify service emulation."
)
ROOT = Path(__file__).resolve().parents[2]

SPEC_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["tasks"],
    "properties": {
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "family",
                    "category",
                    "difficulty",
                    "path",
                    "prompt",
                    "starter",
                    "reference",
                    "extra_files",
                    "tags",
                    "cases",
                    "expected_schema_json",
                    "wrong_solutions",
                ],
                "properties": {
                    "family": {"type": "string"},
                    "category": {"type": "string", "enum": sorted(CATEGORIES)},
                    "difficulty": {"type": "string", "enum": sorted(DIFFICULTIES)},
                    "path": {"type": "string"},
                    "prompt": {"type": "string"},
                    "starter": {"type": "string"},
                    "reference": {"type": "string"},
                    "extra_files": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["path", "content"],
                            "properties": {
                                "path": {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                    },
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "cases": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["variables_json", "expected_html"],
                            "properties": {
                                "variables_json": {"type": "string"},
                                "expected_html": {"type": "string"},
                            },
                        },
                    },
                    "expected_schema_json": {"type": "string"},
                    "wrong_solutions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["name", "content"],
                            "properties": {
                                "name": {"type": "string"},
                                "content": {"type": "string"},
                            },
                        },
                    },
                },
            },
        }
    },
}


class Rejected(ValueError):
    pass


def words(text):
    return set(re.findall(r"[a-z0-9_]+", text.lower()))


def similar_to_heldout(spec, heldout_tasks, threshold=0.5):
    mine = words(spec["prompt"])
    for task in heldout_tasks:
        theirs = words(task.manifest["prompt"])
        if len(mine & theirs) / max(1, len(mine | theirs)) >= threshold:
            return task.manifest["id"]
    return None


def schema_block(sandbox, path):
    parsed = sandbox.call("analyze", {"path": path})
    schemas = parsed.get("schemas", []) if parsed.get("ok") else []
    return schemas[0]["block"] if len(schemas) == 1 and schemas[0]["top_level"] else None


def build(spec, out_root, *, sandbox_factory, image, heldout_tasks, known_families, provenance):
    """Write a candidate task directory and return it, or raise Rejected (nothing kept)."""
    family = spec["family"]
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,40}", family) or family in known_families:
        raise Rejected("invalid or duplicate family")
    kind = CATEGORIES[spec["category"]]
    path = spec["path"]
    folder = (
        "sections/" if kind == "schema" or spec["category"] == "theme-modification" else "snippets/"
    )
    if path != f"{folder}{family}.liquid":
        raise Rejected(f"path must be {folder}{family}.liquid")
    try:
        assert_not_heldout(json.dumps(spec))
    except ValueError as exc:
        raise Rejected(str(exc)) from exc
    near = similar_to_heldout(spec, heldout_tasks)
    if near:
        raise Rejected(f"too similar to a held-out task ({near})")
    extra = {f["path"]: f["content"] for f in spec["extra_files"]}
    if path in extra or any(not p.startswith(("locales/", "assets/", "snippets/")) for p in extra):
        raise Rejected("extra files must be locales/, assets/ or other snippets/")
    if spec["starter"] == spec["reference"] or len(spec["wrong_solutions"]) < 2:
        raise Rejected("needs a differing starter and at least two wrong solutions")
    prompt = spec["prompt"].strip()
    cases = []
    with sandbox_factory(image, {**extra, path: spec["reference"]}) as sb:
        if kind == "render":
            tags = sorted(set(spec["tags"]))
            if not tags or len(spec["cases"]) < 6:
                raise Rejected("render tasks need tags and at least six cases")
            block = schema_block(sb, path)
            contract = {"id": "contract", "path": path, "tags": tags}
            if block is not None:
                contract["schema_block"] = block
            cases.append(contract)
            for i, case in enumerate(spec["cases"]):
                try:
                    variables = json.loads(case["variables_json"])
                except ValueError as exc:
                    raise Rejected("case variables are not JSON") from exc
                expected = fragment(case["expected_html"], tags)
                if not isinstance(variables, dict) or expected is None:
                    raise Rejected("case needs object variables and parseable expected HTML")
                cases.append(
                    {"id": f"case-{i:02d}", "variables": variables, "expected": dom_value(expected)}
                )
            prompt += RENDER_RULES + (
                " Preserve the entire schema block byte-for-byte." if block is not None else ""
            )
            evaluator = "render-contract-v1"
        elif kind == "schema":
            parsed = sb.call("analyze", {"path": path})
            schemas = parsed.get("schemas", []) if parsed.get("ok") else []
            if len(schemas) != 1 or not schemas[0]["top_level"]:
                raise Rejected("schema reference needs exactly one top-level schema")
            try:
                expected = json.loads(spec["expected_schema_json"])
            except ValueError as exc:
                raise Rejected("expected schema is not JSON") from exc
            cases.append(
                {
                    "id": "schema-contract",
                    "path": path,
                    "body": parsed["body_source"],
                    "expected": expected,
                }
            )
            evaluator = "schema-contract-v1"
        else:
            parsed = sb.call("analyze", {"path": path})
            if not parsed.get("ok"):
                raise Rejected("reference does not parse")
            offenses = sb.call("check").get("offenses", [])
            if any(o["severity"] == 0 for o in offenses):
                raise Rejected("reference has static errors")
            cases.append({"id": "reference-contract", "path": path, "expected_ast": parsed["ast"]})
            evaluator = "reference-contract-v1"
    if kind == "reference":
        with sandbox_factory(image, {**extra, path: spec["starter"]}) as sb:
            if not any(o["severity"] == 0 for o in sb.call("check").get("offenses", [])):
                raise Rejected("starter must have a visible static reference error")
    root = Path(out_root) / family
    if root.exists():
        raise Rejected("task directory exists")
    try:
        write_task(root, spec, prompt, path, extra, cases, evaluator, provenance)
        task = Task.load(root)
        for name, (files, expected) in validation_candidates(task).items():
            if grade(task, files, image)["passed"] != expected:
                raise Rejected(f"grader verdict wrong for {name}")
    except Rejected:
        shutil.rmtree(root, ignore_errors=True)
        raise
    except (ValueError, KeyError, TypeError) as exc:
        shutil.rmtree(root, ignore_errors=True)
        raise Rejected(f"invalid task: {exc}") from exc
    return root


def write_task(root, spec, prompt, path, extra, cases, evaluator, provenance):
    def dump(p, value):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")

    def text(p, value):
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(value)

    dump(
        root / "task.json",
        {
            "id": spec["family"],
            "version": 1,
            "split": "train",
            "category": spec["category"],
            "difficulty": spec["difficulty"],
            "family": spec["family"],
            "provenance": provenance,
            "runtime_subset": RUNTIME,
            "editable_files": [path],
            "prompt": prompt + f" Change only {path}. Do not suppress checks or hardcode case "
            "values. All input keys are present.",
            "evaluator": evaluator,
        },
    )
    for p, s in {path: spec["starter"], **extra}.items():
        text(root / "initial" / p, s)
    text(root / "evaluator/reference" / path, spec["reference"])
    dump(root / "evaluator/cases.json", cases)
    wrong = [
        {
            "name": f"wrong-{i}-{re.sub(r'[^a-z0-9-]', '-', w['name'].lower())[:30]}",
            "expected_pass": False,
            "changes": {path: w["content"]},
        }
        for i, w in enumerate(spec["wrong_solutions"])
    ]
    wrong += [
        {
            "name": "suppressed",
            "expected_pass": False,
            "changes": {path: "{% # theme-check-disable %}\n" + spec["reference"]},
        },
        {"name": "deleted-target", "expected_pass": False, "changes": {path: None}},
    ]
    dump(root / "evaluator/validation.json", wrong)


def known_families():
    return {
        t.manifest["family"]
        for split in ("dev", "heldout")
        for t in discover_tasks(ROOT / "tasks" / split)
    } | {p.name for p in (ROOT / "tasks/train").glob("*") if p.is_dir()}
