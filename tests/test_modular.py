from dataclasses import replace
import json
from pathlib import Path
import shutil

import pytest

from liquidbench.evaluators import EVALUATORS
from liquidbench.evaluators.common import same_json, strict_json
from liquidbench.grading import grade, validation_candidates
from liquidbench.task import Task, discover_tasks

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def task():
    return Task.load(ROOT / "tasks/dev/product-card")


class GradingSandbox:
    def __init__(self, image, files):
        self.files = files

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def call(self, tool, args=None):
        assert tool == "check"
        return {"offenses": []}


def test_registry_dispatch_does_not_depend_on_task_id(task, monkeypatch):
    called = []

    def evaluator(task, files, sandbox):
        called.append(task.manifest["id"])
        return [{"name": "custom", "passed": False}]

    monkeypatch.setitem(EVALUATORS, "test-only", evaluator)
    monkeypatch.setattr("liquidbench.grading.Sandbox", GradingSandbox)
    custom = replace(
        task, manifest={**task.manifest, "id": "new-task-id", "evaluator": "test-only"}
    )
    result = grade(custom, task.reference_files, "fake-image")
    assert called == ["new-task-id"]
    assert result["passed"] is False
    assert [c["name"] for c in result["checks"]] == [
        "edit_scope",
        "no_suppressions",
        "theme_check",
        "custom",
    ]


@pytest.mark.parametrize(
    "checks", [[], [{"name": "bad", "passed": "yes"}], [{"name": "edit_scope", "passed": True}]]
)
def test_bad_evaluator_contract_cannot_pass(task, monkeypatch, checks):
    monkeypatch.setitem(EVALUATORS, "test-only", lambda *a: checks)
    monkeypatch.setattr("liquidbench.grading.Sandbox", GradingSandbox)
    custom = replace(task, manifest={**task.manifest, "evaluator": "test-only"})
    with pytest.raises(ValueError):
        grade(custom, task.reference_files, "fake-image")


def test_integrity_gates_run_before_evaluator(task, monkeypatch):
    def forbidden(*args):
        pytest.fail("Sandbox/evaluator must not run after an integrity violation")

    monkeypatch.setattr("liquidbench.grading.Sandbox", forbidden)
    for files in [
        {**task.reference_files, ".theme-check.yml": "extends: []"},
        {**task.reference_files, "snippets/product-card.liquid": "{% # theme-check-disable %}"},
        {},
    ]:
        assert grade(task, files, "fake-image")["passed"] is False


def test_twenty_development_tasks_have_independent_contracts():
    tasks = discover_tasks(ROOT / "tasks/dev")
    assert {t.manifest["id"] for t in tasks} >= {
        "product-card",
        "shipping-message",
        "section-schema",
        "asset-references",
        "announcement-subtitle",
    }
    assert len(tasks) == len({t.manifest["family"] for t in tasks}) == 20
    for task in tasks:
        assert task.manifest["split"] == "development"
        candidates = validation_candidates(task)
        assert candidates["starter"] == (task.initial, False)
        assert candidates["reference"] == (task.reference_files, True)
        assert sum(not expected for _, expected in candidates.values()) >= 3
        assert task.initial != task.reference_files
        assert all(not p.startswith("evaluator/") for p in task.initial)


def copied_task(tmp_path):
    destination = tmp_path / "task"
    shutil.copytree(ROOT / "tasks/dev/product-card", destination)
    return destination


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("evaluator", "os.system", "Unknown evaluator"),
        ("split", "held-out", "development"),
        ("editable_files", ["../secret"], "Invalid editable"),
        ("editable_files", ["missing.liquid"], "must exist"),
    ],
)
def test_reject_invalid_manifest_before_execution(tmp_path, field, value, match):
    root = copied_task(tmp_path)
    p = root / "task.json"
    manifest = json.loads(p.read_text())
    manifest[field] = value
    p.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match=match):
        Task.load(root)


def test_reject_reference_symlink_and_out_of_scope_reference(tmp_path):
    root = copied_task(tmp_path)
    p = root / "evaluator/reference/leak"
    p.symlink_to(root / "task.json")
    with pytest.raises(ValueError, match="symlink"):
        Task.load(root)
    p.unlink()
    p.write_text("not an editable file")
    with pytest.raises(ValueError, match="only editable"):
        Task.load(root)


def test_reject_duplicate_validation_names_and_paths(tmp_path):
    root = copied_task(tmp_path)
    p = root / "evaluator/validation.json"
    candidates = json.loads(p.read_text())
    candidates[1]["name"] = candidates[0]["name"]
    p.write_text(json.dumps(candidates))
    with pytest.raises(ValueError, match="duplicate"):
        Task.load(root)
    candidates[1]["name"] = "restored"
    candidates[1]["changes"] = {"../outside": "bad"}
    p.write_text(json.dumps(candidates))
    with pytest.raises(ValueError, match="safe paths"):
        Task.load(root)


def test_digest_includes_evaluator_cases_reference_and_mutants(task):
    assert replace(task, validation=[]).digest != task.digest
    assert replace(task, cases=[]).digest != task.digest
    assert replace(task, reference_files={}).digest != task.digest
    manifest = {**task.manifest, "evaluator": "different-version"}
    assert replace(task, manifest=manifest).digest != task.digest


@pytest.mark.parametrize("text", ['{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'])
def test_schema_json_rejects_ambiguous_values(text):
    with pytest.raises(ValueError):
        strict_json(text)


def test_schema_numeric_equality_does_not_accept_boolean():
    assert same_json({"columns": 2.0}, {"columns": 2})
    assert not same_json({"columns": True}, {"columns": 1})
    assert not same_json({"enabled": 1}, {"enabled": True})
