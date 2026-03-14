from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_engine
from app.core.engine import ImageTranslationEngine
from app.core.errors import EngineError, InputFileError
from app.core.models import TranslationTask


router = APIRouter(tags=["render"])


class RenderTaskPayload(BaseModel):
    box: List[List[int]]
    source_text: str = Field(default="")
    translated_text: str
    text_color: Optional[List[int]] = None
    font_size: Optional[int] = None


class RenderPayload(BaseModel):
    image_path: str = Field(..., description="Local image path")
    tasks: List[RenderTaskPayload]


@router.post("/render")
def render_text(
    payload: RenderPayload,
    engine: ImageTranslationEngine = Depends(get_engine),
) -> dict[str, str]:
    try:
        tasks = [
            TranslationTask(
                id=f"task_{index + 1:03d}",
                box=tuple((point[0], point[1]) for point in task.box),
                source_text=task.source_text,
                translated_text=task.translated_text,
                text_color=tuple(task.text_color) if task.text_color else None,
                font_size=task.font_size,
            )
            for index, task in enumerate(payload.tasks)
        ]
        return engine.render_only(Path(payload.image_path), tasks)
    except InputFileError as exc:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_input_file", "detail": str(exc)},
        ) from exc
    except EngineError as exc:
        raise HTTPException(
            status_code=500,
            detail={"error": "engine_error", "detail": str(exc)},
        ) from exc
