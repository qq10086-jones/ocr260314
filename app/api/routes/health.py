from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_config, get_fast_inpainter, get_ocr_provider

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    config = get_config()

    font_exists = config.render.font_path.exists()
    output_dir_exists = config.runtime.output_dir.exists()

    warnings: list[str] = []
    if not font_exists:
        warnings.append(f"字体文件不存在: {config.render.font_path}")
    if not output_dir_exists:
        warnings.append(f"输出目录不存在，将在首次运行时创建: {config.runtime.output_dir}")

    providers: dict[str, object] = {
        "ocr": type(get_ocr_provider()).__name__,
        "fast_inpaint": type(get_fast_inpainter()).__name__,
        "hq_inpaint": None,
    }

    return {
        "status": "ok" if not warnings else "degraded",
        "providers": providers,
        "resources": {
            "font_exists": font_exists,
            "output_dir_exists": output_dir_exists,
        },
        "warnings": warnings,
    }
