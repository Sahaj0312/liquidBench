"""New subtitle behavior plus regression checks over a supplied section hash."""

from .common import check
from .dom import element, fragment


def evaluate(task, files, sandbox):
    path = "sections/announcement.liquid"
    parsed = sandbox.call("analyze", {"path": path})
    if not parsed["ok"]:
        return [check("liquid_structure", False, parsed["error"])]
    schemas = parsed["schemas"]
    preserved = (
        len(schemas) == 1
        and schemas[0]["top_level"]
        and schemas[0]["block"] == task.cases[0]["schema_block"]
    )
    checks = [check("preserved_schema", preserved)]
    if not preserved:
        return checks
    for case in task.cases[1:]:
        section = case["variables"]["section"]
        settings = section["settings"]
        children = [element("h2", settings["heading"])]
        subtitle = (settings["subtitle"] or "").strip(" \t\r\n\v\f")
        if subtitle:
            children.append(element("p", subtitle, {"class": "announcement__subtitle"}))
        if settings["show_body"]:
            children.append(element("p", settings["body"], {"class": "announcement__body"}))
        expected = [
            element(
                "section",
                attrs={"class": "announcement", "data-section-id": section["id"]},
                children=children,
            )
        ]
        if not settings["enabled"]:
            expected = []
        rendered = sandbox.call(
            "render", {"path": path, "variables": case["variables"], "strip_schema": True}
        )
        actual = fragment(rendered["output"], {"section", "h2", "p"}) if rendered["ok"] else None
        # Whitespace between children is immaterial; child text remains exact.
        if actual:
            for node in actual:
                if not node["text"].strip():
                    node["text"] = ""
        passed = rendered["ok"] and actual == expected
        checks.append(
            check(case["id"], passed, None if passed else rendered.get("error", "DOM mismatch"))
        )
    return checks
