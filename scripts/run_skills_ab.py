"""Plan by default. --execute requires an approved endpoint and successful preflight.

No compute provisioning, automatic task reruns, or hidden-case prompt construction.
"""

import argparse
import json
from pathlib import Path

from liquidbench.preflight import validate_report
from liquidbench.provider import ChatProvider
from liquidbench.runner import SYSTEM, load_config, run
from liquidbench.sandbox import image_id
from liquidbench.skills import SkillBundle, initial_messages, sha256
from liquidbench.task import discover_tasks


def plan(base, treatment, tasks):
    if base.get("skills") is not None or treatment.get("skills") is None:
        raise ValueError("Expected a baseline without skills and a treatment with skills")
    if {k: v for k, v in base.items() if k != "skills"} != {
        k: v for k, v in treatment.items() if k != "skills"
    }:
        raise ValueError("Paired configurations must differ only in skills")
    bundle = SkillBundle.load(treatment["skills"])
    order = []
    for index, task in enumerate(tasks):
        for condition in ("base", "skills") if index % 2 == 0 else ("skills", "base"):
            order.append(
                {"task_id": task.manifest["id"], "condition": condition, "task_digest": task.digest}
            )
    return {
        "development_only": True,
        "research_result": False,
        "system_sha256": sha256(SYSTEM.encode()),
        "skills": bundle.metadata(),
        "configs": {"base": base, "skills": treatment},
        "order": order,
    }


def execute(plan_data, tasks, directory, *, runner=run, resolve_image=image_id):
    directory.mkdir(parents=True, exist_ok=False)
    (directory / "plan.json").write_text(json.dumps(plan_data, indent=2) + "\n")
    configs = plan_data["configs"]
    image = resolve_image(configs["base"]["image"])
    summaries = {
        condition: {
            "split": "development",
            "research_result": False,
            "runs": [],
            "status_counts": {"passed": 0, "failed": 0, "infrastructure_error": 0},
        }
        for condition in configs
    }
    by_id = {task.manifest["id"]: task for task in tasks}
    for condition in configs:
        (directory / condition).mkdir()
    for item in plan_data["order"]:
        condition = item["condition"]
        destination, result = runner(
            by_id[item["task_id"]], {**configs[condition], "image": image}, directory / condition
        )
        summary = summaries[condition]
        summary["runs"].append(
            {
                "task_id": item["task_id"],
                "status": result["status"],
                "termination": result["termination"],
                "artifacts": destination.name,
            }
        )
        summary["status_counts"][result["status"]] += 1
        for label, data in summaries.items():
            (directory / label / "summary.json").write_text(json.dumps(data, indent=2) + "\n")
        print(f"{condition}/{item['task_id']}: {result['status']}", flush=True)
        if result["status"] == "infrastructure_error":
            # Preserve missing pairs; never silently replace or continue a broken deployment.
            return 2
    return int(any(s["status_counts"]["failed"] for s in summaries.values()))


def verify_counts(plan_data, tasks, feasibility, provider):
    bundle = SkillBundle.load(plan_data["configs"]["skills"]["skills"])
    if feasibility["system_sha256"] != plan_data["system_sha256"] or (
        feasibility["skill_manifest_sha256"] != bundle.manifest_sha256
    ):
        raise ValueError("Feasibility report is stale")
    checks = []
    for task in tasks:
        for condition in ("base", "skills"):
            messages = initial_messages(
                SYSTEM, task.manifest["prompt"], bundle if condition == "skills" else None
            )
            predicted = feasibility["tasks"][task.manifest["id"]][
                "baseline_initial_prompt_tokens"
                if condition == "base"
                else "skills_initial_prompt_tokens"
            ]
            actual = provider.count_prompt(messages, 90)
            checks.append(
                {
                    "task": task.manifest["id"],
                    "condition": condition,
                    "local": predicted,
                    "endpoint": actual,
                }
            )
            if predicted != actual:
                raise ValueError(f"Local/server count mismatch: {checks[-1]}")
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--preflight", type=Path)
    parser.add_argument("--output", type=Path, default=Path("runs/skills-ab-01"))
    args = parser.parse_args()
    tasks = discover_tasks(Path("tasks/dev"))
    data = plan(
        load_config("configs/qwen-ab-base.json"), load_config("configs/qwen-ab-skills.json"), tasks
    )
    if not args.execute:
        print(json.dumps(data, indent=2))
        return 0
    if args.output.exists():
        raise ValueError("Output exists; refusing to overwrite or resume a paired experiment")
    if args.preflight is None:
        raise ValueError("--execute requires --preflight report.json")
    preflight = json.loads(args.preflight.read_text())
    validate_report(preflight, data["configs"]["base"])
    feasibility = json.loads(Path("docs/calibration/skills-feasibility.json").read_text())
    data["endpoint_count_checks"] = verify_counts(
        data, tasks, feasibility, ChatProvider(data["configs"]["base"])
    )
    data["preflight_sha256"] = sha256(args.preflight.read_bytes())
    return execute(data, tasks, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
