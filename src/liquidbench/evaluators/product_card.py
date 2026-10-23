"""Product-card DOM evaluator; receives hidden cases only on the host."""

from .dom import FragmentParser

from .common import check


def matches_card(html, product):
    parser = FragmentParser({"article", "h2", "p", "span"})
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
