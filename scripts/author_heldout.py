"""Author the frozen held-out benchmark (tasks/heldout); run once, never overwrite.

Held-out tasks evaluate final models only. Their families, prompts, cases and
solutions must never be shown to a training-data generator or used to tune
prompts. Expected outputs come from independent Python oracles, not from
rendering the reference solution; validation then proves the reference passes
and every plausible-wrong or adversarial candidate fails.
uv run python scripts/author_heldout.py
"""

import copy
import html
import itertools
import json
from pathlib import Path

from liquidbench.evaluators.contracts import dom_value
from liquidbench.evaluators.dom import element as node
from liquidbench.sandbox import Sandbox, image_id

ROOT = Path("tasks/heldout")
IMAGE = image_id("liquidbench-runtime:0.1")
PROVENANCE = (
    "Original synthetic LiquidBench held-out evaluation fixture, authored 2026-10-24 before "
    "any training data. Final-model evaluation only; never shown to training-data generation."
)
RUNTIME = (
    "Core Ruby Liquid with supplied hashes only; or static schema/reference contracts. "
    "No Shopify service emulation."
)
RENDER_RULES = (
    " Output only the specified elements/attributes; escape dynamic text and attributes."
    " Inter-element whitespace, comments and quote style may vary; leaf text is exact."
)


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def markup(nodes):
    return "".join(
        "<"
        + n["tag"]
        + "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in n["attrs"])
        + ">"
        + html.escape(n["text"])
        + markup(n["children"])
        + "</"
        + n["tag"]
        + ">"
        for n in nodes
    )


def add(
    name,
    category,
    difficulty,
    path,
    prompt,
    starter,
    reference,
    cases,
    wrong,
    *,
    initial=None,
    evaluator="render-contract-v1",
    alt=None,
):
    root = ROOT / name
    assert not root.exists(), name
    files = {path: starter, **(initial or {})}
    dump(
        root / "task.json",
        {
            "id": name,
            "version": 1,
            "split": "heldout",
            "category": category,
            "difficulty": difficulty,
            "family": name,
            "provenance": PROVENANCE,
            "runtime_subset": RUNTIME,
            "editable_files": [path],
            "prompt": prompt + f" Change only {path}. Do not suppress checks or hardcode case "
            "values. All input keys are present.",
            "evaluator": evaluator,
        },
    )
    for p, s in files.items():
        text(root / "initial" / p, s)
    text(root / "evaluator/reference" / path, reference)
    dump(root / "evaluator/cases.json", cases)
    candidates = [
        {
            "name": "alternative-valid",
            "expected_pass": True,
            "changes": {
                path: alt
                if alt is not None
                else "{% comment %}Equivalent layout{% endcomment %}\n"
                + reference.replace("><", ">\n<")
            },
        }
    ]
    candidates += [{"name": n, "expected_pass": False, "changes": {path: s}} for n, s in wrong]
    candidates += [
        {
            "name": "suppressed",
            "expected_pass": False,
            "changes": {path: "{% # theme-check-disable %}\n" + reference},
        },
        {
            "name": "extra-file",
            "expected_pass": False,
            "changes": {"snippets/unauthorized.liquid": "bypass"},
        },
        {"name": "deleted-target", "expected_pass": False, "changes": {path: None}},
    ]
    dump(root / "evaluator/validation.json", candidates)
    print(name, len(candidates) + 2, "candidates")


def render_task(
    name, cat, diff, prompt, ref, variables, oracle, wrong, *, starter, tags, schema=None
):
    path = ("sections/" if schema else "snippets/") + name + ".liquid"
    suffix = "\n" + schema if schema else ""
    contract = {"id": "contract", "path": path, "tags": tags}
    if schema:
        contract["schema_block"] = schema
    cases = [contract] + [
        {"id": f"case-{i:02d}", "variables": v, "expected": dom_value(oracle(v))}
        for i, v in enumerate(variables)
    ]
    first = next(markup(oracle(v)) for v in variables if oracle(v))
    wrong = [(n, s + suffix) for n, s in list(wrong) + [("hardcoded-first-case", first)]]
    if schema:
        wrong.append(("changed-schema", ref + suffix.replace('"Panel"', '"Other"', 1)))
    add(
        name,
        cat,
        diff,
        path,
        prompt
        + RENDER_RULES
        + (" Preserve the entire schema block byte-for-byte." if schema else ""),
        starter + suffix,
        ref + suffix,
        cases,
        wrong,
        alt=ref.replace("><", ">\n<") + suffix,
    )


def schema_task(name, diff, heading, schema, description, mutations):
    path = "sections/" + name + ".liquid"
    body = f'<section class="{name}"><h2>{heading}</h2></section>\n'

    def wrap(s):
        return body + "{% schema %}\n" + json.dumps(s, indent=2) + "\n{% endschema %}\n"

    ref = wrap(schema)
    initial = copy.deepcopy(schema)
    mutations[0][1](initial)
    wrong = []
    for label, mutate in mutations:
        x = copy.deepcopy(schema)
        mutate(x)
        wrong.append((label, wrap(x)))
    wrong += [
        ("duplicate-key", ref.replace('"name":', '"name":"spoof","name":', 1)),
        ("dead-schema", "{% comment %}" + ref + "{% endcomment %}"),
        ("changed-markup", ref.replace(f"<h2>{heading}</h2>", "<h2>Changed</h2>")),
    ]
    cases = [{"id": "schema-contract", "path": path, "body": body + "\n", "expected": schema}]
    add(
        name,
        "section-schema",
        diff,
        path,
        f"Repair only the JSON schema in {path}. Keep every byte outside its one top-level "
        "schema block unchanged. Strict JSON only. Exactly the following fields, array order "
        "and values are required; object key order/JSON whitespace may vary. " + description,
        wrap(initial),
        ref,
        cases,
        wrong,
        evaluator="schema-contract-v1",
        alt=body + "{% schema %}\n" + json.dumps(schema, sort_keys=True) + "\n{% endschema %}\n",
    )


def refs(name, diff, ref, starter, files, description, wrong):
    path = "snippets/" + name + ".liquid"
    with Sandbox(IMAGE, {**files, path: ref}) as sb:
        ast = sb.call("analyze", {"path": path})
        assert ast["ok"], ast
    cases = [{"id": "reference-contract", "path": path, "expected_ast": ast["ast"]}]
    wrong = list(wrong) + [
        ("dead-code", "{% if false %}" + ref + "{% endif %}"),
        ("commented", "{% comment %}" + ref + "{% endcomment %}"),
        ("extra-markup", ref + "<p>extra</p>"),
    ]
    add(
        name,
        "theme-references",
        diff,
        path,
        f"Repair the literal references in {path}. Preserve all live markup, filters, tags "
        "and output positions. Only literal operands may change; quote style and "
        "inter-element whitespace may vary. " + description + " These are static reference "
        "checks; do not use the core renderer for Shopify filters or tags.",
        starter,
        ref,
        cases,
        wrong,
        initial=files,
        evaluator="reference-contract-v1",
        alt=ref.replace("'", '"').replace(" | t ", " | translate "),
    )


def section_schema(name, extra):
    return (
        "{% schema %}\n"
        + json.dumps(
            {
                "name": "Panel",
                "settings": [
                    {"type": "text", "id": "heading", "label": "Heading", "default": name},
                    *extra,
                ],
                "presets": [{"name": "Panel"}],
            },
            indent=2,
        )
        + "\n{% endschema %}"
    )


def trim(value):
    return (value or "").strip(" \t\n\r\f\v")


# ---------------------------------------------------------------- Liquid syntax (5)

ref = (
    '{% if product.inventory > 5 %}<p class="stock">In stock</p>{% elsif product.inventory > 0 %}'
    '<p class="stock">Only {{ product.inventory }} left</p>{% elsif product.backorder %}'
    '<p class="stock">Backorder</p>{% else %}<p class="stock">Sold out</p>{% endif %}'
)
render_task(
    "stock-badge",
    "liquid-syntax",
    "easy",
    "Repair snippets/stock-badge.liquid. product.inventory is a nonnegative integer and "
    "product.backorder a boolean. Output one p class=stock: In stock when inventory is more "
    "than 5; Only N left when inventory is 1 to 5, where N is the inventory; Backorder when "
    "inventory is 0 and backorder is true; otherwise Sold out.",
    ref,
    [
        {"product": {"inventory": i, "backorder": b}}
        for i, b in itertools.product([0, 1, 4, 5, 6, 30], [False, True])
    ],
    lambda v: [
        node(
            "p",
            (
                lambda i, b: "In stock"
                if i > 5
                else f"Only {i} left"
                if i > 0
                else "Backorder"
                if b
                else "Sold out"
            )(**{"i": v["product"]["inventory"], "b": v["product"]["backorder"]}),
            {"class": "stock"},
        )
    ],
    [
        ("boundary", ref.replace("inventory > 5", "inventory >= 5")),
        ("ignored-backorder", ref.replace("elsif product.backorder", "elsif false")),
        (
            "backorder-first",
            '{% if product.backorder %}<p class="stock">Backorder</p>{% els' + ref[3:],
        ),
    ],
    starter=ref.replace("inventory > 5", "inventory >= 5").replace(
        '{% elsif product.backorder %}<p class="stock">Backorder</p>', ""
    ),
    tags=["p"],
)

ref = (
    "{% if product.compare_at_price %}{% if product.compare_at_price > product.price %}"
    "{% assign saved = product.compare_at_price | minus: product.price | times: 100 | "
    'divided_by: product.compare_at_price %}<span class="sale">Save {{ saved }}%</span>'
    "{% endif %}{% endif %}"
)
pairs = [
    (1000, None),
    (1000, 1000),
    (1000, 900),
    (750, 1000),
    (999, 1000),
    (1, 3),
    (0, 500),
    (2500, 3999),
    (333, 1000),
    (10, 11),
]
render_task(
    "discount-label",
    "liquid-syntax",
    "medium",
    "Repair snippets/discount-label.liquid. product.price is a nonnegative integer in cents; "
    "product.compare_at_price is null or a positive integer in cents. Only when "
    "compare_at_price is greater than price, output one span class=sale with text Save P% "
    "where P is floor((compare_at_price - price) * 100 / compare_at_price) as a base-10 "
    "integer. Otherwise output nothing.",
    ref,
    [{"product": {"price": p, "compare_at_price": c}} for p, c in pairs],
    lambda v: (
        lambda p, c: [node("span", f"Save {(c - p) * 100 // c}%", {"class": "sale"})]
        if c is not None and c > p
        else []
    )(v["product"]["price"], v["product"]["compare_at_price"]),
    [
        (
            "price-denominator",
            ref.replace("divided_by: product.compare_at_price", "divided_by: product.price"),
        ),
        (
            "shows-equal",
            ref.replace("compare_at_price > product.price", "compare_at_price >= product.price"),
        ),
        (
            "rounded",
            ref.replace(
                "divided_by: product.compare_at_price",
                "divided_by: product.compare_at_price | plus: 0.5 | floor",
            ).replace("times: 100 |", "times: 100.0 |"),
        ),
    ],
    starter=ref.replace(
        "times: 100 | divided_by: product.compare_at_price",
        "divided_by: product.compare_at_price | times: 100",
    ),
    tags=["span"],
)

ref = (
    '{% assign included = false %}{% if order.country == "CA" and order.subtotal >= 5000 %}'
    "{% assign included = true %}{% endif %}{% if customer.member and order.subtotal >= 2500 %}"
    '{% assign included = true %}{% endif %}{% if included %}<p class="gift-wrap">Gift wrap '
    'included</p>{% elsif order.country == "CA" %}<p class="gift-wrap">Gift wrap $5</p>'
    '{% else %}<p class="gift-wrap">Gift wrap unavailable</p>{% endif %}'
)
precedence = (
    '{% if order.country == "CA" and order.subtotal >= 5000 or customer.member and '
    'order.subtotal >= 2500 %}<p class="gift-wrap">Gift wrap included</p>{% elsif '
    'order.country == "CA" %}<p class="gift-wrap">Gift wrap $5</p>{% else %}<p '
    'class="gift-wrap">Gift wrap unavailable</p>{% endif %}'
)


def gift(v):
    c, s, m = v["order"]["country"], v["order"]["subtotal"], v["customer"]["member"]
    label = (
        "Gift wrap included"
        if (c == "CA" and s >= 5000) or (m and s >= 2500)
        else "Gift wrap $5"
        if c == "CA"
        else "Gift wrap unavailable"
    )
    return [node("p", label, {"class": "gift-wrap"})]


render_task(
    "gift-wrap-eligibility",
    "liquid-syntax",
    "hard",
    "Repair snippets/gift-wrap-eligibility.liquid. order.country is an uppercase ISO country "
    "code string, order.subtotal a nonnegative integer in cents, customer.member a boolean. "
    "Output one p class=gift-wrap: Gift wrap included exactly when (country is CA and "
    "subtotal is at least 5000) or (member is true and subtotal is at least 2500); otherwise "
    "Gift wrap $5 when country is CA; otherwise Gift wrap unavailable. Country comparison is "
    "exact and case-sensitive.",
    ref,
    [
        {"order": {"country": c, "subtotal": s}, "customer": {"member": m}}
        for c, s, m in [
            ("CA", 0, False),
            ("CA", 4999, False),
            ("CA", 5000, False),
            ("CA", 3000, True),
            ("US", 3000, True),
            ("US", 2499, True),
            ("US", 2500, True),
            ("US", 9000, False),
            ("ca", 9000, False),
            ("GB", 2500, False),
            ("CA", 2499, True),
            ("FR", 5000, True),
        ]
    ],
    gift,
    [
        ("precedence", precedence),
        ("boundary", ref.replace("subtotal >= 5000", "subtotal > 5000")),
        (
            "member-any-subtotal",
            ref.replace("customer.member and order.subtotal >= 2500", "customer.member"),
        ),
    ],
    starter=precedence,
    tags=["p"],
)

sizes = {"XS": "Extra small", "S": "Small", "M": "Medium", "L": "Large", "XL": "Extra large"}
ref = (
    '<span class="size">{% case variant.size %}'
    + "".join(f'{{% when "{k}" %}}{v}' for k, v in sizes.items())
    + "{% else %}One size{% endcase %}</span>"
)
render_task(
    "size-label",
    "liquid-syntax",
    "easy",
    "Repair snippets/size-label.liquid. variant.size is a string. Output one span class=size "
    "with text Extra small for XS, Small for S, Medium for M, Large for L, Extra large for "
    "XL, and One size for any other value. Matching is exact and case-sensitive.",
    ref,
    [{"variant": {"size": s}} for s in ["XS", "S", "M", "L", "XL", "", "xl", "s", "M ", "XXL"]],
    lambda v: [node("span", sizes.get(v["variant"]["size"], "One size"), {"class": "size"})],
    [
        ("missing-xl", ref.replace('{% when "XL" %}Extra large', "")),
        ("case-insensitive", ref.replace("case variant.size", "case variant.size | upcase")),
        ("wrong-fallback", ref.replace("One size", "Unknown")),
    ],
    starter=ref.replace('{% when "XS" %}Extra small', "")
    .replace('{% when "XL" %}Extra large', "")
    .replace("One size", "Unknown"),
    tags=["span"],
)

ref = (
    "{% assign open = false %}{% if now.weekday >= 1 and now.weekday <= 5 %}{% if now.hour >= 9 "
    "and now.hour < 17 %}{% assign open = true %}{% endif %}{% elsif now.weekday == 6 %}"
    "{% if now.hour >= 10 and now.hour < 14 %}{% assign open = true %}{% endif %}{% endif %}"
    '<p class="hours">{% if open %}Open now{% else %}Closed{% endif %}</p>'
)


def hours(v):
    d, h = v["now"]["weekday"], v["now"]["hour"]
    is_open = (1 <= d <= 5 and 9 <= h < 17) or (d == 6 and 10 <= h < 14)
    return [node("p", "Open now" if is_open else "Closed", {"class": "hours"})]


render_task(
    "store-hours",
    "liquid-syntax",
    "medium",
    "Repair snippets/store-hours.liquid. now.weekday is an integer 0 to 6 where 0 is Sunday "
    "and 6 is Saturday; now.hour is an integer 0 to 23. The store is open Monday to Friday "
    "from hour 9 up to but not including hour 17, Saturday from hour 10 up to but not "
    "including hour 14, and closed Sunday. Output one p class=hours with Open now or Closed.",
    ref,
    [
        {"now": {"weekday": d, "hour": h}}
        for d, h in [
            (1, 8),
            (1, 9),
            (3, 16),
            (5, 17),
            (6, 9),
            (6, 10),
            (6, 13),
            (6, 14),
            (0, 12),
            (2, 0),
            (4, 23),
            (5, 9),
            (0, 9),
        ]
    ],
    hours,
    [
        ("inclusive-close", ref.replace("now.hour < 17", "now.hour <= 17")),
        ("saturday-as-weekday", ref.replace("now.weekday <= 5", "now.weekday <= 6")),
        ("sunday-open", ref.replace("now.weekday >= 1", "now.weekday >= 0")),
    ],
    starter=ref.replace("now.hour < 17", "now.hour <= 17").replace(
        "now.weekday <= 5", "now.weekday <= 6"
    ),
    tags=["p"],
)

# ---------------------------------------------------------------- Rendering (5)

ref = (
    "{% assign dollars = product.price | divided_by: 100 %}{% assign cents = product.price | "
    'modulo: 100 %}<span class="price">${{ dollars }}.{% if cents < 10 %}0{% endif %}'
    "{{ cents }}</span>"
)
render_task(
    "price-format",
    "rendering",
    "medium",
    "Repair snippets/price-format.liquid. product.price is a nonnegative integer number of "
    "cents. Output one span class=price with text $D.CC: D is the whole-dollar amount as a "
    "base-10 integer with no separators, and CC is exactly two digits of remaining cents. "
    "Do not use Shopify money filters.",
    ref,
    [{"product": {"price": p}} for p in [0, 5, 10, 99, 100, 1234, 1230, 1200, 100000, 7]],
    lambda v: [node("span", "$%d.%02d" % divmod(v["product"]["price"], 100), {"class": "price"})],
    [
        ("float-division", '<span class="price">${{ product.price | divided_by: 100.0 }}</span>'),
        ("no-padding", ref.replace("{% if cents < 10 %}0{% endif %}", "")),
        ("cents-as-dollars", ref.replace("divided_by: 100", "times: 1")),
    ],
    starter='<span class="price">${{ product.price | divided_by: 100.0 }}</span>',
    tags=["span"],
)

ref = (
    '{% assign words = customer.name | default: "" | split: " " %}<span class="avatar">'
    "{% if words.size == 0 %}?{% else %}{{ words[0] | slice: 0 | upcase | escape }}"
    "{% if words.size > 1 %}{{ words[1] | slice: 0 | upcase | escape }}{% endif %}{% endif %}"
    "</span>"
)
render_task(
    "initials-avatar",
    "rendering",
    "easy",
    "Repair snippets/initials-avatar.liquid. customer.name is null or an ASCII string. Split "
    "it into words on runs of whitespace, ignoring leading and trailing whitespace. Output one "
    "span class=avatar whose text is the uppercased first character of the first word, "
    "followed by the uppercased first character of the second word when there is one. Use ? "
    "when there are no words.",
    ref,
    [
        {"customer": {"name": n}}
        for n in [
            "ada lovelace",
            "Grace",
            "  jean  paul  sartre ",
            None,
            "",
            "   ",
            "<b> &c",
            "x\ty",
            "o'neil smith",
            "ALAN TURING",
            "<b quinn",
        ]
    ],
    lambda v: [
        node(
            "span",
            "".join(w[0].upper() for w in (v["customer"]["name"] or "").split()[:2]) or "?",
            {"class": "avatar"},
        )
    ],
    [
        (
            "one-initial",
            ref.replace(
                "{% if words.size > 1 %}{{ words[1] | slice: 0 | upcase | escape }}{% endif %}", ""
            ),
        ),
        ("no-upcase", ref.replace(" | upcase", "")),
        ("wrong-fallback", ref.replace("%}?{%", "%}-{%")),
        ("unescaped", ref.replace(" | escape", "")),
    ],
    starter='<span class="avatar">{{ customer.name | slice: 0 | upcase }}</span>',
    tags=["span"],
)

ref = (
    '{% if crumbs.size > 0 %}<nav aria-label="Breadcrumb"><ol>{% for crumb in crumbs %}<li>'
    '{% if forloop.last %}<span aria-current="page">{{ crumb.title | escape }}</span>{% else %}'
    '<a href="{{ crumb.url | escape }}">{{ crumb.title | escape }}</a>{% endif %}</li>'
    "{% endfor %}</ol></nav>{% endif %}"
)


def crumbs(v):
    items = v["crumbs"]
    if not items:
        return []
    children = [
        node(
            "li",
            children=[
                node("span", c["title"], {"aria-current": "page"})
                if i == len(items) - 1
                else node("a", c["title"], {"href": c["url"]})
            ],
        )
        for i, c in enumerate(items)
    ]
    return [
        node("nav", attrs={"aria-label": "Breadcrumb"}, children=[node("ol", children=children)])
    ]


home, shoes = {"title": "Home", "url": "/"}, {"title": "Shoes", "url": "/collections/shoes"}
render_task(
    "breadcrumb-trail",
    "rendering",
    "medium",
    "Repair snippets/breadcrumb-trail.liquid. crumbs is an ordered array of objects with "
    "title and url strings. When it is empty output nothing. Otherwise output nav "
    "aria-label=Breadcrumb containing one ol with one li per crumb in order. Every li except "
    "the last contains one a with href equal to url and text title; the last li contains one "
    "span aria-current=page with text title and no link.",
    ref,
    [
        {"crumbs": c}
        for c in [
            [],
            [home],
            [home, shoes],
            [home, shoes, {"title": "Runner <X>", "url": "/p/runner"}],
            [home, home],
            [{"title": 'A & "B"', "url": '/s?q="x"&n=1'}, shoes],
            [{"title": "東京", "url": "/t"}, home, shoes, home],
        ]
    ],
    crumbs,
    [
        ("last-linked", ref.replace("{% if forloop.last %}", "{% if false %}")),
        ("empty-nav", ref.replace("{% if crumbs.size > 0 %}", "{% if true %}")),
        ("first-current", ref.replace("forloop.last", "forloop.first")),
        ("unescaped", ref.replace(" | escape", "")),
    ],
    starter=(
        '<nav aria-label="Breadcrumb"><ol>{% for crumb in crumbs %}<li><a href="{{ crumb.url }}">'
        "{{ crumb.title }}</a></li>{% endfor %}</ol></nav>"
    ),
    tags=["nav", "ol", "li", "a", "span"],
)

ref = (
    '<div class="rating" aria-label="{{ product.rating }} out of 5 stars"><span class="stars">'
    "{% for i in (1..5) %}{% if i <= product.rating %}★{% else %}☆{% endif %}{% endfor %}"
    '</span>{% if product.review_count == 1 %}<span class="count">(1 review)</span>'
    '{% elsif product.review_count > 1 %}<span class="count">({{ product.review_count }} '
    "reviews)</span>{% endif %}</div>"
)


def rating(v):
    r, n = v["product"]["rating"], v["product"]["review_count"]
    count = (
        []
        if n == 0
        else [node("span", "(1 review)" if n == 1 else f"({n} reviews)", {"class": "count"})]
    )
    return [
        node(
            "div",
            attrs={"class": "rating", "aria-label": f"{r} out of 5 stars"},
            children=[node("span", "★" * r + "☆" * (5 - r), {"class": "stars"}), *count],
        )
    ]


render_task(
    "rating-stars",
    "rendering",
    "medium",
    "Repair snippets/rating-stars.liquid. product.rating is an integer 0 to 5 and "
    "product.review_count a nonnegative integer. Output one div class=rating with aria-label "
    "R out of 5 stars (R is the rating). Inside it, first one span class=stars whose text is R "
    "copies of ★ followed by 5-R copies of ☆. Then, only when review_count is above 0, one "
    "span class=count with text (1 review) when the count is 1, otherwise (N reviews).",
    ref,
    [
        {"product": {"rating": r, "review_count": n}}
        for r, n in [(0, 0), (1, 1), (3, 2), (5, 0), (4, 128), (2, 1), (5, 1000), (0, 7)]
    ],
    rating,
    [
        (
            "always-plural",
            ref.replace(
                '{% if product.review_count == 1 %}<span class="count">(1 review)</span>{% elsif',
                "{% if",
            ),
        ),
        ("off-by-one", ref.replace("i <= product.rating", "i < product.rating")),
        ("missing-aria", ref.replace(' aria-label="{{ product.rating }} out of 5 stars"', "")),
        ("count-at-zero", ref.replace("review_count > 1", "review_count != 1")),
    ],
    starter=(
        '<div class="rating"><span class="stars">{% for i in (1..product.rating) %}★'
        '{% endfor %}</span><span class="count">({{ product.review_count }} reviews)</span>'
        "</div>"
    ),
    tags=["div", "span"],
)

ref = (
    "{% if paginate.pages > 1 %}{% assign win_start = paginate.current | minus: 2 %}"
    "{% if win_start < 1 %}{% assign win_start = 1 %}{% endif %}{% assign win_end = "
    "paginate.current | plus: 2 %}{% if win_end > paginate.pages %}{% assign win_end = "
    'paginate.pages %}{% endif %}<nav class="pagination">{% if paginate.current > 1 %}'
    '<a class="prev" href="?page={{ paginate.current | minus: 1 }}">Previous</a>{% endif %}'
    '{% for n in (win_start..win_end) %}{% if n == paginate.current %}<span class="current">'
    '{{ n }}</span>{% else %}<a href="?page={{ n }}">{{ n }}</a>{% endif %}{% endfor %}'
    '{% if paginate.current < paginate.pages %}<a class="next" href="?page={{ '
    'paginate.current | plus: 1 }}">Next</a>{% endif %}</nav>{% endif %}'
)


def pages(v):
    c, p = v["paginate"]["current"], v["paginate"]["pages"]
    if p <= 1:
        return []
    kids = [node("a", "Previous", {"class": "prev", "href": f"?page={c - 1}"})] if c > 1 else []
    for n in range(max(1, c - 2), min(p, c + 2) + 1):
        kids.append(
            node("span", str(n), {"class": "current"})
            if n == c
            else node("a", str(n), {"href": f"?page={n}"})
        )
    if c < p:
        kids.append(node("a", "Next", {"class": "next", "href": f"?page={c + 1}"}))
    return [node("nav", attrs={"class": "pagination"}, children=kids)]


render_task(
    "pagination-window",
    "rendering",
    "hard",
    "Repair snippets/pagination-window.liquid. paginate.current and paginate.pages are "
    "integers with 1 <= current <= pages. When pages is 1 output nothing. Otherwise output one "
    "nav class=pagination containing, in order: an a class=prev with href ?page=P and text "
    "Previous when current > 1 (P is current - 1); then each page n from max(1, current - 2) "
    "to min(pages, current + 2), where the current page is a span class=current with text n "
    "and every other page an a with href ?page=n and text n; then an a class=next with href "
    "?page=N and text Next when current < pages (N is current + 1).",
    ref,
    [
        {"paginate": {"current": c, "pages": p}}
        for c, p in [
            (1, 1),
            (1, 2),
            (2, 2),
            (1, 10),
            (3, 10),
            (5, 10),
            (9, 10),
            (10, 10),
            (2, 3),
            (4, 5),
        ]
    ],
    pages,
    [
        (
            "no-clamp-start",
            ref.replace("{% if win_start < 1 %}{% assign win_start = 1 %}{% endif %}", ""),
        ),
        ("all-pages", ref.replace("(win_start..win_end)", "(1..paginate.pages)")),
        ("current-linked", ref.replace("{% if n == paginate.current %}", "{% if false %}")),
        ("single-page-nav", ref.replace("{% if paginate.pages > 1 %}", "{% if true %}")),
    ],
    starter=(
        '<nav class="pagination">{% for n in (1..paginate.pages) %}<a href="?page={{ n }}">'
        "{{ n }}</a>{% endfor %}</nav>"
    ),
    tags=["nav", "a", "span"],
)

# ---------------------------------------------------------------- Section schema (5)

s = {
    "name": "Colors",
    "settings": [
        {"type": "color", "id": "background", "label": "Background", "default": "#ffffff"},
        {"type": "color", "id": "text", "label": "Text", "default": "#111111"},
        {"type": "checkbox", "id": "gradient", "label": "Use gradient", "default": False},
    ],
    "presets": [{"name": "Colors"}],
}
schema_task(
    "color-scheme-schema",
    "easy",
    "Colors",
    s,
    "Root name Colors. settings, in order: color id background, label Background, default "
    "#ffffff; color id text, label Text, default #111111; checkbox id gradient, label Use "
    "gradient, default false (a JSON boolean). presets contains one entry named Colors.",
    [
        ("string-boolean", lambda x: x["settings"][2].update(default="false")),
        ("wrong-type", lambda x: x["settings"][0].update(type="text")),
        ("wrong-default", lambda x: x["settings"][1].update(default="#000000")),
    ],
)

s = {
    "name": "Collection grid",
    "settings": [
        {"type": "collection", "id": "collection", "label": "Collection"},
        {
            "type": "range",
            "id": "products_to_show",
            "label": "Products to show",
            "min": 2,
            "max": 12,
            "step": 2,
            "default": 4,
        },
        {
            "type": "select",
            "id": "layout",
            "label": "Layout",
            "options": [{"value": "grid", "label": "Grid"}, {"value": "list", "label": "List"}],
            "default": "grid",
        },
    ],
    "presets": [{"name": "Collection grid", "settings": {"products_to_show": 8, "layout": "list"}}],
}
schema_task(
    "collection-grid-schema",
    "medium",
    "Collection grid",
    s,
    "Root name Collection grid. settings, in order: collection id collection, label "
    "Collection, no default; range id products_to_show, label Products to show, min 2, max 12, "
    "step 2, default 4; select id layout, label Layout, options grid/Grid then list/List, "
    "default grid. presets contains one entry named Collection grid with settings "
    "products_to_show=8 and layout=list. Numbers are JSON numbers.",
    [
        ("bad-step", lambda x: x["settings"][1].update(step=3)),
        ("missing-collection", lambda x: x["settings"].pop(0)),
        ("wrong-preset", lambda x: x["presets"][0]["settings"].update(layout="grid")),
    ],
)

s = {
    "name": "Slideshow",
    "settings": [
        {"type": "checkbox", "id": "autoplay", "label": "Autoplay", "default": False},
        {
            "type": "range",
            "id": "speed",
            "label": "Change every",
            "min": 3,
            "max": 9,
            "step": 1,
            "unit": "s",
            "default": 5,
        },
    ],
    "max_blocks": 5,
    "blocks": [
        {
            "type": "slide",
            "name": "Slide",
            "settings": [
                {"type": "image_picker", "id": "image", "label": "Image"},
                {"type": "text", "id": "heading", "label": "Heading", "default": "Slide"},
                {"type": "url", "id": "link", "label": "Link"},
            ],
        }
    ],
    "presets": [
        {
            "name": "Slideshow",
            "blocks": [
                {"type": "slide", "settings": {"heading": "First"}},
                {"type": "slide", "settings": {"heading": "Second"}},
            ],
        }
    ],
}
schema_task(
    "slideshow-blocks-schema",
    "hard",
    "Slideshow",
    s,
    "Root fields exactly: name Slideshow, settings, max_blocks=5, blocks, presets. settings, "
    "in order: checkbox id autoplay, label Autoplay, default false; range id speed, label "
    "Change every, min 3, max 9, step 1, unit s, default 5. blocks contains exactly one "
    "definition: type slide, name Slide, settings in order image_picker id image label Image; "
    "text id heading label Heading default Slide; url id link label Link. presets contains "
    "exactly one entry named Slideshow whose blocks are type slide with settings "
    "heading=First, then type slide with settings heading=Second. No other fields.",
    [
        ("default-out-of-range", lambda x: x["settings"][1].update(default=10)),
        ("missing-max-blocks", lambda x: x.pop("max_blocks")),
        ("unknown-preset-block", lambda x: x["presets"][0]["blocks"][1].update(type="banner")),
        ("wrong-block-setting", lambda x: x["blocks"][0]["settings"][2].update(id="url")),
    ],
)

s = {
    "name": "Testimonials",
    "settings": [
        {"type": "text", "id": "title", "label": "Title", "default": "What customers say"}
    ],
    "blocks": [
        {
            "type": "quote",
            "name": "Quote",
            "limit": 6,
            "settings": [
                {"type": "textarea", "id": "body", "label": "Quote"},
                {"type": "text", "id": "author", "label": "Author"},
            ],
        }
    ],
    "presets": [{"name": "Testimonials"}],
}
schema_task(
    "testimonials-schema",
    "medium",
    "Testimonials",
    s,
    "Root fields exactly: name Testimonials, settings, blocks, presets. settings contains one "
    "text id title, label Title, default What customers say. blocks contains exactly one "
    "definition: type quote, name Quote, limit 6 (a JSON number), settings in order textarea "
    "id body label Quote, then text id author label Author. presets contains one entry named "
    "Testimonials with no other fields.",
    [
        ("string-limit", lambda x: x["blocks"][0].update(limit="6")),
        ("missing-author", lambda x: x["blocks"][0]["settings"].pop()),
        ("richtext-body", lambda x: x["blocks"][0]["settings"][0].update(type="richtext")),
    ],
)

s = {
    "name": "Footer",
    "settings": [
        {"type": "link_list", "id": "menu", "label": "Menu", "default": "footer"},
        {"type": "checkbox", "id": "show_payment", "label": "Show payment icons", "default": True},
        {"type": "text", "id": "copyright", "label": "Copyright"},
    ],
}
schema_task(
    "footer-schema",
    "easy",
    "Footer",
    s,
    "Root fields exactly: name Footer and settings; no presets. settings, in order: link_list "
    "id menu, label Menu, default footer; checkbox id show_payment, label Show payment icons, "
    "default true (a JSON boolean); text id copyright, label Copyright, no default.",
    [
        ("string-boolean", lambda x: x["settings"][1].update(default="true")),
        ("missing-menu-default", lambda x: x["settings"][0].pop("default")),
        ("extra-presets", lambda x: x.update(presets=[{"name": "Footer"}])),
    ],
)

# ---------------------------------------------------------------- Theme references (4)


def loc(en, fr):
    return {"locales/en.default.json": json.dumps(en), "locales/fr.json": json.dumps(fr)}


ref = (
    '<a href="/" class="logo"><img src="{{ \'logo.svg\' | asset_url }}" '
    'alt="{{ \'header.logo_alt\' | t }}" width="120" height="40"></a>'
)
refs(
    "logo-asset",
    "easy",
    ref,
    ref.replace("'logo.svg'", "'logo.SVG'").replace("header.logo_alt", "header.logoAlt"),
    {
        "assets/logo.svg": '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        **loc({"header": {"logo_alt": "Home"}}, {"header": {"logo_alt": "Accueil"}}),
    },
    "img src uses the existing assets/logo.svg through asset_url; alt uses header.logo_alt "
    "through t (translate accepted); both locales must resolve the key.",
    [
        ("path-prefix", ref.replace("'logo.svg'", "'assets/logo.svg'")),
        ("literal-alt", ref.replace("{{ 'header.logo_alt' | t }}", "Home")),
        ("dropped-size", ref.replace(' width="120" height="40"', "")),
    ],
)

ref = (
    "<script src=\"{{ 'cart.js' | asset_url }}\" defer></script>"
    "{{ 'cart.css' | asset_url | stylesheet_tag }}"
)
refs(
    "cart-assets",
    "medium",
    ref,
    ref.replace("'cart.js'", "'cart.min.js'").replace("'cart.css'", "'carts.css'"),
    {"assets/cart.js": "export {};\n", "assets/cart.css": ".cart { display: grid; }\n"},
    "script src uses the existing assets/cart.js through asset_url and keeps defer; the "
    "following output uses the existing assets/cart.css through asset_url then stylesheet_tag.",
    [
        (
            "swapped",
            ref.replace("'cart.js'", "TEMP")
            .replace("'cart.css'", "'cart.js'")
            .replace("TEMP", "'cart.css'"),
        ),
        ("missing-defer", ref.replace(" defer", "")),
        ("filter-order", ref.replace("asset_url | stylesheet_tag", "stylesheet_tag | asset_url")),
    ],
)

ref = (
    "<h2>{{ 'cart.title' | t }}</h2><p class=\"empty\">{{ 'cart.empty' | t }}</p>"
    "<button type=\"submit\">{{ 'cart.checkout' | t }}</button>"
)
refs(
    "cart-labels",
    "medium",
    ref,
    ref.replace("cart.title", "cart.heading").replace("cart.checkout", "cart.check_out"),
    loc(
        {"cart": {"title": "Your cart", "empty": "Your cart is empty", "checkout": "Check out"}},
        {
            "cart": {
                "title": "Votre panier",
                "empty": "Votre panier est vide",
                "checkout": "Paiement",
            }
        },
    ),
    "h2 uses cart.title, p uses cart.empty and button uses cart.checkout, each through t "
    "(translate accepted); both locales must resolve all three keys.",
    [
        (
            "swapped",
            ref.replace("cart.title", "TEMP")
            .replace("cart.empty", "cart.title")
            .replace("TEMP", "cart.empty"),
        ),
        ("literal-text", ref.replace("{{ 'cart.checkout' | t }}", "Check out")),
        ("one-key-wrong", ref.replace("cart.checkout", "cart.check_out")),
    ],
)

ref = (
    "{% render 'price-tag', price: product.price, compare: product.compare_at_price %}"
    "<span class=\"label\">{{ 'products.sale' | t }}</span>"
)
refs(
    "price-render",
    "hard",
    ref,
    ref.replace("'price-tag'", "'price_tag'").replace("products.sale", "product.sale"),
    {
        "snippets/price-tag.liquid": '<span class="price">{{ price }}</span>\n',
        **loc({"products": {"sale": "Sale"}}, {"products": {"sale": "Solde"}}),
    },
    "The render tag uses the existing snippets/price-tag.liquid and keeps both named "
    "arguments price and compare with their values; the span uses products.sale through t "
    "(translate accepted); both locales must resolve the key.",
    [
        ("include-tag", ref.replace("{% render", "{% include")),
        ("dropped-argument", ref.replace(", compare: product.compare_at_price", "")),
        ("renamed-argument", ref.replace("compare: product", "compare_at: product")),
    ],
)

# ---------------------------------------------------------------- Theme modification (5)

ref = (
    '<section class="hero" data-id="{{ section.id | escape }}"><h2>{{ section.settings.heading | '
    'escape }}</h2>{% assign label = section.settings.cta_label | default: "" | strip %}'
    '{% assign url = section.settings.cta_url | default: "" | strip %}{% if label != empty and '
    'url != empty %}<a class="button" href="{{ url | escape }}">{{ label | escape }}</a>'
    "{% endif %}</section>"
)


def hero(v):
    st = v["section"]["settings"]
    label, url = trim(st["cta_label"]), trim(st["cta_url"])
    cta = [node("a", label, {"class": "button", "href": url})] if label and url else []
    return [
        node(
            "section",
            attrs={"class": "hero", "data-id": v["section"]["id"]},
            children=[node("h2", st["heading"]), *cta],
        )
    ]


render_task(
    "hero-cta",
    "theme-modification",
    "easy",
    "Modify sections/hero-cta.liquid to add an optional call-to-action link after the h2, "
    "inside the existing section. Inputs: section.id and section.settings.heading are "
    "strings; section.settings.cta_label and section.settings.cta_url are null or strings. "
    "Emit one a class=button only when both the ASCII-trimmed label and the ASCII-trimmed url "
    "are nonempty; its href is the trimmed url and its text the trimmed label. Preserve the "
    "existing section class, data-id and heading with their escaping.",
    ref,
    [
        {
            "section": {
                "id": 'h"&',
                "settings": {"heading": "Big <Sale>", "cta_label": lab, "cta_url": url},
            }
        }
        for lab, url in itertools.product(
            [None, "", " \t", " Shop now "], [None, "", " /collections/all ", '/sale?x="1"&y=2']
        )
    ],
    hero,
    [
        ("label-only-guard", ref.replace("label != empty and url != empty", "label != empty")),
        ("untrimmed", ref.replace(" | strip", "")),
        (
            "outside-section",
            ref.replace("{% endif %}</section>", "{% endif %}").replace(
                "</h2>{% assign", "</h2></section>{% assign"
            ),
        ),
    ],
    starter=(
        '<section class="hero" data-id="{{ section.id | escape }}"><h2>{{ '
        "section.settings.heading | escape }}</h2></section>"
    ),
    tags=["section", "h2", "a"],
    schema=section_schema(
        "Hero",
        [
            {"type": "text", "id": "cta_label", "label": "Button label"},
            {"type": "url", "id": "cta_url", "label": "Button link"},
        ],
    ),
)

ref = (
    '<section class="card" data-id="{{ section.id | escape }}">{% if product.compare_at_price %}'
    '{% if product.compare_at_price > product.price %}<span class="badge">Sale</span>{% endif %}'
    '{% endif %}<h3>{{ section.settings.heading | escape }}</h3><p class="price">{{ price_label '
    "| escape }}</p></section>"
)


def card(v):
    p = v["product"]
    badge = (
        [node("span", "Sale", {"class": "badge"})]
        if p["compare_at_price"] is not None and p["compare_at_price"] > p["price"]
        else []
    )
    return [
        node(
            "section",
            attrs={"class": "card", "data-id": v["section"]["id"]},
            children=[
                *badge,
                node("h3", v["section"]["settings"]["heading"]),
                node("p", v["price_label"], {"class": "price"}),
            ],
        )
    ]


render_task(
    "card-sale-badge",
    "theme-modification",
    "medium",
    "Modify sections/card-sale-badge.liquid to add a sale badge. Inputs: section.id and "
    "section.settings.heading are strings; price_label is a top-level string; product.price "
    "is a nonnegative integer and product.compare_at_price null or a positive integer. When "
    "compare_at_price is greater than price, emit one span class=badge with text Sale as the "
    "first child of the existing section, before the h3. Preserve the section class and "
    "data-id, the h3 heading and the p class=price with their text and escaping.",
    ref,
    [
        {
            "section": {"id": "c<&", "settings": {"heading": "Trail <Runner>"}},
            "price_label": "$120 & up",
            "product": {"price": p, "compare_at_price": c},
        }
        for p, c in [(100, None), (100, 100), (100, 150), (150, 100), (0, 1), (999, 1000)]
    ],
    card,
    [
        (
            "shows-equal",
            ref.replace("compare_at_price > product.price", "compare_at_price >= product.price"),
        ),
        (
            "after-heading",
            ref.replace(
                "{% if product.compare_at_price %}{% if product.compare_at_price"
                ' > product.price %}<span class="badge">Sale</span>{% endif %}'
                "{% endif %}<h3>{{ section.settings.heading | escape }}</h3>",
                "<h3>{{ section.settings.heading | escape }}</h3>{% if "
                "product.compare_at_price %}{% if product.compare_at_price > "
                'product.price %}<span class="badge">Sale</span>{% endif %}'
                "{% endif %}",
            ),
        ),
        ("lost-price", ref.replace('<p class="price">{{ price_label | escape }}</p>', "")),
    ],
    starter=(
        '<section class="card" data-id="{{ section.id | escape }}"><h3>{{ '
        'section.settings.heading | escape }}</h3><p class="price">{{ price_label | escape '
        "}}</p></section>"
    ),
    tags=["section", "h3", "p", "span"],
    schema=section_schema("Card", []),
)

ref = (
    "{% assign columns = section.settings.columns %}{% if columns < 1 %}{% assign columns = 1 %}"
    "{% endif %}{% if columns > 4 %}{% assign columns = 4 %}{% endif %}<section "
    'data-id="{{ section.id | escape }}">{% if items.size == 0 %}<p class="empty">Nothing here'
    '</p>{% else %}<ul class="grid" data-columns="{{ columns }}">{% for item in items %}<li>'
    "{{ item | escape }}</li>{% endfor %}</ul>{% endif %}</section>"
)


def grid(v):
    cols = min(4, max(1, v["section"]["settings"]["columns"]))
    inner = (
        [node("p", "Nothing here", {"class": "empty"})]
        if not v["items"]
        else [
            node(
                "ul",
                attrs={"class": "grid", "data-columns": str(cols)},
                children=[node("li", x) for x in v["items"]],
            )
        ]
    )
    return [node("section", attrs={"data-id": v["section"]["id"]}, children=inner)]


render_task(
    "grid-columns",
    "theme-modification",
    "medium",
    "Modify sections/grid-columns.liquid. Inputs: section.id is a string; "
    "section.settings.columns is an integer that may be outside 1 to 4; items is a top-level "
    "ordered array of strings. Keep the existing section data-id. When items is nonempty, "
    "keep the ul class=grid with one li per item in order, and add the attribute data-columns "
    "equal to columns clamped to the range 1 to 4. When items is empty, replace the ul with "
    "one p class=empty with text Nothing here.",
    ref,
    [
        {"section": {"id": 'g"<', "settings": {"columns": c}}, "items": i}
        for c, i in [
            (3, ["A", "B"]),
            (0, ["A"]),
            (-2, ["<x>", "&"]),
            (4, ["A"]),
            (9, ["A", "B", "C"]),
            (1, ["東京"]),
            (2, []),
            (5, []),
            (2, ["A", "A"]),
        ]
    ],
    grid,
    [
        (
            "no-low-clamp",
            ref.replace("{% if columns < 1 %}{% assign columns = 1 %}{% endif %}", ""),
        ),
        (
            "no-high-clamp",
            ref.replace("{% if columns > 4 %}{% assign columns = 4 %}{% endif %}", ""),
        ),
        ("empty-ul", ref.replace("{% if items.size == 0 %}", "{% if false %}")),
        (
            "attribute-on-section",
            ref.replace(' data-columns="{{ columns }}"', "").replace(
                '<section data-id="{{ section.id | escape }}">',
                '<section data-id="{{ section.id | escape }}" data-columns="{{ columns }}">',
            ),
        ),
    ],
    starter=(
        '<section data-id="{{ section.id | escape }}"><ul class="grid">{% for item in items %}'
        "<li>{{ item | escape }}</li>{% endfor %}</ul></section>"
    ),
    tags=["section", "ul", "li", "p"],
    schema=section_schema(
        "Grid",
        [
            {
                "type": "range",
                "id": "columns",
                "label": "Columns",
                "min": 1,
                "max": 4,
                "step": 1,
                "default": 3,
            }
        ],
    ),
)

ref = (
    '<section data-id="{{ section.id | escape }}"><h2>{{ section.settings.heading | escape }}'
    "</h2>{% assign shown = 0 %}{% for faq in faqs %}{% assign question = faq.question | "
    'default: "" | strip %}{% if question != empty %}<details{% if shown == 0 %} open'
    "{% endif %}><summary>{{ question | escape }}</summary><p>{{ faq.answer | escape }}</p>"
    "</details>{% assign shown = shown | plus: 1 %}{% endif %}{% endfor %}{% if shown == 0 %}"
    '<p class="empty">No questions yet</p>{% endif %}</section>'
)


def faq(v):
    kids = [node("h2", v["section"]["settings"]["heading"])]
    shown = 0
    for f in v["faqs"]:
        q = trim(f["question"])
        if q:
            kids.append(
                node(
                    "details",
                    attrs={"open": ""} if shown == 0 else {},
                    children=[node("summary", q), node("p", f["answer"] or "")],
                )
            )
            shown += 1
    if not shown:
        kids.append(node("p", "No questions yet", {"class": "empty"}))
    return [node("section", attrs={"data-id": v["section"]["id"]}, children=kids)]


def q(question, answer):
    return {"question": question, "answer": answer}


render_task(
    "faq-details",
    "theme-modification",
    "hard",
    "Modify sections/faq-details.liquid into an accordion. Inputs: section.id and "
    "section.settings.heading are strings; faqs is a top-level ordered array of objects whose "
    "question and answer are null or strings. Keep the section data-id and h2 heading. For "
    "each faq whose ASCII-trimmed question is nonempty, in order, emit one details containing "
    "a summary with the trimmed question and then a p with the answer exactly as given (empty "
    "when null). Skip other faqs. The first emitted details, and only that one, has the open "
    "attribute. When no details is emitted, output one p class=empty with text No questions "
    "yet after the h2.",
    ref,
    [
        {"section": {"id": 'f&"', "settings": {"heading": "FAQ <1>"}}, "faqs": f}
        for f in [
            [],
            [q("Shipping?", "3 days")],
            [q("  ", "x"), q("Returns?", "30 days"), q("Sizes?", None)],
            [q(None, "x"), q("", "y")],
            [q(" <b>Q</b> ", " A & B "), q("Q2", "")],
            [q("A", "1"), q("B", "2"), q("C", "3")],
            [q("\t", None), q(None, None), q("Last", "z")],
        ]
    ],
    faq,
    [
        (
            "forloop-first-open",
            ref.replace(
                "{% if shown == 0 %} open{% endif %}", "{% if forloop.first %} open{% endif %}"
            ),
        ),
        ("unescaped", ref.replace(" | escape", "")),
        ("untrimmed", ref.replace(' | default: "" | strip', ' | default: ""')),
        ("all-open", ref.replace("{% if shown == 0 %} open{% endif %}", " open")),
    ],
    starter=(
        '<section data-id="{{ section.id | escape }}"><h2>{{ section.settings.heading | escape '
        "}}</h2>{% for faq in faqs %}<p>{{ faq.question }}</p><p>{{ faq.answer }}</p>"
        "{% endfor %}</section>"
    ),
    tags=["section", "h2", "details", "summary", "p"],
    schema=section_schema("FAQ", []),
)

ref = (
    '<section data-id="{{ section.id | escape }}">{% if section.settings.ends_at > now %}'
    '<p class="message">{{ section.settings.message | escape }}</p>{% assign remaining = '
    "section.settings.ends_at | minus: now %}{% assign hours = remaining | divided_by: 3600 %}"
    '{% assign minutes = remaining | modulo: 3600 | divided_by: 60 %}<p class="countdown">'
    'Ends in {{ hours }}h {{ minutes }}m</p>{% else %}<p class="message">Sale ended</p>'
    "{% endif %}</section>"
)


def countdown(v):
    left = v["section"]["settings"]["ends_at"] - v["now"]
    kids = (
        [
            node("p", v["section"]["settings"]["message"], {"class": "message"}),
            node("p", f"Ends in {left // 3600}h {left % 3600 // 60}m", {"class": "countdown"}),
        ]
        if left > 0
        else [node("p", "Sale ended", {"class": "message"})]
    )
    return [node("section", attrs={"data-id": v["section"]["id"]}, children=kids)]


render_task(
    "sale-countdown",
    "theme-modification",
    "hard",
    "Modify sections/sale-countdown.liquid. Inputs: section.id and section.settings.message "
    "are strings; section.settings.ends_at and the top-level now are integer Unix timestamps "
    "in seconds. Keep the section data-id. While ends_at is later than now, keep the existing "
    "p class=message with the message text and add after it one p class=countdown with text "
    "Ends in Hh Mm, where R = ends_at - now, H = floor(R / 3600) and M = floor((R mod 3600) / "
    "60), both base-10 integers. When ends_at is not later than now, output only one p "
    "class=message with text Sale ended inside the section.",
    ref,
    [
        {
            "section": {
                "id": 's"&',
                "settings": {"message": "Summer <sale> & more", "ends_at": 1_800_000_000 + d},
            },
            "now": 1_800_000_000,
        }
        for d in [0, -5, 1, 59, 60, 3599, 3600, 3661, 90061, 86400 * 3]
    ],
    countdown,
    [
        ("inclusive-end", ref.replace("ends_at > now", "ends_at >= now")),
        ("total-minutes", ref.replace("modulo: 3600 | divided_by: 60", "divided_by: 60")),
        (
            "ended-keeps-message",
            ref.replace(
                '<p class="message">Sale ended</p>',
                '<p class="message">{{ section.settings.message | escape }}</p>',
            ),
        ),
    ],
    starter=(
        '<section data-id="{{ section.id | escape }}"><p class="message">{{ '
        "section.settings.message | escape }}</p></section>"
    ),
    tags=["section", "p"],
    schema=section_schema(
        "Countdown",
        [
            {"type": "text", "id": "message", "label": "Message"},
            {"type": "number", "id": "ends_at", "label": "Ends at (Unix seconds)"},
        ],
    ),
)
