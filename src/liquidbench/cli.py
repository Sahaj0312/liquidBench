import argparse
import json
from pathlib import Path
import shutil
import subprocess

from .grading import grade, validation_candidates
from .runner import load_config, run
from .sandbox import InfrastructureError, docker, image_id
from .task import Task


def main():
    parser = argparse.ArgumentParser(prog="liquidbench")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("doctor")
    commands.add_parser("build-image")
    validate = commands.add_parser("validate-task")
    validate.add_argument("--task", type=Path, default=Path("tasks/dev/product-card"))
    validate.add_argument("--image", default="liquidbench-runtime:0.1")
    validate.add_argument("--output", type=Path, default=Path("runs/grader-validation.json"))
    execute = commands.add_parser("run")
    execute.add_argument("--task", type=Path, default=Path("tasks/dev/product-card"))
    execute.add_argument("--config", type=Path, required=True)
    execute.add_argument("--output", type=Path, default=Path("runs"))
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
        task = Task.load(args.task)
        if args.command == "validate-task":
            image = image_id(args.image)
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
                    f"{name}: {'PASS' if result['passed'] else 'FAIL'} "
                    f"(expected {'PASS' if expected else 'FAIL'})",
                    flush=True,
                )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(
                    {"task_digest": task.digest, "image_id": image, "outcomes": outcomes}, indent=2
                )
                + "\n"
            )
            return int(not all(item["correct_verdict"] for item in outcomes))
        destination, result = run(task, load_config(args.config), args.output)
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
