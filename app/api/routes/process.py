from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import get_config, get_engine
from app.core.config import AppConfig
from app.core.engine import ImageTranslationEngine
from app.core.errors import EngineBusyError, EngineError, InputFileError
from app.core.models import ProcessRequest


router = APIRouter(tags=["process"])


class ProcessPayload(BaseModel):
    image_path: str = Field(..., description="Local image path")
    src_lang: str = Field(default="auto")
    tgt_lang: str = Field(default="ja")
    mode: str = Field(default="fast")
    translate: bool = Field(default=True)


@router.post("/process")
def process_image(
    payload: ProcessPayload,
    engine: ImageTranslationEngine = Depends(get_engine),
    config: AppConfig = Depends(get_config),
) -> dict[str, object]:
    executor = ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(
            engine.process,
            ProcessRequest(
                image_path=Path(payload.image_path),
                src_lang=payload.src_lang,
                tgt_lang=payload.tgt_lang,
                mode=payload.mode,
                translate=payload.translate,
            ),
        )
        result = future.result(timeout=config.runtime.process_timeout_seconds)
    except EngineBusyError as exc:
        raise HTTPException(
            status_code=429,
            detail={"error": "engine_busy", "detail": str(exc)},
        ) from exc
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
    except FuturesTimeoutError as exc:
        executor.shutdown(wait=False, cancel_futures=True)
        raise HTTPException(
            status_code=504,
            detail={"error": "processing_timeout", "detail": "任务处理超时"},
        ) from exc
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return result.to_dict()
