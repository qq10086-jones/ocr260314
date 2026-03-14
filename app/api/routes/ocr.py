from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_engine
from app.core.engine import ImageTranslationEngine
from app.core.errors import EngineError, InputFileError


router = APIRouter(tags=["ocr"])


class OCRPayload(BaseModel):
    image_path: str = Field(..., description="Local image path")


@router.post("/ocr")
def detect_text(
    payload: OCRPayload,
    engine: ImageTranslationEngine = Depends(get_engine),
) -> dict[str, object]:
    try:
        boxes = engine.detect_only(Path(payload.image_path))
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

    return {
        "status": "success",
        "count": len(boxes),
        "boxes": [
            {
                "box": box.box,
                "text": box.text,
                "score": box.score,
            }
            for box in boxes
        ],
    }
