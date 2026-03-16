from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from app.utils.paths import PROJECT_ROOT, resolve_from_root


@dataclass(frozen=True)
class RuntimeConfig:
    output_dir: Path
    temp_dir: Path
    debug: bool
    process_timeout_seconds: int


@dataclass(frozen=True)
class OCRConfig:
    provider: str


@dataclass(frozen=True)
class TranslatorConfig:
    provider: str
    src_lang: str
    tgt_lang: str


@dataclass(frozen=True)
class InpaintConfig:
    provider: str
    expand_pixels: int
    mask_version: str = "v3"


@dataclass(frozen=True)
class ComfyUIConfig:
    server: str
    root_dir: Path
    workflow_file: Path
    request_timeout_seconds: int
    max_consecutive_failures: int
    degradation_cooldown_seconds: int


@dataclass(frozen=True)
class RenderConfig:
    font_path: Path
    stroke_enabled: bool


@dataclass(frozen=True)
class AppConfig:
    runtime: RuntimeConfig
    ocr: OCRConfig
    translator: TranslatorConfig
    inpaint: InpaintConfig
    render: RenderConfig
    comfyui: ComfyUIConfig | None = None  # Optional — not required for default execution


DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(config_path: str | Path | None = None) -> AppConfig:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open("r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    return AppConfig(
        runtime=_build_runtime_config(raw["runtime"]),
        ocr=OCRConfig(**raw["ocr"]),
        translator=TranslatorConfig(**raw["translator"]),
        inpaint=InpaintConfig(**raw["inpaint"]),
        render=_build_render_config(raw["render"]),
        comfyui=_build_comfyui_config(raw["comfyui"]) if "comfyui" in raw else None,
    )


def _build_runtime_config(raw: dict[str, Any]) -> RuntimeConfig:
    return RuntimeConfig(
        output_dir=resolve_from_root(raw["output_dir"]),
        temp_dir=resolve_from_root(raw["temp_dir"]),
        debug=bool(raw["debug"]),
        process_timeout_seconds=int(raw["process_timeout_seconds"]),
    )


def _build_comfyui_config(raw: dict[str, Any]) -> ComfyUIConfig:
    return ComfyUIConfig(
        server=str(raw["server"]),
        root_dir=resolve_from_root(raw["root_dir"]),
        workflow_file=resolve_from_root(raw["workflow_file"]),
        request_timeout_seconds=int(raw["request_timeout_seconds"]),
        max_consecutive_failures=int(raw["max_consecutive_failures"]),
        degradation_cooldown_seconds=int(raw["degradation_cooldown_seconds"]),
    )


def _build_render_config(raw: dict[str, Any]) -> RenderConfig:
    return RenderConfig(
        font_path=resolve_from_root(raw["font_path"]),
        stroke_enabled=bool(raw["stroke_enabled"]),
    )
