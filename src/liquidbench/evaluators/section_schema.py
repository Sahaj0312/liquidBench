"""Declared JSON contract, not a simulation of Shopify's theme editor."""

from .common import check, same_json, strict_json


def evaluate(task, files, sandbox):
    parsed = sandbox.call("analyze", {"path": "sections/feature-panel.liquid"})
    if not parsed["ok"]:
        return [check("liquid_structure", False, parsed["error"])]
    schemas = parsed["schemas"]
    valid_block = len(schemas) == 1 and schemas[0]["top_level"]
    checks = [check("single_top_level_schema", valid_block)]
    if not valid_block:
        return checks
    case = task.cases[0]
    checks.append(check("preserved_markup", parsed["body_source"] == case["body"]))
    try:
        schema = strict_json(schemas[0]["body"])
    except ValueError as exc:
        return checks + [check("strict_schema_json", False, str(exc))]
    checks.append(check("strict_schema_json", isinstance(schema, dict)))
    if not isinstance(schema, dict):
        return checks
    expected = case["schema"]
    checks.append(
        check(
            "root_contract",
            schema.keys() == expected.keys() and schema.get("name") == expected["name"],
        )
    )
    settings = schema.get("settings")
    valid_ids = (
        isinstance(settings, list)
        and len(settings) == len(expected["settings"])
        and all(isinstance(s, dict) and isinstance(s.get("id"), str) for s in settings)
    )
    by_id = {s["id"]: s for s in settings} if valid_ids else {}
    expected_ids = {s["id"] for s in expected["settings"]}
    checks.append(
        check(
            "unique_setting_ids",
            valid_ids and len(by_id) == len(settings) and by_id.keys() == expected_ids,
        )
    )
    for wanted in expected["settings"]:
        actual = by_id.get(wanted["id"], {})
        # Labels may differ, but must exist and be nonempty. Order is not significant.
        label = actual.get("label")
        valid = (
            isinstance(label, str)
            and bool(label.strip())
            and same_json(
                {k: v for k, v in actual.items() if k != "label"},
                {k: v for k, v in wanted.items() if k != "label"},
            )
        )
        checks.append(check("setting_" + wanted["id"], valid))
    checks.append(check("preset_contract", same_json(schema.get("presets"), expected["presets"])))
    return checks
