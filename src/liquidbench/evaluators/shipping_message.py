"""Core Liquid branches, false preservation, thresholds, and escaped fallbacks."""

from .common import check
from .dom import element, fragment


def evaluate(task, files, sandbox):
    checks = []
    for case in task.cases:
        variables = case["variables"]
        settings, cart = variables["settings"], variables["cart"]
        expected = []
        if settings["enabled"]:
            threshold = 5000 if settings["threshold"] is None else settings["threshold"]
            if cart["item_count"] == 0:
                text = "Your cart is empty"
            elif cart["total"] >= threshold:
                text = "Free shipping unlocked"
            else:
                text = (settings["message"] or "").strip(" \t\r\n\v\f") or "Keep shopping"
            expected = [element("p", text, {"class": "shipping-message"})]
        rendered = sandbox.call(
            "render", {"path": "snippets/shipping-message.liquid", "variables": variables}
        )
        passed = rendered["ok"] and fragment(rendered["output"], {"p"}) == expected
        checks.append(
            check(case["id"], passed, None if passed else rendered.get("error", "DOM mismatch"))
        )
    return checks
