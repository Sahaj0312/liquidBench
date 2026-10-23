from collections import Counter
import copy
import json
from pathlib import Path

import pytest

from liquidbench.runner import load_config
from liquidbench.skills import sha256
from liquidbench.study import CONDITIONS, build_plan, execute_block, verify_counts
from liquidbench.task import discover_tasks, fingerprint

ROOT = Path(__file__).resolve().parents[1]


def setup_plan(tmp_path, skill_spec):
    base = load_config(ROOT / "configs/qwen-ab-base.json")
    neutral = tmp_path / "notes.txt"
    neutral.write_text("Neutral records only.")
    configs = {
        "base": base,
        "full": {**base, "skills": skill_spec},
        "on_demand": {**base, "skills": skill_spec, "skill_loading": "on_demand"},
        "neutral": {
            **base,
            "neutral_context": {"path": str(neutral), "sha256": sha256(neutral.read_bytes())},
        },
    }
    tasks = discover_tasks(ROOT / "tasks/dev")
    return build_plan(configs, tasks), tasks


def test_fixed_schedule_balanced_complete_deterministic(tmp_path, skill_spec):
    plan, tasks = setup_plan(tmp_path, skill_spec)
    assert plan == build_plan(plan["configs"], list(reversed(tasks)))
    assert len(plan["order"]) == 240
    pairs = Counter((r["repetition"], r["task_id"], r["condition"]) for r in plan["order"])
    assert len(pairs) == 240 and set(pairs.values()) == {1}
    assert {r["seed"] for r in plan["order"]} == {42}
    for repetition in range(1, 4):
        positions = Counter(
            (r["condition"], r["position"]) for r in plan["order"] if r["repetition"] == repetition
        )
        assert set(positions.values()) == {5}
    for block in range(15):
        selected = [r for r in plan["order"] if r["block"] == block]
        assert len(selected) == 16
        assert len({r["task_id"] for r in selected}) == 4
        assert Counter(r["condition"] for r in selected) == dict.fromkeys(CONDITIONS, 4)


@pytest.mark.parametrize("change", ["budget", "missing", "wrong_policy", "wrong_bundle", "leak"])
def test_uncontrolled_conditions_rejected(tmp_path, skill_spec, change):
    plan, tasks = setup_plan(tmp_path, skill_spec)
    configs = copy.deepcopy(plan["configs"])
    if change == "budget":
        configs["on_demand"]["max_turns"] += 1
    elif change == "missing":
        del configs["neutral"]
    elif change == "wrong_policy":
        configs["full"]["skill_loading"] = "on_demand"
    elif change == "wrong_bundle":
        configs["on_demand"]["skills"]["revision"] = "0" * 40
    else:
        configs["base"]["skills"] = skill_spec
    with pytest.raises(ValueError):
        build_plan(configs, tasks)


def test_stale_report_or_mismatched_endpoint_counts_block(tmp_path, skill_spec):
    plan, tasks = setup_plan(tmp_path, skill_spec)
    report = {
        "plan_sha256": fingerprint(plan),
        "tasks": {
            t.manifest["id"]: {c: {"initial_tokens": 100} for c in CONDITIONS} for t in tasks
        },
    }

    class Provider:
        def count_prompt(self, messages, timeout):
            return 100

    assert len(verify_counts(plan, tasks, report, Provider())) == 80
    report["tasks"][tasks[0].manifest["id"]]["neutral"]["initial_tokens"] = 99
    with pytest.raises(ValueError, match="count mismatch"):
        verify_counts(plan, tasks, report, Provider())
    report["plan_sha256"] = "stale"
    with pytest.raises(ValueError, match="Stale"):
        verify_counts(plan, tasks, report, Provider())


@pytest.mark.parametrize("infrastructure", [False, True])
def test_block_keeps_failures_no_replacement_or_overwrite(tmp_path, skill_spec, infrastructure):
    plan, tasks = setup_plan(tmp_path, skill_spec)
    seen = []

    def runner(task, config, output):
        seen.append(task.manifest["id"])
        return output / "artifact", {
            "status": "infrastructure_error" if infrastructure else "failed",
            "termination": "infrastructure_error" if infrastructure else "turn_budget",
        }

    directory = tmp_path / "block"
    code = execute_block(
        plan, tasks, 0, directory, runner=runner, resolve_image=lambda _: plan["runtime_image_id"]
    )
    assert code == (2 if infrastructure else 1)
    assert len(seen) == (1 if infrastructure else 16)
    summary = json.loads((directory / "summary.json").read_text())
    assert summary["complete"] is (not infrastructure)
    assert len(summary["planned"]) == 16 and len(summary["runs"]) == len(seen)
    with pytest.raises(FileExistsError):
        execute_block(plan, tasks, 0, directory, runner=runner)


def test_runtime_mismatch_blocks_before_model(tmp_path, skill_spec):
    plan, tasks = setup_plan(tmp_path, skill_spec)
    with pytest.raises(ValueError, match="Runtime image"):
        execute_block(
            plan,
            tasks,
            0,
            tmp_path / "block",
            runner=lambda *a: pytest.fail("No model"),
            resolve_image=lambda _: "wrong",
        )


def test_relative_output_preserves_absolute_runner_artifacts(tmp_path, skill_spec, monkeypatch):
    plan, tasks = setup_plan(tmp_path, skill_spec)
    monkeypatch.chdir(tmp_path)

    def runner(task, config, output):
        return output.resolve() / "artifact", {"status": "failed", "termination": "turn_budget"}

    assert (
        execute_block(
            plan,
            tasks,
            0,
            Path("relative"),
            runner=runner,
            resolve_image=lambda _: plan["runtime_image_id"],
        )
        == 1
    )
    summary = json.loads(Path("relative/summary.json").read_text())
    assert summary["runs"][0]["artifacts"] == "base/artifact"
