from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


Point = tuple[int, int]
QuadBox = tuple[Point, Point, Point, Point]


@dataclass(frozen=True)
class OCRBox:
    box: QuadBox
    text: str
    score: float


@dataclass(frozen=True)
class TranslationTask:
    id: str
    box: QuadBox
    source_text: str
    translated_text: str = ""
    text_color: tuple[int, int, int] | None = None
    font_size: int | None = None


@dataclass(frozen=True)
class DebugArtifacts:
    input_path: str | None = None
    mask_path: str | None = None
    clean_bg_path: str | None = None
    log_path: str | None = None


@dataclass
class StageTiming:
    load_image_seconds: float = 0.0
    ocr_seconds: float = 0.0
    translate_seconds: float = 0.0
    inpaint_seconds: float = 0.0
    render_seconds: float = 0.0
    export_seconds: float = 0.0


@dataclass
class ProcessResult:
    job_id: str
    status: str
    mode: str
    input_path: str
    output_path: str
    elapsed_seconds: float
    tasks: list[TranslationTask] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    debug: DebugArtifacts = field(default_factory=DebugArtifacts)
    timings: StageTiming = field(default_factory=StageTiming)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tasks"] = [asdict(task) for task in self.tasks]
        return data


@dataclass(frozen=True)
class ProcessRequest:
    image_path: Path
    src_lang: str
    tgt_lang: str
    mode: str = "fast"
    translate: bool = True

