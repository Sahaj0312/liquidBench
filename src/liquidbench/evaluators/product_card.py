"""Product-card DOM evaluator; receives hidden cases only on the host."""

from html.parser import HTMLParser

from .common import check


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


def evaluate(task, files, evaluator):
    checks = []
    for case in task.cases:
        rendered = evaluator.call(
            "render",
            {"path": "snippets/product-card.liquid", "variables": {"product": case["product"]}},
        )
        passed = rendered["ok"] and matches_card(rendered["output"], case["product"])
        checks.append(
            check(case["id"], passed, None if passed else rendered.get("error", "DOM mismatch"))
        )
    return checks
