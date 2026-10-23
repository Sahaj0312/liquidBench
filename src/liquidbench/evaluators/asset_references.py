"""Static reference resolution with AST preservation, no mocked Shopify filters."""

from .common import check, strict_json, walk_nodes


def structure(value):
    """Ignore literal operands and harmless quote/spacing differences only."""
    if isinstance(value, list):
        return [
            structure(v)
            for v in value
            if not (
                isinstance(v, dict)
                and v.get("type") == "TextNode"
                and not v.get("value", "").strip()
            )
        ]
    if not isinstance(value, dict):
        return value
    result = {
        k: structure(v)
        for k, v in value.items()
        if k
        not in {
            "single",
            "whitespaceStart",
            "whitespaceEnd",
            "delimiterWhitespaceStart",
            "delimiterWhitespaceEnd",
        }
    }
    if result.get("type") == "String":
        result["value"] = "__literal_operand__"
    if result.get("type") == "LiquidFilter" and result.get("name") == "translate":
        result["name"] = "t"
    return result


def lookup(value, key):
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


def evaluate(task, files, sandbox):
    path = "snippets/promo-assets.liquid"
    parsed = sandbox.call("analyze", {"path": path})
    if not parsed["ok"]:
        return [check("liquid_structure", False, parsed["error"])]
    # Baseline AST is author-supplied evaluator data, never copied into an agent sandbox.
    expected_ast = task.cases[0]["original_ast"]
    checks = [
        check("preserved_live_structure", structure(parsed["ast"]) == structure(expected_ast))
    ]
    outputs = [n for n in walk_nodes(parsed["ast"]) if n.get("type") == "LiquidVariableOutput"]
    checks.append(check("output_count", len(outputs) == len(task.cases)))
    if len(outputs) != len(task.cases):
        return checks
    locales = {p: strict_json(text) for p, text in task.initial.items() if p.startswith("locales/")}
    for output, case in zip(outputs, task.cases):
        markup = output.get("markup", {})
        expression = markup.get("expression", {}) if isinstance(markup, dict) else {}
        filters = markup.get("filters", []) if isinstance(markup, dict) else []
        names = ["t" if f["name"] == "translate" else f["name"] for f in filters]
        literal = expression.get("value") if expression.get("type") == "String" else None
        valid = literal == case["literal"] and names == case["filters"]
        checks.append(check(case["id"] + "_reference", valid))
        if case["filters"][0] == "asset_url":
            resolved = literal is not None and "assets/" + literal in files
        else:
            resolved = isinstance(literal, str) and all(
                isinstance(lookup(data, literal), str) for data in locales.values()
            )
        checks.append(check(case["id"] + "_resolves", resolved))
    return checks
