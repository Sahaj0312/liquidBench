import json
from pathlib import Path
import runpy

import pytest

from liquidbench.runner import load_config
from liquidbench.task import discover_tasks

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = runpy.run_path(str(ROOT / "scripts/run_skills_ab.py"))


def paired(skill_spec):
    base = load_config(ROOT / "configs/qwen-ab-base.json")
    treatment = {**base, "skills": skill_spec}
    tasks = [
        t for t in discover_tasks(ROOT / "tasks/dev") if t.manifest["id"] in SCRIPT["M5_TASK_IDS"]
    ]
    return SCRIPT["plan"](base, treatment, tasks), tasks


def test_paired_order_has_exactly_one_each_and_keeps_failures(skill_spec, tmp_path):
    data, tasks = paired(skill_spec)
    seen = []

    def runner(task, config, output):
        seen.append((task.manifest["id"], bool(config["skills"]), config["image"]))
        return output / "artifact", {"status": "failed", "termination": "turn_budget"}

    code = SCRIPT["execute"](
        data, tasks, tmp_path / "pair", runner=runner, resolve_image=lambda _: "pinned"
    )
    assert code == 1 and len(seen) == 10 and len(set(seen)) == 10
    assert [row[1] for row in seen] == [
        False,
        True,
        True,
        False,
        False,
        True,
        True,
        False,
        False,
        True,
    ]
    for condition in ("base", "skills"):
        summary = json.loads((tmp_path / "pair" / condition / "summary.json").read_text())
        assert summary["status_counts"]["failed"] == 5
    with pytest.raises(FileExistsError):
        SCRIPT["execute"](data, tasks, tmp_path / "pair", runner=runner)


def test_infrastructure_failure_stops_pair_without_replacement(skill_spec, tmp_path):
    data, tasks = paired(skill_spec)
    seen = []

    def runner(task, config, output):
        seen.append(task)
        return output / "artifact", {
            "status": "infrastructure_error",
            "termination": "infrastructure_error",
        }

    assert (
        SCRIPT["execute"](
            data, tasks, tmp_path / "pair", runner=runner, resolve_image=lambda _: "pinned"
        )
        == 2
    )
    assert len(seen) == 1
    summary = json.loads((tmp_path / "pair/skills/summary.json").read_text())
    assert summary["runs"] == []


def test_unequal_budgets_rejected(skill_spec):
    base = load_config(ROOT / "configs/qwen-ab-base.json")
    with pytest.raises(ValueError, match="differ only"):
        SCRIPT["plan"](base, {**base, "skills": skill_spec, "max_turns": 13}, [])


def test_stale_feasibility_and_server_count_mismatch_rejected(skill_spec):
    data, tasks = paired(skill_spec)
    feasibility = {
        "system_sha256": data["system_sha256"],
        "skill_manifest_sha256": data["skills"]["manifest_sha256"],
        "tasks": {
            t.manifest["id"]: {
                "baseline_initial_prompt_tokens": 100,
                "skills_initial_prompt_tokens": 200,
            }
            for t in tasks
        },
    }

    class Provider:
        def count_prompt(self, messages, timeout):
            return 100 if len(messages) == 2 else 200

    checks = SCRIPT["verify_counts"](data, tasks, feasibility, Provider())
    assert len(checks) == 10
    feasibility["tasks"][tasks[0].manifest["id"]]["skills_initial_prompt_tokens"] = 201
    with pytest.raises(ValueError, match="count mismatch"):
        SCRIPT["verify_counts"](data, tasks, feasibility, Provider())
    feasibility["system_sha256"] = "stale"
    with pytest.raises(ValueError, match="stale"):
        SCRIPT["verify_counts"](data, tasks, feasibility, Provider())
