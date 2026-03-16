from __future__ import annotations

from functools import lru_cache

from app.core.config import AppConfig, load_config
from app.core.engine import ImageTranslationEngine
from app.providers.inpaint.opencv_provider import OpenCVInpainter
from app.providers.ocr.rapidocr_provider import RapidOCROCRProvider
from app.providers.translator.local_provider import GoogleTranslatorProvider
from app.providers.translator.noop import NoOpTranslator
from app.render.text_renderer import TextRenderer
from app.services.job_service import JobService
from app.services.lock_service import ProcessLockService


@lru_cache
def get_config() -> AppConfig:
    return load_config()


@lru_cache
def get_ocr_provider() -> RapidOCROCRProvider:
    return RapidOCROCRProvider()


@lru_cache
def get_translator_provider() -> NoOpTranslator | GoogleTranslatorProvider:
    config = get_config()
    return NoOpTranslator() if config.translator.provider == "noop" else GoogleTranslatorProvider()


@lru_cache
def get_fast_inpainter() -> OpenCVInpainter:
    config = get_config()
    return OpenCVInpainter(expand_pixels=config.inpaint.expand_pixels)


@lru_cache
def get_renderer() -> TextRenderer:
    config = get_config()
    return TextRenderer(str(config.render.font_path))


@lru_cache
def get_engine() -> ImageTranslationEngine:
    config = get_config()
    return ImageTranslationEngine(
        config=config,
        ocr_provider=get_ocr_provider(),
        translator_provider=get_translator_provider(),
        fast_inpainter=get_fast_inpainter(),
        hq_inpainter=None,
        renderer=get_renderer(),
        lock_service=ProcessLockService(),
        job_service=JobService(config),
    )
