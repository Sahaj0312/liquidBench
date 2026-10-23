"""Small shared grading helpers; no task-specific dispatch."""


def check(name, passed, detail=None):
    return {"name": name, "passed": bool(passed), "detail": detail}
