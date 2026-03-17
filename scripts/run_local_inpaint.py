#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import load_config
from app.core.engine import ImageTranslationEngine
from app.core.models import ProcessRequest
from app.providers.inpaint.opencv_provider import OpenCVInpainter
from app.providers.ocr.rapidocr_provider import RapidOCROCRProvider
from app.providers.translator.noop import NoOpTranslator
from app.render.text_renderer import TextRenderer
from app.services.job_service import JobService
from app.services.lock_service import ProcessLockService


def build_engine(output_root: Path, temp_root: Path) -> ImageTranslationEngine:
    config = load_config()
    runtime = replace(config.runtime, output_dir=output_root, temp_dir=temp_root)
    config = replace(config, runtime=runtime)

    try:
        renderer = TextRenderer(font_path=str(config.render.font_path))
    except Exception:
        renderer = None

    return ImageTranslationEngine(
        config=config,
        ocr_provider=RapidOCROCRProvider(),
        translator_provider=NoOpTranslator(),
        fast_inpainter=OpenCVInpainter(expand_pixels=config.inpaint.expand_pixels),
        hq_inpainter=None,
        renderer=renderer,
        lock_service=ProcessLockService(),
        job_service=JobService(config),
    )


def process_image(engine: ImageTranslationEngine, image_path: Path, mode: str) -> dict:
    result = engine.process(
        ProcessRequest(
            image_path=image_path,
            src_lang="auto",
            tgt_lang="ja",
            mode=mode,
            translate=False,
        )
    )
    result_dir = Path(result.output_path).parent
    return {
        "image": str(image_path),
        "job_id": result.job_id,
        "result_dir": str(result_dir),
        "result": str(result_dir / "result.png"),
        "clean_bg": str(result_dir / "clean_bg.png"),
        "mask": str(result_dir / "mask.png"),
        "log": str(result_dir / "logs.txt"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local OCR260314 inpaint smoke on one image or a folder.")
    parser.add_argument("--image", type=Path, help="Single image to process.")
    parser.add_argument("--input-dir", type=Path, help="Directory of images to process.")
    parser.add_argument("--mode", choices=["fast", "smart"], default="smart")
    parser.add_argument("--output-root", type=Path, default=Path("manual_runs") / "local_inpaint")
    args = parser.parse_args()

    if not args.image and not args.input_dir:
        raise SystemExit("Specify --image or --input-dir")

    engine = build_engine(args.output_root / "runs", args.output_root / "tmp")

    images: list[Path] = []
    if args.image:
        images.append(args.image)
    if args.input_dir:
        for path in sorted(args.input_dir.iterdir()):
            if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                images.append(path)

    outputs = [process_image(engine, image_path, args.mode) for image_path in images]
    print(json.dumps(outputs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
