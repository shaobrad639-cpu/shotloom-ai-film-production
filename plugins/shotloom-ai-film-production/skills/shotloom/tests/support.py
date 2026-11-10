"""Shared fixtures for the Shotloom validator test-suite."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
EXAMPLES = ROOT / "examples" / "shot-03"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def copy_example(target: Path) -> Path:
    destination = target / "shot-03"
    shutil.copytree(EXAMPLES, destination)
    return destination


def run_script(script: str, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / script), *[str(arg) for arg in args]],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )


def greenlit() -> dict[str, Any]:
    return load_json(EXAMPLES / "shot-pass-greenlit.json")
