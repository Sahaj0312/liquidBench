"""Predeclared four-condition development study; no provisioning or prompt tuning."""

import json
from pathlib import Path

from .runner import SYSTEM, run
from .sandbox import image_id
from .skills import SkillBundle, initial_messages, load_neutral, sha256, validate_loading
from .task import fingerprint

CONDITIONS = ("base", "full", "on_demand", "neutral")
TREATMENT_KEYS = {"skills", "skill_loading", "neutral_context"}
REPETITIONS = 3
RUNTIME_IMAGE = "sha256:ffd88aa28203d5582a880a59727f5e4700f1bf225387a381b60cb60bbadc9638"


def messages(config, prompt, bundle=None):
    return initial_messages(
        SYSTEM,
        prompt,
        bundle,
        loading=config.get("skill_loading", "full"),
        neutral=load_neutral(config),
    )


def build_plan(configs, tasks):
    if set(configs) != set(CONDITIONS):
        raise ValueError("Exactly four declared conditions are required")
    common = {k: v for k, v in configs["base"].items() if k not in TREATMENT_KEYS}
    for config in configs.values():
        validate_loading(config)
        if {k: v for k, v in config.items() if k not in TREATMENT_KEYS} != common:
            raise ValueError("Conditions must share all non-treatment settings")
    if (
        configs["base"].get("skills") is not None
        or configs["base"].get("neutral_context") is not None
        or configs["full"].get("skills") is None
        or configs["full"].get("skill_loading", "full") != "full"
        or configs["on_demand"].get("skill_loading") != "on_demand"
        or configs["on_demand"].get("skills") != configs["full"]["skills"]
        or configs["neutral"].get("skills") is not None
        or configs["neutral"].get("neutral_context") is None
    ):
        raise ValueError("Condition exposure policy mismatch")
    neutral = load_neutral(configs["neutral"])
    bundle = SkillBundle.load(configs["full"]["skills"])
    tasks = sorted(tasks, key=lambda t: t.manifest["id"])
    if len(tasks) != 20 or len({t.manifest["id"] for t in tasks}) != 20:
        raise ValueError("Study requires exactly 20 unique development tasks")
    order = []
    for repetition in range(REPETITIONS):
        offset = (7 * repetition) % len(tasks)
        rotated = tasks[offset:] + tasks[:offset]
        for index, task in enumerate(rotated):
            shift = (index + repetition) % len(CONDITIONS)
            for position, condition in enumerate(CONDITIONS[shift:] + CONDITIONS[:shift]):
                order.append(
                    {
                        "repetition": repetition + 1,
                        "seed": common["seed"],
                        "block": repetition * 5 + index // 4,
                        "task_id": task.manifest["id"],
                        "task_digest": task.digest,
                        "condition": condition,
                        "position": position,
                    }
                )
    source = Path(__file__).parent
    return {
        "schema_version": 1,
        "development_only": True,
        "research_result": False,
        "repetition_policy": "3 fixed-seed repeats; deterministic reproducibility checks, not independent samples",
        "system_sha256": sha256(SYSTEM.encode()),
        "python_source_digest": fingerprint(
            {str(p.relative_to(source)): p.read_text() for p in sorted(source.rglob("*.py"))}
        ),
        "runtime_image_id": RUNTIME_IMAGE,
        "skills": bundle.metadata(),
        "index_sha256": sha256(bundle.index_message().encode()),
        "neutral_sha256": sha256(neutral.encode()),
        "configs": configs,
        "order": order,
    }


def measure_plan(plan, tasks, count):
    bundles = {
        c: SkillBundle.load(cfg["skills"]) if cfg.get("skills") else None
        for c, cfg in plan["configs"].items()
    }
    rows = {}
    for task in tasks:
        row = {}
        for condition, config in plan["configs"].items():
            history = messages(config, task.manifest["prompt"], bundles[condition])
            initial = count(history)
            if initial + config["max_output_tokens"] + 32 > config["max_context_tokens"]:
                raise ValueError("Initial context does not fit")
            after_reads = {}
            if bundles[condition] is not None:
                for path in sorted(bundles[condition].documents):
                    action = {"tool": "read_file", "args": {"path": path}}
                    response = {
                        "ok": True,
                        "tool": "read_file",
                        "result": bundles[condition].read(path),
                    }
                    after_reads[path] = count(
                        history
                        + [
                            {"role": "assistant", "content": json.dumps(action)},
                            {
                                "role": "user",
                                "content": "Tool result: "
                                + json.dumps(response, ensure_ascii=False),
                            },
                        ]
                    )
            row[condition] = {"initial_tokens": initial, "after_single_read": after_reads}
        if row["neutral"]["initial_tokens"] != row["full"]["initial_tokens"]:
            raise ValueError("Neutral/full initial token counts must match exactly")
        rows[task.manifest["id"]] = row
    return {"plan_sha256": fingerprint(plan), "inference_performed": False, "tasks": rows}


def verify_counts(plan, tasks, feasibility, provider):
    if feasibility["plan_sha256"] != fingerprint(plan):
        raise ValueError("Stale feasibility report")
    bundles = {
        c: SkillBundle.load(cfg["skills"]) if cfg.get("skills") else None
        for c, cfg in plan["configs"].items()
    }
    checks = []
    for task in tasks:
        for condition, config in plan["configs"].items():
            expected = feasibility["tasks"][task.manifest["id"]][condition]["initial_tokens"]
            actual = provider.count_prompt(
                messages(config, task.manifest["prompt"], bundles[condition]),
                config["request_timeout"],
            )
            checks.append(
                {
                    "task": task.manifest["id"],
                    "condition": condition,
                    "local": expected,
                    "endpoint": actual,
                }
            )
            if actual != expected:
                raise ValueError(f"Local/server count mismatch: {checks[-1]}")
    return checks


def execute_block(plan, tasks, block, directory, *, runner=run, resolve_image=image_id):
    if type(block) is not int or block not in range(15):
        raise ValueError("Block must be 0..14")
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    selected = [item for item in plan["order"] if item["block"] == block]
    summary = {
        "block": block,
        "plan_sha256": fingerprint(plan),
        "planned": selected,
        "runs": [],
        "complete": False,
    }
    summary_path = directory / "summary.json"

    def save():
        summary_path.write_text(json.dumps(summary, indent=2) + "\n")

    save()
    image = resolve_image(plan["configs"]["base"]["image"])
    if image != plan["runtime_image_id"]:
        raise ValueError("Runtime image differs from frozen plan")
    by_id = {t.manifest["id"]: t for t in tasks}
    for item in selected:
        config = {**plan["configs"][item["condition"]], "image": image}
        destination, result = runner(by_id[item["task_id"]], config, directory / item["condition"])
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
            f"{item['repetition']}/{item['task_id']}/{item['condition']}: {result['status']}",
            flush=True,
        )
        if result["status"] == "infrastructure_error":
            return 2
    summary["complete"] = True
    save()
    return int(any(r["status"] == "failed" for r in summary["runs"]))
