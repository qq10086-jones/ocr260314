"""
Shared fixtures for all tests.
Engine is intentionally constructed with minimal providers:
  - NoOpTranslator: no network calls
  - OpenCVInpainter only: no ComfyUI dependency
  - renderer=None: no font file dependency
This makes the fixture runnable on any machine without external services.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import load_config
from app.core.engine import ImageTranslationEngine
from app.providers.inpaint.opencv_provider import OpenCVInpainter
from app.providers.ocr.rapidocr_provider import RapidOCROCRProvider
from app.providers.translator.noop import NoOpTranslator
from app.services.job_service import JobService
from app.services.lock_service import ProcessLockService

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_IMAGE = Path(__file__).parent.parent / "samples" / "input" / "test_ocr.png"


@pytest.fixture(scope="session")
def app_config():
    return load_config()


@pytest.fixture
def minimal_engine(app_config):
    """Engine with no external dependencies. Safe to run anywhere."""
    return ImageTranslationEngine(
        config=app_config,
        ocr_provider=RapidOCROCRProvider(),
        translator_provider=NoOpTranslator(),
        fast_inpainter=OpenCVInpainter(expand_pixels=app_config.inpaint.expand_pixels),
        hq_inpainter=None,
        renderer=None,
        lock_service=ProcessLockService(),
        job_service=JobService(app_config),
    )


@pytest.fixture(scope="session")
def sample_image_path():
    assert SAMPLE_IMAGE.exists(), (
        f"Sample image not found: {SAMPLE_IMAGE}\n"
        "Add a test image at samples/input/test_ocr.png before running tests."
    )
    return SAMPLE_IMAGE
