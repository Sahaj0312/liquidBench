"""Local benchmark audit only: public checker diagnostics on starter/reference files."""

import json
from pathlib import Path

from liquidbench.sandbox import Sandbox, image_id
from liquidbench.task import discover_tasks


def main():
    image = image_id("liquidbench-runtime:0.1")
    rows = []
    for task in discover_tasks(Path("tasks/dev")):
        row = {"task_id": task.manifest["id"], "task_digest": task.digest}
        for name, files in (("starter", task.initial), ("reference", task.reference_files)):
            with Sandbox(image, files) as box:
                row[name] = box.call("check")
        rows.append(row)
        print(row["task_id"], flush=True)
    path = Path("docs/diagnostic/benchmark-audit.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"runtime_image_id": image, "tasks": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
