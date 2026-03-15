from __future__ import annotations

import json
import time
from pathlib import Path

from app.core.config import AppConfig
from app.core.errors import InputFileError
from app.core.models import DebugArtifacts, OCRBox, ProcessRequest, ProcessResult, StageTiming, TranslationTask
from app.providers.inpaint.base import InpainterProvider
from app.providers.inpaint.comfyui_provider import ComfyUIInpainter
from app.providers.inpaint.opencv_provider import OpenCVInpainter
from app.providers.ocr.base import OCRProvider
from app.providers.translator.base import TranslatorProvider
from app.render.color_extractor import get_smart_text_color
from app.render.text_renderer import TextRenderer
from app.services.job_service import JobService
from app.services.lock_service import ProcessLockService
from app.utils.image_io import ensure_image_exists, load_image, save_image
from app.utils.logging import append_log


class ImageTranslationEngine:
    def __init__(
        self,
        config: AppConfig,
        ocr_provider: OCRProvider,
        translator_provider: TranslatorProvider,
        fast_inpainter: InpainterProvider,
        hq_inpainter: InpainterProvider | None = None,
        renderer: TextRenderer | None = None,
        lock_service: ProcessLockService | None = None,
        job_service: JobService | None = None,
    ) -> None:
        self._config = config
        self._ocr_provider = ocr_provider
        self._translator_provider = translator_provider
        self._fast_inpainter = fast_inpainter
        self._hq_inpainter = hq_inpainter
        self._renderer = renderer
        self._lock_service = lock_service or ProcessLockService()
        self._job_service = job_service or JobService(config)

    def process(self, request: ProcessRequest) -> ProcessResult:
        self._lock_service.acquire()
        started_at = time.perf_counter()
        job_paths = self._job_service.create_job()
        timings = StageTiming()

        try:
            image_path = self._validate_input_path(request.image_path)
            append_log(job_paths.log_path, f"process_start mode={request.mode} image={image_path}")

            stage_started_at = time.perf_counter()
            image = self._load_image(image_path)
            timings.load_image_seconds = round(time.perf_counter() - stage_started_at, 3)

            stage_started_at = time.perf_counter()
            ocr_boxes = self._ocr_provider.detect(image)
            timings.ocr_seconds = round(time.perf_counter() - stage_started_at, 3)
            append_log(job_paths.log_path, f"ocr_boxes={len(ocr_boxes)}")

            tasks = self._build_tasks(ocr_boxes, request, image)

            stage_started_at = time.perf_counter()
            translated_tasks = self._translate_tasks(tasks, request)
            timings.translate_seconds = round(time.perf_counter() - stage_started_at, 3)

            mask = self._build_mask(image, ocr_boxes)
            
            # P2: 生成质量调试图 (Overlay)
            from app.qa.evaluator import QAEvaluator
            qa = QAEvaluator()
            overlay = qa.generate_debug_overlay(image, mask)
            qa_stats = qa.calculate_mask_stats(mask)
            # 明确保存到任务文件夹
            save_image(job_paths.job_dir / "debug_overlay.png", overlay)
            print(f"[Debug] 已保存 QA 调试图到: {job_paths.job_dir / 'debug_overlay.png'}")

            stage_started_at = time.perf_counter()
            cleaned_background = self._select_inpainter(request.mode).inpaint(image, mask)
            timings.inpaint_seconds = round(time.perf_counter() - stage_started_at, 3)

            stage_started_at = time.perf_counter()
            rendered_result = self._render(cleaned_background, translated_tasks)
            timings.render_seconds = round(time.perf_counter() - stage_started_at, 3)

            stage_started_at = time.perf_counter()
            save_image(job_paths.input_path, image)
            save_image(job_paths.mask_path, mask)
            save_image(job_paths.clean_bg_path, cleaned_background)
            output_path = save_image(job_paths.result_path, rendered_result)
            warnings = self._build_warnings(request)
            timings.export_seconds = round(time.perf_counter() - stage_started_at, 3)
            self._write_result_json(
                job_paths.result_json_path,
                translated_tasks,
                request,
                output_path,
                timings,
                warnings=warnings,
                qa_stats=qa_stats
            )
            append_log(job_paths.log_path, f"result_saved={output_path}")

            elapsed_seconds = round(time.perf_counter() - started_at, 3)
            append_log(job_paths.log_path, f"process_success elapsed_seconds={elapsed_seconds}")
            return ProcessResult(
                job_id=job_paths.job_id,
                status="success",
                mode=request.mode,
                input_path=str(image_path),
                output_path=str(output_path),
                elapsed_seconds=elapsed_seconds,
                tasks=translated_tasks,
                debug=DebugArtifacts(
                    input_path=str(job_paths.input_path),
                    mask_path=str(job_paths.mask_path),
                    clean_bg_path=str(job_paths.clean_bg_path),
                    log_path=str(job_paths.log_path),
                ),
                warnings=warnings,
                timings=timings,
            )
        except Exception as exc:
            append_log(job_paths.log_path, f"process_error error={exc}")
            raise
        finally:
            self._lock_service.release()

    def detect_only(self, image_path: Path) -> list[OCRBox]:
        resolved_path = self._validate_input_path(image_path)
        image = self._load_image(resolved_path)
        return self._ocr_provider.detect(image)

    def erase_only(self, image_path: Path, mode: str = "fast") -> dict[str, str]:
        resolved_path = self._validate_input_path(image_path)
        image = self._load_image(resolved_path)
        ocr_boxes = self._ocr_provider.detect(image)
        mask = self._build_mask(image, ocr_boxes)
        cleaned = self._select_inpainter(mode).inpaint(image, mask)

        job_paths = self._job_service.create_job()
        save_image(job_paths.input_path, image)
        save_image(job_paths.mask_path, mask)
        save_image(job_paths.clean_bg_path, cleaned)

        return {
            "job_id": job_paths.job_id,
            "mode": mode,
            "input_path": str(resolved_path),
            "output_path": str(job_paths.clean_bg_path),
            "mask_path": str(job_paths.mask_path),
            "warning": "当前 /erase 已接入真实 OCR + mask + inpaint，但仍未返回更细的调试元数据",
        }

    def render_only(self, image_path: Path, tasks: list[TranslationTask]) -> dict[str, str]:
        resolved_path = self._validate_input_path(image_path)
        image = self._load_image(resolved_path)
        rendered = self._render(image, tasks)

        job_paths = self._job_service.create_job()
        save_image(job_paths.input_path, image)
        output_path = save_image(job_paths.result_path, rendered)
        timings = StageTiming()
        self._write_result_json(
            job_paths.result_json_path,
            tasks,
            ProcessRequest(image_path=resolved_path, src_lang="auto", tgt_lang="ja"),
            output_path,
            timings,
            warnings=[],
        )

        return {
            "job_id": job_paths.job_id,
            "input_path": str(resolved_path),
            "output_path": str(output_path),
        }

    def _load_image(self, image_path: Path):
        return load_image(image_path)

    def _build_tasks(
        self,
        ocr_boxes: list[OCRBox],
        request: ProcessRequest,
        image,
    ) -> list[TranslationTask]:
        tasks: list[TranslationTask] = []
        for index, ocr_box in enumerate(ocr_boxes):
            tasks.append(
                TranslationTask(
                    id=f"task_{index + 1:03d}",
                    box=ocr_box.box,
                    source_text=ocr_box.text,
                    translated_text=ocr_box.text if not request.translate else "",
                    text_color=get_smart_text_color(image, ocr_box.box),
                )
            )
        return tasks

    def _translate_tasks(
        self,
        tasks: list[TranslationTask],
        request: ProcessRequest,
    ) -> list[TranslationTask]:
        if not request.translate:
            return tasks

        translated_tasks: list[TranslationTask] = []
        for task in tasks:
            translated_text = task.source_text
            try:
                translated_text = self._translator_provider.translate(
                    task.source_text,
                    request.src_lang,
                    request.tgt_lang,
                )
            except Exception:
                translated_text = task.source_text

            translated_tasks.append(
                TranslationTask(
                    id=task.id,
                    box=task.box,
                    source_text=task.source_text,
                    translated_text=translated_text,
                    text_color=task.text_color,
                    font_size=task.font_size,
                )
            )
        return translated_tasks

    def _build_warnings(self, request: ProcessRequest) -> list[str]:
        warnings: list[str] = []
        if request.mode == "hq" and self._hq_inpainter is None:
            warnings.append("HQ inpainter 未配置，当前自动回退 fast 模式")
        if isinstance(self._hq_inpainter, ComfyUIInpainter) and self._hq_inpainter.is_degraded:
            warnings.append("ComfyUI 当前处于降级状态，HQ 请求已回退到 OpenCV")
        if self._renderer is None:
            warnings.append("Renderer 尚未接入，结果输出当前为擦字背景")
        return warnings

    def _validate_input_path(self, image_path: Path) -> Path:
        try:
            return ensure_image_exists(image_path)
        except FileNotFoundError as exc:
            raise InputFileError(str(exc)) from exc

    def _select_inpainter(self, mode: str) -> InpainterProvider:
        if mode == "hq" and self._hq_inpainter is not None:
            return self._hq_inpainter
        return self._fast_inpainter

from app.mask.refiner import MaskRefiner

...

    def _build_mask(self, image, ocr_boxes: list[OCRBox]):
        # 默认使用新的 MaskRefiner 进行精细分割
        refiner = MaskRefiner(expand_pixels=self._config.inpaint.expand_pixels // 2)
        return refiner.refine_mask(image, ocr_boxes)

    def _render(self, image, tasks: list[TranslationTask]):
        if self._renderer is None:
            return image
        return self._renderer.render(image, tasks)

    def _write_result_json(
        self,
        output_path: Path,
        tasks: list[TranslationTask],
        request: ProcessRequest,
        result_image_path: Path,
        timings: StageTiming,
        warnings: list[str],
        qa_stats: dict | None = None,
    ) -> None:
        payload = {
            "status": "success",
            "mode": request.mode,
            "input_path": str(request.image_path),
            "output_path": str(result_image_path),
            "warnings": warnings,
            "qa_stats": qa_stats or {},
            "timings": {
                "load_image_seconds": timings.load_image_seconds,
                "ocr_seconds": timings.ocr_seconds,
                "translate_seconds": timings.translate_seconds,
                "inpaint_seconds": timings.inpaint_seconds,
                "render_seconds": timings.render_seconds,
                "export_seconds": timings.export_seconds,
            },
            "tasks": [
                {
                    "id": task.id,
                    "box": task.box,
                    "source_text": task.source_text,
                    "translated_text": task.translated_text,
                    "text_color": task.text_color,
                    "font_size": task.font_size,
                }
                for task in tasks
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
