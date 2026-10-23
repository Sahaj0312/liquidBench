"""Probe an already authorized endpoint; never provision compute or load tasks.

This is a serving diagnostic, not a benchmark attempt or GPU/precision attestation.
Run explicitly with --config and a new --output directory. CI uses HTTP mocks only.
"""

import argparse
import json
from pathlib import Path

from liquidbench.preflight import preflight
from liquidbench.runner import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = preflight(load_config(args.config), args.output)
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "policy": report["policy"],
                "failure_kind": report["failure_kind"],
                "model_failures": report["model_failures"],
                "artifacts": str(args.output),
            }
        )
    )
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
