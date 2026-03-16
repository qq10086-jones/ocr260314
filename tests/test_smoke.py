"""
Sprint-0 / M0-B: Smoke test baseline.

Purpose: verify the core pipeline (OCR -> mask -> inpaint -> output) runs
end-to-end in fast mode without ComfyUI, network calls, or font files.

These tests are the minimum safety net that must pass before any M1
refactoring begins. If any of these fail after a code change, stop and fix.

Run with:
    pytest tests/test_smoke.py -v
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.models import ProcessRequest


class TestEngineSmoke:
    """End-to-end pipeline smoke tests."""

    def test_fast_mode_returns_success(self, minimal_engine, sample_image_path):
        """Core pipeline completes without exception and reports success."""
        request = ProcessRequest(
            image_path=sample_image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode="fast",
            translate=False,
        )
        result = minimal_engine.process(request)
        assert result.status == "success"

    def test_fast_mode_produces_output_file(self, minimal_engine, sample_image_path):
        """Output image file is written to disk."""
        request = ProcessRequest(
            image_path=sample_image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode="fast",
            translate=False,
        )
        result = minimal_engine.process(request)
        assert Path(result.output_path).exists(), (
            f"Output file not found: {result.output_path}"
        )

    def test_fast_mode_produces_result_json(self, minimal_engine, sample_image_path):
        """result.json is written and contains expected top-level keys."""
        request = ProcessRequest(
            image_path=sample_image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode="fast",
            translate=False,
        )
        result = minimal_engine.process(request)

        result_json_path = Path(result.output_path).parent / "result.json"
        assert result_json_path.exists(), f"result.json not found at {result_json_path}"

        payload = json.loads(result_json_path.read_text(encoding="utf-8"))
        for key in ("status", "mode", "output_path", "tasks", "timings"):
            assert key in payload, f"Missing key '{key}' in result.json"

    def test_fast_mode_result_has_job_id(self, minimal_engine, sample_image_path):
        """Every result has a non-empty job_id for artifact traceability."""
        request = ProcessRequest(
            image_path=sample_image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode="fast",
            translate=False,
        )
        result = minimal_engine.process(request)
        assert result.job_id, "job_id must not be empty"

    def test_fast_mode_records_elapsed_time(self, minimal_engine, sample_image_path):
        """elapsed_seconds is a positive number."""
        request = ProcessRequest(
            image_path=sample_image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode="fast",
            translate=False,
        )
        result = minimal_engine.process(request)
        assert result.elapsed_seconds > 0

    def test_tasks_is_a_list(self, minimal_engine, sample_image_path):
        """tasks field is always a list (empty is fine if OCR finds nothing)."""
        request = ProcessRequest(
            image_path=sample_image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode="fast",
            translate=False,
        )
        result = minimal_engine.process(request)
        assert isinstance(result.tasks, list)

    def test_hq_mode_falls_back_to_fast_when_no_hq_inpainter(
        self, minimal_engine, sample_image_path
    ):
        """
        When hq_inpainter=None, requesting mode='hq' falls back to fast
        and completes successfully (with a warning).
        """
        request = ProcessRequest(
            image_path=sample_image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode="hq",
            translate=False,
        )
        result = minimal_engine.process(request)
        assert result.status == "success"
        assert any("HQ" in w or "hq" in w.lower() or "fast" in w.lower() for w in result.warnings), (
            "Expected a fallback warning when hq_inpainter is None"
        )


class TestConfigSmoke:
    """Configuration loading smoke tests."""

    def test_config_loads(self, app_config):
        """Config loads without error from config/config.yaml."""
        assert app_config is not None

    def test_config_has_required_sections(self, app_config):
        """All required config sections are present."""
        assert app_config.runtime is not None
        assert app_config.ocr is not None
        assert app_config.translator is not None
        assert app_config.inpaint is not None
        assert app_config.render is not None

    def test_config_timeout_is_positive(self, app_config):
        assert app_config.runtime.process_timeout_seconds > 0


class TestInputValidation:
    """Input validation smoke tests."""

    def test_missing_image_raises_input_error(self, minimal_engine):
        """Engine raises InputFileError for non-existent image path."""
        from app.core.errors import InputFileError

        request = ProcessRequest(
            image_path=Path("non_existent_image_xyz.png"),
            src_lang="auto",
            tgt_lang="ja",
            mode="fast",
            translate=False,
        )
        with pytest.raises(InputFileError):
            minimal_engine.process(request)
