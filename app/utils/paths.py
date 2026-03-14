from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def resolve_from_root(value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


@dataclass(frozen=True)
class JobPaths:
    job_id: str
    job_dir: Path
    input_path: Path
    mask_path: Path
    clean_bg_path: Path
    result_path: Path
    result_json_path: Path
    log_path: Path


def build_job_paths(output_root: str | Path, job_id: str | None = None) -> JobPaths:
    current_job_id = job_id or f"job_{uuid4().hex[:12]}"
    date_dir = datetime.now().strftime("%Y-%m-%d")
    job_dir = resolve_from_root(output_root) / date_dir / current_job_id

    return JobPaths(
        job_id=current_job_id,
        job_dir=job_dir,
        input_path=job_dir / "input.png",
        mask_path=job_dir / "mask.png",
        clean_bg_path=job_dir / "clean_bg.png",
        result_path=job_dir / "result.png",
        result_json_path=job_dir / "result.json",
        log_path=job_dir / "logs.txt",
    )
