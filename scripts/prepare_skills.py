"""Fetch the pinned upstream checkout locally, without vendoring or executing it.

Run from the repository root with uv run python scripts/prepare_skills.py.
Existing checkouts are verified, never reset. No model requests are made.
"""

import argparse
import json
from pathlib import Path
import subprocess

from liquidbench.skills import SkillBundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("configs/qwen-ab-skills.json"))
    args = parser.parse_args()
    spec = json.loads(args.config.read_text())["skills"]
    manifest = json.loads(Path(spec["manifest"]).read_text())
    checkout = Path(spec["checkout"])
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--no-checkout", manifest["repository"], str(checkout)], check=True
        )
        subprocess.run(
            ["git", "-C", str(checkout), "checkout", "--detach", spec["revision"]], check=True
        )
    bundle = SkillBundle.load(spec)
    print(json.dumps({"revision": spec["revision"], "verified_documents": len(bundle.documents)}))


if __name__ == "__main__":
    main()
