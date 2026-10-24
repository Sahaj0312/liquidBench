from collections import Counter
import json
from pathlib import Path

import pytest

from liquidbench.heldout_study import (
    ARMS,
    PHASES,
    build_plan,
    execute_phase,
    initial_counts,
    verify_counts,
)
from liquidbench.runner import load_config
from liquidbench.task import discover_tasks

ROOT = Path(__file__).resolve().parents[1]


def arm_configs(skill_spec, **changes):
    base = load_config(ROOT / "configs/qwen-ab-base.json")
    tuned = {**base, "model": "liquidbench-lora-v1"}
    configs = {
        "base": base,
        "base_skills": {**base, "skills": skill_spec, "skill_loading": "on_demand"},
        "tuned": tuned,
        "tuned_skills": {**tuned, "skills": skill_spec, "skill_loading": "on_demand"},
    }
    for arm, update in changes.items():
        configs[arm] = {**configs[arm], **update}
    return configs


def suites():
    tasks = sorted(discover_tasks(ROOT / "tasks/dev"), key=lambda t: t.manifest["id"])
    return {"original": tasks[:8], "extension": tasks[8:]}


def test_plan_runs_every_task_once_per_arm_and_repetition_in_phase_order(skill_spec):
    plan = build_plan(arm_configs(skill_spec), suites(), repetitions=2)
    order = plan["order"]
    assert len(order) == 20 * 4 * 2
    assert (
        Counter((o["task_id"], o["arm"], o["repetition"]) for o in order).most_common(1)[0][1] == 1
    )
    phases = [o["phase"] for o in order]
    assert phases == sorted(phases, key=list(PHASES).index)
    for phase, arms in PHASES.items():
        assert {o["arm"] for o in order if o["phase"] == phase} == set(arms)
    # Each arm goes first equally often, so order effects cannot favor one arm.
    firsts = Counter(o["arm"] for o in order if o["position"] == 0)
    assert len(set(firsts.values())) == 1 and set(firsts) == set(ARMS)
    assert plan == build_plan(arm_configs(skill_spec), suites(), repetitions=2)


@pytest.mark.parametrize(
    "changes,match",
    [
        ({"tuned": {"temperature": 0.7}}, "share all non-treatment"),
        ({"base": {"skill_loading": "on_demand"}}, "requires a skill bundle|must not load"),
        ({"tuned_skills": {"skill_loading": "full"}}, "on demand"),
        ({"tuned": {"model": "Qwen/Qwen2.5-Coder-7B-Instruct"}}, "same served model|different"),
    ],
)
def test_uncontrolled_arms_are_rejected(skill_spec, changes, match):
    with pytest.raises(ValueError, match=match):
        build_plan(arm_configs(skill_spec, **changes), suites(), repetitions=2)


class FakeProvider:
    def __init__(self, shift=0):
        self.shift = shift

    def count_prompt(self, messages, timeout):
        return sum(len(m["content"]) for m in messages) + self.shift


def test_live_counts_must_match_the_frozen_counts(skill_spec):
    plan = build_plan(arm_configs(skill_spec), suites(), repetitions=1)
    tasks = [t for ts in suites().values() for t in ts]
    counts = initial_counts(plan, tasks, lambda m: sum(len(x["content"]) for x in m) // 100)
    exact = initial_counts(plan, tasks, lambda m: FakeProvider().count_prompt(m, 0))
    verify_counts(plan, tasks, exact, "base", FakeProvider())
    with pytest.raises(ValueError, match="mismatch"):
        verify_counts(plan, tasks, counts, "tuned", FakeProvider())
    with pytest.raises(ValueError, match="Stale"):
        verify_counts({**plan, "repetitions": 9}, tasks, exact, "base", FakeProvider())


def test_phase_runs_in_order_without_retries_and_stops_on_infrastructure(tmp_path, skill_spec):
    plan = build_plan(arm_configs(skill_spec), suites(), repetitions=1)
    tasks = [t for ts in suites().values() for t in ts]
    seen = []

    def runner(task, config, output):
        seen.append((task.manifest["id"], config["model"]))
        status = "infrastructure_error" if len(seen) == 5 else "failed"
        return output / f"run-{len(seen)}", {"status": status, "termination": "finished"}

    code = execute_phase(
        plan,
        tasks,
        "tuned",
        tmp_path / "t",
        runner=runner,
        resolve_image=lambda _: plan["runtime_image_id"],
    )
    assert code == 2 and len(seen) == 5
    assert {m for _, m in seen} == {"liquidbench-lora-v1"}
    planned = [o["task_id"] for o in plan["order"] if o["phase"] == "tuned"][:5]
    assert [t for t, _ in seen] == planned
    summary = json.loads((tmp_path / "t/summary.json").read_text())
    assert summary["complete"] is False and len(summary["runs"]) == 5
    with pytest.raises(FileExistsError):
        execute_phase(plan, tasks, "tuned", tmp_path / "t", runner=runner)
