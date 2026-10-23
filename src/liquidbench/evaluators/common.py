"""Small shared grading helpers; no task-specific dispatch."""


def check(name, passed, detail=None):
    return {"name": name, "passed": bool(passed), "detail": detail}


def strict_json(text):
    import json

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")

    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def same_json(actual, expected):
    """JSON numbers may be integral floats, but booleans are never numbers."""
    if isinstance(expected, bool):
        return type(actual) is bool and actual == expected
    if isinstance(expected, (int, float)):
        return type(actual) in (int, float) and actual == expected
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and actual.keys() == expected.keys()
            and all(same_json(actual[k], v) for k, v in expected.items())
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(same_json(a, b) for a, b in zip(actual, expected))
        )
    return type(actual) is type(expected) and actual == expected


def walk_nodes(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_nodes(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_nodes(value)
