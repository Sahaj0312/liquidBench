from dataclasses import replace
import json
from pathlib import Path

import pytest

from liquidbench import cli
from liquidbench.runner import load_config, run
from liquidbench.task import discover_tasks
from test_runner import MemorySandbox, ScriptedProvider

ROOT = Path(__file__).resolve().parents[1]
TASKS = discover_tasks(ROOT / "tasks/dev")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.manifest["id"])
def test_runner_never_exposes_hidden_evaluation_assets(task, tmp_path):
    canary = "PRIVATE_EVALUATION_CANARY_6472"
    task = replace(
        task,
        cases=[{"id": canary}],
        validation=[{"secret": canary}],
        reference_files={p: canary for p in task.initial},
    )
    received = []

    def sandbox_factory(image, initial):
        received.append(dict(initial))
        return MemorySandbox(image, initial)

    provider = ScriptedProvider(['{"tool":"finish","args":{}}'])
    _, result = run(
        task,
        load_config(ROOT / "configs/local-smoke.json"),
        tmp_path,
        provider=provider,
        sandbox_factory=sandbox_factory,
        resolve_image=lambda _: "sha256:test",
        grader=lambda *a: {"passed": False},
    )
    assert canary not in "".join(provider.contexts)
    assert canary not in json.dumps(received)
    assert received == [task.initial]
    assert result["status"] == "failed"


def test_suite_retains_model_failures_and_missing_infrastructure(tmp_path, monkeypatch):
    statuses = iter(
        ["failed", "infrastructure_error", "passed", "passed", "failed"]
        + ["failed"] * (len(TASKS) - 5)
    )
    seen = []
    monkeypatch.setattr(cli, "image_id", lambda _: "sha256:fixed")

    def fake_run(task, config, directory):
        assert config["image"] == "sha256:fixed"
        seen.append(task.manifest["id"])
        return directory / task.manifest["id"], {"status": next(statuses), "termination": "test"}

    monkeypatch.setattr(cli, "run", fake_run)
    code = cli.run_suite(TASKS, load_config(ROOT / "configs/local-smoke.json"), tmp_path)
    summary = json.loads(next(tmp_path.glob("suite-*/summary.json")).read_text())
    assert code == 2
    assert seen == [t.manifest["id"] for t in TASKS]
    assert summary["status_counts"] == {
        "passed": 2,
        "failed": len(TASKS) - 3,
        "infrastructure_error": 1,
    }
    assert summary["split"] == "development"
    assert summary["research_result"] is False
