"""Held-out isolation: final-model evaluation only, frozen by digest."""

import json
from pathlib import Path

from .task import discover_tasks, fingerprint

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "docs/heldout/manifest.json"
HELDOUT = ROOT / "tasks/heldout"


def verify_frozen(root=HELDOUT, manifest=MANIFEST):
    """Load held-out tasks only if they exactly match the frozen manifest."""
    frozen = json.loads(Path(manifest).read_text())
    tasks = discover_tasks(Path(root))
    actual = {t.manifest["id"]: t.digest for t in tasks}
    if actual != {k: v["digest"] for k, v in frozen["tasks"].items()}:
        raise ValueError("Held-out tasks differ from the frozen manifest")
    if fingerprint(frozen["tasks"]) != frozen["suite_digest"]:
        raise ValueError("Held-out manifest digest mismatch")
    return tasks


def assert_not_heldout(text, root=HELDOUT):
    """Reject training/generation material that names a held-out family or prompt."""
    for task in discover_tasks(Path(root)):
        family, prompt = task.manifest["family"], task.manifest["prompt"]
        if family in text or prompt[:80] in text:
            raise ValueError(f"Held-out material leaked: {family}")
