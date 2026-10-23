"""Explicit allowlist of trusted evaluators, never imports from task data."""

from .product_card import evaluate as product_card

from .shipping_message import evaluate as shipping_message
from .section_schema import evaluate as section_schema
from .asset_references import evaluate as asset_references
from .announcement_subtitle import evaluate as announcement_subtitle

EVALUATORS = {
    "product-card-v1": product_card,
    "shipping-message-v1": shipping_message,
    "section-schema-v1": section_schema,
    "asset-references-v1": asset_references,
    "announcement-subtitle-v1": announcement_subtitle,
}


def get_evaluator(name):
    try:
        return EVALUATORS[name]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"Unknown evaluator: {name!r}") from exc
