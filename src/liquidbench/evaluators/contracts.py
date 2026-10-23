"""Declarative development contracts; expected outputs stay on the host.

No fixture code is imported or executed. Rendering uses only the existing strict
core Liquid sandbox. Schema/reference checks do not emulate Shopify services.
"""

from .common import check, same_json, strict_json
from .dom import fragment


def dom_value(nodes):
    """Normalize JSON attribute pairs and whitespace-only container text."""
    if nodes is None:
        return None
    return [
        {
            **node,
            "attrs": [list(pair) for pair in node["attrs"]],
            "text": "" if node["children"] and not node["text"].strip() else node["text"],
            "children": dom_value(node["children"]),
        }
        for node in nodes
    ]


def render_contract(task, files, sandbox):
    contract = task.cases[0]
    checks = []
    if "schema_block" in contract:
        parsed = sandbox.call("analyze", {"path": contract["path"]})
        schemas = parsed.get("schemas", [])
        preserved = (
            parsed["ok"]
            and len(schemas) == 1
            and schemas[0]["top_level"]
            and schemas[0]["block"] == contract["schema_block"]
        )
        checks.append(check("preserved_schema", preserved))
        if not preserved:
            return checks
    for case in task.cases[1:]:
        reply = sandbox.call(
            "render",
            {
                "path": contract["path"],
                "variables": case["variables"],
                "strip_schema": "schema_block" in contract,
            },
        )
        actual = dom_value(fragment(reply["output"], contract["tags"])) if reply["ok"] else None
        passed = reply["ok"] and actual == case["expected"]
        checks.append(
            check(case["id"], passed, None if passed else reply.get("error", "DOM mismatch"))
        )
    return checks


def schema_contract(task, files, sandbox):
    contract = task.cases[0]
    parsed = sandbox.call("analyze", {"path": contract["path"]})
    schemas = parsed.get("schemas", [])
    valid = parsed["ok"] and len(schemas) == 1 and schemas[0]["top_level"]
    checks = [check("single_top_level_schema", valid)]
    if not valid:
        return checks
    checks.append(check("preserved_markup", parsed["body_source"] == contract["body"]))
    try:
        value = strict_json(schemas[0]["body"])
    except ValueError as exc:
        return checks + [check("strict_schema_json", False, str(exc))]
    return checks + [check("declared_schema_contract", same_json(value, contract["expected"]))]


def reference_shape(value):
    """Keep every literal and live node; ignore quote style and formatting only."""
    if isinstance(value, list):
        return [
            reference_shape(v)
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
        k: reference_shape(v)
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
    if result.get("type") == "LiquidFilter" and result.get("name") == "translate":
        result["name"] = "t"
    return result


def reference_contract(task, files, sandbox):
    contract = task.cases[0]
    parsed = sandbox.call("analyze", {"path": contract["path"]})
    return [
        check(
            "live_reference_structure",
            parsed["ok"]
            and reference_shape(parsed.get("ast")) == reference_shape(contract["expected_ast"]),
        )
    ]
