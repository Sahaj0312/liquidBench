"""Shared integrity gates and dispatch to trusted task evaluators."""

import re

from .evaluators import get_evaluator
from .evaluators.common import check
from .evaluators.product_card import matches_card as matches_card  # Existing public helper.
from .sandbox import Sandbox


def grade(task, files, image):
    evaluate = get_evaluator(task.manifest["evaluator"])
    changed = {p for p in set(files) | set(task.initial) if files.get(p) != task.initial.get(p)}
    scope_ok = changed <= set(task.manifest["editable_files"]) and set(files) == set(task.initial)
    checks = [check("edit_scope", scope_ok, sorted(changed))]
    suppressed = [
        p
        for p, text in files.items()
        if p.endswith(".liquid")
        and re.search(r"theme[\s_-]*check[\s_-]*(?:disable|enable)", text, re.I)
    ]
    checks.append(check("no_suppressions", not suppressed, suppressed))
    if not scope_ok or suppressed:
        return {"passed": False, "checks": checks}
    # A fresh container receives final files, never evaluator code or hidden cases on disk.
    with Sandbox(image, files) as sandbox:
        offenses = sandbox.call("check")["offenses"]
        checks.append(check("theme_check", not any(x["severity"] == 0 for x in offenses), offenses))
        task_checks = evaluate(task, files, sandbox)
        if not task_checks or any(type(x.get("passed")) is not bool for x in task_checks):
            raise ValueError("Evaluator must return nonempty named boolean checks")
        checks.extend(task_checks)
    if len({c["name"] for c in checks}) != len(checks):
        raise ValueError("Evaluator check names must be unique")
    return {"passed": all(c["passed"] for c in checks), "checks": checks}


def validation_candidates(task):
    """Apply declarative mutations to reference files; never execute fixture code."""
    result = {
        "starter": (dict(task.initial), False),
        "reference": (dict(task.reference_files), True),
    }
    for candidate in task.validation:
        files = dict(task.reference_files)
        for name, content in candidate["changes"].items():
            if content is None:
                files.pop(name, None)
            else:
                files[name] = content
        result[candidate["name"]] = files, candidate["expected_pass"]
    return result
