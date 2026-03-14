from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_engine
from app.core.engine import ImageTranslationEngine
from app.core.errors import EngineError, InputFileError


router = APIRouter(tags=["erase"])


class ErasePayload(BaseModel):
    image_path: str = Field(..., description="Local image path")
    mode: str = Field(default="fast")


@router.post("/erase")
def erase_text(
    payload: ErasePayload,
    engine: ImageTranslationEngine = Depends(get_engine),
) -> dict[str, str]:
    try:
        return engine.erase_only(Path(payload.image_path), mode=payload.mode)
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
