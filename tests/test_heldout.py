import json
from pathlib import Path

import pytest

from liquidbench.heldout import assert_not_heldout, verify_frozen
from liquidbench.task import discover_tasks

ROOT = Path(__file__).resolve().parents[1]


def test_heldout_matches_frozen_manifest_and_is_disjoint_from_dev():
    tasks = verify_frozen()
    assert len(tasks) == 24 and {t.manifest["split"] for t in tasks} == {"heldout"}
    dev = {t.manifest["family"] for t in discover_tasks(ROOT / "tasks/dev")}
    assert not dev & {t.manifest["family"] for t in tasks}


def test_edited_heldout_task_is_rejected(tmp_path):
    import shutil

    shutil.copytree(ROOT / "tasks/heldout", tmp_path / "heldout")
    path = tmp_path / "heldout/size-label/task.json"
    manifest = json.loads(path.read_text())
    manifest["prompt"] += " Easier now."
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="frozen manifest"):
        verify_frozen(tmp_path / "heldout")


def test_leak_guard_flags_heldout_family_or_prompt():
    task = discover_tasks(ROOT / "tasks/heldout")[0]
    with pytest.raises(ValueError, match="leaked"):
        assert_not_heldout("Write a task like " + task.manifest["family"])
    with pytest.raises(ValueError, match="leaked"):
        assert_not_heldout(task.manifest["prompt"])
    assert_not_heldout("Repair snippets/newsletter-form.liquid so the label is escaped.")


def test_extension_themes_are_disjoint_from_training_themes():
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from generate_training_tasks import THEMES
    from heldout_themes import HELDOUT_THEMES

    generic = {"section", "labels", "list", "label", "script", "page", "block", "notice"}

    def words(theme):
        return set(theme.lower().replace("-", " ").split()) - generic

    training = [words(t) for themes in THEMES.values() for t in themes]
    for themes in HELDOUT_THEMES.values():
        for theme in themes:
            # One shared domain word ("product", "order") is fine; two means the same feature.
            assert not any(len(words(theme) & t) >= 2 for t in training), theme
