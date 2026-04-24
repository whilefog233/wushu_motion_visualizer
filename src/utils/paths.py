from __future__ import annotations

from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
CACHE_DIR = DATA_DIR / "cache"


def ensure_project_dirs() -> None:
    for path in (DATA_DIR, INPUT_DIR, OUTPUT_DIR, CACHE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def make_output_run_dir(prefix: str) -> Path:
    ensure_project_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{prefix}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir
