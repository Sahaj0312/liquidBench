"""Explicit allowlist of trusted evaluators, never imports from task data."""

from .product_card import evaluate as product_card

EVALUATORS = {"product-card-v1": product_card}


def get_evaluator(name):
    try:
        return EVALUATORS[name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Unknown evaluator: {name!r}") from exc
