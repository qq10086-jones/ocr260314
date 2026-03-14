from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import get_comfyui_state, get_config, get_hq_inpainter


router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, object]:
    config = get_config()
    comfyui_state = get_comfyui_state()
    comfyui_provider = get_hq_inpainter()
    font_exists = config.render.font_path.exists()
    workflow_exists = config.comfyui.workflow_file.exists()
    comfyui_root_exists = config.comfyui.root_dir.exists()
    output_dir_exists = config.runtime.output_dir.exists()

    warnings: list[str] = []
    if not font_exists:
        warnings.append(f"字体文件不存在: {config.render.font_path}")
    if not workflow_exists:
        warnings.append(f"ComfyUI workflow 文件不存在: {config.comfyui.workflow_file}")
    if not comfyui_root_exists:
        warnings.append(f"ComfyUI 根目录不存在: {config.comfyui.root_dir}")
    if not output_dir_exists:
        warnings.append(f"输出目录不存在，将在首次运行时创建: {config.runtime.output_dir}")

    return {
        "status": "ok" if not warnings else "degraded",
        "comfyui_available": comfyui_provider.is_available(),
        "comfyui_degraded": comfyui_state.is_degraded,
        "resources": {
            "font_exists": font_exists,
            "workflow_exists": workflow_exists,
            "comfyui_root_exists": comfyui_root_exists,
            "output_dir_exists": output_dir_exists,
        },
        "warnings": warnings,
    }
