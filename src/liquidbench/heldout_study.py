"""Predeclared four-arm held-out evaluation: {base, fine-tuned} x {plain, on-demand skills}.

The arms differ only in the served model and in skill exposure. The base pair runs
first on the pinned base server; the fine-tuned pair then runs on the merged
adapter, with the same serving command apart from the model path. Every attempt
runs once in plan order, with no retries, replacements or resumes.
"""

import json
from pathlib import Path

from .runner import SYSTEM, run
from .sandbox import image_id
from .skills import SkillBundle, initial_messages, sha256, validate_loading
from .task import fingerprint

ARMS = ("base", "base_skills", "tuned", "tuned_skills")
PHASES = {"base": ("base", "base_skills"), "tuned": ("tuned", "tuned_skills")}
TREATMENT_KEYS = {"model", "model_revision", "skills", "skill_loading", "purpose"}
RUNTIME_IMAGE = "sha256:ffd88aa28203d5582a880a59727f5e4700f1bf225387a381b60cb60bbadc9638"


def messages(config, prompt):
    bundle = SkillBundle.load(config["skills"]) if config.get("skills") else None
    loading = config.get("skill_loading", "full")
    return initial_messages(SYSTEM, prompt, bundle, loading=loading)


def build_plan(configs, suites, repetitions):
    """`suites` maps a suite name to its verified task list."""
    if set(configs) != set(ARMS):
        raise ValueError(f"Arms must be exactly {ARMS}")
    common = {k: v for k, v in configs["base"].items() if k not in TREATMENT_KEYS}
    for config in configs.values():
        validate_loading(config)
        if {k: v for k, v in config.items() if k not in TREATMENT_KEYS} != common:
            raise ValueError("Arms must share all non-treatment settings")
    for plain, skilled in (("base", "base_skills"), ("tuned", "tuned_skills")):
        if configs[plain].get("skills") is not None:
            raise ValueError(f"{plain} must not load skills")
        if configs[skilled].get("skill_loading") != "on_demand" or not configs[skilled].get(
            "skills"
        ):
            raise ValueError(f"{skilled} must load skills on demand")
        if configs[plain]["model"] != configs[skilled]["model"]:
            raise ValueError("A phase's two arms must use the same served model")
    if configs["base_skills"]["skills"] != configs["tuned_skills"]["skills"]:
        raise ValueError("Both skill arms must use the same skills revision")
    if configs["base"]["model"] == configs["tuned"]["model"]:
        raise ValueError("Base and tuned arms must serve different models")
    tasks = sorted(
        ((name, t) for name, ts in suites.items() for t in ts), key=lambda x: x[1].manifest["id"]
    )
    if len({t.manifest["id"] for _, t in tasks}) != len(tasks):
        raise ValueError("Task ids must be unique across suites")
    order = []
    for phase, arms in PHASES.items():
        for repetition in range(repetitions):
            offset = (11 * repetition) % len(tasks)
            rotated = tasks[offset:] + tasks[:offset]
            for index, (suite, task) in enumerate(rotated):
                pair = arms if (index + repetition) % 2 == 0 else arms[::-1]
                for position, arm in enumerate(pair):
                    order.append(
                        {
                            "phase": phase,
                            "repetition": repetition + 1,
                            "suite": suite,
                            "task_id": task.manifest["id"],
                            "task_digest": task.digest,
                            "arm": arm,
                            "position": position,
                        }
                    )
    source = Path(__file__).parent
    bundle = SkillBundle.load(configs["base_skills"]["skills"])
    return {
        "schema_version": 1,
        "heldout": True,
        "repetitions": repetitions,
        "repetition_policy": "fixed-seed repeats; reproducibility checks, not independent samples",
        "system_sha256": sha256(SYSTEM.encode()),
        "python_source_digest": fingerprint(
            {str(p.relative_to(source)): p.read_text() for p in sorted(source.rglob("*.py"))}
        ),
        "runtime_image_id": RUNTIME_IMAGE,
        "skills": bundle.metadata(),
        "suites": {name: len(ts) for name, ts in suites.items()},
        "configs": configs,
        "order": order,
    }


def initial_counts(plan, tasks, count):
    """Initial prompt token count of every (task, arm); each must leave room to act."""
    rows = {}
    for task in tasks:
        row = {}
        for arm, config in plan["configs"].items():
            tokens = count(messages(config, task.manifest["prompt"]))
            if tokens + config["max_output_tokens"] + 32 > config["max_context_tokens"]:
                raise ValueError(f"Initial context does not fit: {task.manifest['id']} {arm}")
            row[arm] = tokens
        rows[task.manifest["id"]] = row
    return {"plan_sha256": fingerprint(plan), "tasks": rows}


def verify_counts(plan, tasks, counts, phase, provider):
    """The live server must count every initial prompt of this phase exactly as frozen."""
    if counts["plan_sha256"] != fingerprint(plan):
        raise ValueError("Stale initial-count report")
    for task in tasks:
        for arm in PHASES[phase]:
            config = plan["configs"][arm]
            live = provider.count_prompt(
                messages(config, task.manifest["prompt"]), config["request_timeout"]
            )
            if live != counts["tasks"][task.manifest["id"]][arm]:
                raise ValueError(f"Server count mismatch: {task.manifest['id']} {arm} {live}")


def execute_phase(plan, tasks, phase, directory, *, runner=run, resolve_image=image_id):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    selected = [item for item in plan["order"] if item["phase"] == phase]
    summary = {"phase": phase, "plan_sha256": fingerprint(plan), "runs": [], "complete": False}
    path = directory / "summary.json"

    def save():
        path.write_text(json.dumps(summary, indent=2) + "\n")

    save()
    image = resolve_image(plan["configs"]["base"]["image"])
    if image != plan["runtime_image_id"]:
        raise ValueError("Runtime image differs from frozen plan")
    by_id = {t.manifest["id"]: t for t in tasks}
    for item in selected:
        task = by_id[item["task_id"]]
        if task.digest != item["task_digest"]:
            raise ValueError(f"Task changed after planning: {item['task_id']}")
        config = {**plan["configs"][item["arm"]], "image": image}
        destination, result = runner(task, config, directory / item["arm"])
        summary["runs"].append(
            {
                **item,
                "artifacts": str(destination.relative_to(directory)),
                "status": result["status"],
                "termination": result["termination"],
            }
        )
        save()
        print(
            f"{item['repetition']}/{item['task_id']}/{item['arm']}: {result['status']}", flush=True
        )
        if result["status"] == "infrastructure_error":
            return 2
    summary["complete"] = True
    save()
    return 0
