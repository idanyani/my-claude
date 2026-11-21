"""Run a hook as Claude Code does: a python3 process fed its payload on stdin."""

import subprocess
import sys
from pathlib import Path


def run_hook(hook: Path, stdin: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(hook)], input=stdin, capture_output=True, text=True, check=False
    )
