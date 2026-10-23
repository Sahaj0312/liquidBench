import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from .grading import grade, validation_candidates
from .runner import load_config, run
from .sandbox import InfrastructureError, docker, image_id
from .task import Task, discover_tasks


def validate(task, image):
    outcomes = []
    for name, (files, expected) in validation_candidates(task).items():
        result = grade(task, files, image)
        outcomes.append(
            {
                "candidate": name,
                "expected_pass": expected,
                "correct_verdict": result["passed"] == expected,
                "grade": result,
            }
        )
        print(
            f"{task.manifest['id']}/{name}: {'PASS' if result['passed'] else 'FAIL'} "
            f"(expected {'PASS' if expected else 'FAIL'})",
            flush=True,
        )
    return {
        "task_id": task.manifest["id"],
        "task_digest": task.digest,
        "image_id": image,
        "outcomes": outcomes,
        "valid": all(item["correct_verdict"] for item in outcomes),
    }


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def run_suite(tasks, config, output):
    """One development attempt per task; retains failures and missing infrastructure runs."""
    name = "suite-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    directory = output.resolve() / name
    directory.mkdir(parents=True, exist_ok=False)
    # All attempts in this suite use the same immutable runtime image.
    config = {**config, "image": image_id(config["image"])}
    summary = {
        "split": "development",
        "research_result": False,
        "runs": [],
        "status_counts": {"passed": 0, "failed": 0, "infrastructure_error": 0},
    }
    for task in tasks:
        destination, result = run(task, config, directory)
        summary["runs"].append(
            {
                "task_id": task.manifest["id"],
                "status": result["status"],
                "termination": result["termination"],
                "artifacts": destination.name,
            }
        )
        summary["status_counts"][result["status"]] += 1
        save_json(directory / "summary.json", summary)
        print(f"{task.manifest['id']}: {result['status']} ({result['termination']})", flush=True)
    print(
        json.dumps(
            {"summary": str(directory / "summary.json"), **summary["status_counts"]}, indent=2
        )
    )
    return (
        2
        if summary["status_counts"]["infrastructure_error"]
        else int(bool(summary["status_counts"]["failed"]))
    )


def main():
    parser = argparse.ArgumentParser(prog="liquidbench")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("build-image")
    for name in ("validate-task", "validate-suite", "run", "run-suite"):
        command = commands.add_parser(name)
        if name.endswith("suite"):
            command.add_argument("--tasks-root", type=Path, default=Path("tasks/dev"))
        else:
            command.add_argument("--task", type=Path, default=Path("tasks/dev/product-card"))
        if name.startswith("validate"):
            command.add_argument("--image", default="liquidbench-runtime:0.1")
            default = (
                "runs/validation-suite.json"
                if name.endswith("suite")
                else "runs/grader-validation.json"
            )
            command.add_argument("--output", type=Path, default=Path(default))
        else:
            command.add_argument("--config", type=Path, required=True)
            command.add_argument("--output", type=Path, default=Path("runs"))
    args = parser.parse_args()
    try:
        if args.command == "doctor":
            report = {"docker_cli": shutil.which("docker")}
            try:
                report["docker_server"] = docker("info", "--format", "{{.ServerVersion}}")
                report["image_id"] = image_id("liquidbench-runtime:0.1")
            except InfrastructureError as exc:
                report["error"] = str(exc)
            print(json.dumps(report, indent=2))
            return int("error" in report)
        if args.command == "build-image":
            return subprocess.call(
                [
                    "docker",
                    "build",
                    "-f",
                    "runtime/Dockerfile",
                    "-t",
                    "liquidbench-runtime:0.1",
                    ".",
                ]
            )
        tasks = (
            discover_tasks(args.tasks_root)
            if args.command.endswith("suite")
            else [Task.load(args.task)]
        )
        if args.command.startswith("validate"):
            image = image_id(args.image)
            reports = [validate(task, image) for task in tasks]
            valid = all(report["valid"] for report in reports)
            report = (
                {"split": "development", "valid": valid, "tasks": reports}
                if args.command.endswith("suite")
                else reports[0]
            )
            save_json(args.output, report)
            return int(not valid)
        config = load_config(args.config)
        if args.command == "run-suite":
            return run_suite(tasks, config, args.output)
        destination, result = run(tasks[0], config, args.output)
        print(
            json.dumps(
                {
                    "status": result["status"],
                    "termination": result["termination"],
                    "artifacts": str(destination),
                },
                indent=2,
            )
        )
        return {"passed": 0, "failed": 1, "infrastructure_error": 2}[result["status"]]
    except (ValueError, OSError, InfrastructureError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
