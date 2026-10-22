"""Task-specific behavior grading; hidden cases never enter the agent sandbox."""

from html.parser import HTMLParser
import re

from .sandbox import Sandbox


class CardParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"tag": "root", "attrs": [], "children": [], "text": ""}
        self.stack = [self.root]
        self.invalid = False

    def handle_starttag(self, tag, attrs):
        if tag not in {"article", "h2", "p", "span"}:
            self.invalid = True
        if len({name for name, _ in attrs}) != len(attrs):
            self.invalid = True
        attrs = [
            (
                name,
                " ".join(sorted(set(value.split()))) if name == "class" and value else value or "",
            )
            for name, value in attrs
        ]
        node = {"tag": tag, "attrs": sorted(attrs), "children": [], "text": ""}
        self.stack[-1]["children"].append(node)
        self.stack.append(node)

    def handle_endtag(self, tag):
        if len(self.stack) == 1 or self.stack[-1]["tag"] != tag:
            self.invalid = True
        else:
            self.stack.pop()

    def handle_startendtag(self, tag, attrs):
        self.invalid = True

    def handle_data(self, data):
        self.stack[-1]["text"] += data

    def handle_decl(self, decl):
        self.invalid = True

    def parse_html_declaration(self, index):
        # Newer Python versions treat some invalid declarations as comments.
        # Reject declarations consistently, without rejecting ordinary comments.
        if not self.rawdata.startswith("<!--", index):
            self.invalid = True
        return super().parse_html_declaration(index)


def matches_card(html, product):
    parser = CardParser()
    try:
        parser.feed(html)
        parser.close()
    except (ValueError, AssertionError):
        # HTMLParser can raise on malformed declarations; submitted markup is
        # a task failure, not a crashed evaluator or a missing infrastructure run.
        return False
    if parser.invalid or len(parser.stack) != 1 or parser.root["text"].strip():
        return False
    roots = parser.root["children"]
    if len(roots) != 1:
        return False
    card = roots[0]
    if (
        card["tag"] != "article"
        or card["attrs"] != [("class", "product-card")]
        or card["text"].strip()
    ):
        return False
    vendor = (product["vendor"] or "").strip()
    expected = [("h2", [], product["title"] or "Untitled product")]
    if vendor:
        expected.append(("p", [("class", "vendor")], vendor))
    expected.append(
        ("span", [("class", "availability")], "In stock" if product["available"] else "Sold out")
    )
    if len(card["children"]) != len(expected):
        return False
    return all(
        node["tag"] == tag
        and node["attrs"] == attrs
        and not node["children"]
        and node["text"] == text
        for node, (tag, attrs, text) in zip(card["children"], expected)
    )


def check(name, passed, detail=None):
    return {"name": name, "passed": bool(passed), "detail": detail}


def grade(task, files, image):
    if task.manifest["id"] != "product-card":
        raise ValueError("No grader registered for this task")
    checks = []
    changed = {p for p in set(files) | set(task.initial) if files.get(p) != task.initial.get(p)}
    allowed = set(task.manifest["editable_files"])
    scope_ok = changed <= allowed and set(files) == set(task.initial)
    checks.append(check("edit_scope", scope_ok, sorted(changed)))
    source = files.get("snippets/product-card.liquid", "")
    suppressed = bool(re.search(r"theme[\s_-]*check[\s_-]*(?:disable|enable)", source, re.I))
    checks.append(check("no_suppressions", not suppressed))
    if not scope_ok or suppressed:
        return {"passed": False, "checks": checks}
    # A new container receives only the final files. Agent processes are gone.
    with Sandbox(image, files) as evaluator:
        offenses = evaluator.call("check")["offenses"]
        errors = [item for item in offenses if item["severity"] == 0]
        checks.append(check("theme_check", not errors, offenses))
        for case in task.cases:
            rendered = evaluator.call(
                "render",
                {"path": "snippets/product-card.liquid", "variables": {"product": case["product"]}},
            )
            passed = rendered["ok"] and matches_card(rendered["output"], case["product"])
            checks.append(
                check(case["id"], passed, None if passed else rendered.get("error", "DOM mismatch"))
            )
    return {"passed": all(item["passed"] for item in checks), "checks": checks}


def validation_candidates(task):
    reference = task.reference
    return {
        "starter": (task.initial, False),
        "reference": ({**task.initial, "snippets/product-card.liquid": reference}, True),
        "unescaped": (
            {**task.initial, "snippets/product-card.liquid": reference.replace(" | escape", "")},
            False,
        ),
        "always_in_stock": (
            {
                **task.initial,
                "snippets/product-card.liquid": reference.replace(
                    "if product.available", "if true"
                ),
            },
            False,
        ),
        "missing_fallback": (
            {
                **task.initial,
                "snippets/product-card.liquid": reference.replace(
                    " | default: 'Untitled product'", ""
                ),
            },
            False,
        ),
        "hardcoded": (
            {
                **task.initial,
                "snippets/product-card.liquid": '<article class="product-card"><h2>Cotton Tee</h2>'
                '<p class="vendor">North</p><span class="availability">In stock</span>'
                "</article>",
            },
            False,
        ),
        "suppressed": (
            {
                **task.initial,
                "snippets/product-card.liquid": "{% # theme-check-disable %}" + reference,
            },
            False,
        ),
        "grader_config": (
            {
                **task.initial,
                "snippets/product-card.liquid": reference,
                ".theme-check.yml": "extends: []",
            },
            False,
        ),
    }
