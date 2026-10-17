#!/usr/bin/env python3
"""One command for every check, on every OS. Agents, the verifier and CI run exactly this.

Usage:  uv run python scripts/check.py
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable  # the uv-managed interpreter that runs this script
CHECKS = [
    ("ruff check", [PY, "-m", "ruff", "check", "."]),
    ("ruff format", [PY, "-m", "ruff", "format", "--check", "."]),
    ("mypy", [PY, "-m", "mypy"]),
    ("pytest", [PY, "-m", "pytest"]),
    ("agent layer", [PY, "scripts/validate_agent_layer.py"]),
    ("diff limit", [PY, "scripts/check_diff_limit.py"]),
]


def main() -> int:
    for name, cmd in CHECKS:
        print(f"== {name}", flush=True)
        if subprocess.run(cmd, cwd=ROOT, check=False).returncode != 0:
            print(f"FAILED: {name}")
            return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
