from __future__ import annotations

from pathlib import Path

from app.core.config import AppConfig
from app.utils.paths import JobPaths, build_job_paths


class JobService:
    def __init__(self, config: AppConfig) -> None:
        self._config = config

    def create_job(self, job_id: str | None = None) -> JobPaths:
        job_paths = build_job_paths(self._config.runtime.output_dir, job_id=job_id)
        job_paths.job_dir.mkdir(parents=True, exist_ok=True)
        self._config.runtime.temp_dir.mkdir(parents=True, exist_ok=True)
        return job_paths

    def ensure_parent(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
