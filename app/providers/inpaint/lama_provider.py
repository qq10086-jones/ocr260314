from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PIL import Image

from app.providers.inpaint.base import InpaintResult
from app.utils.paths import PROJECT_ROOT


class LaMaProvider:
    """
    Type D local inpaint provider backed by ``simple_lama_inpainting``.

    This implementation is intentionally workspace-local:
    model/cache downloads default to ``<repo>/.model_cache/lama`` instead of
    the user's global ``~/.cache`` so the provider can run on locked-down
    machines without special profile permissions.
    """

    def __init__(self, cache_dir: str | Path | None = None) -> None:
        self._model = None
        self._load_error: RuntimeError | None = None
        self._cache_dir = self._resolve_cache_dir(cache_dir)

    def _resolve_cache_dir(self, cache_dir: str | Path | None) -> Path:
        explicit = cache_dir or os.environ.get("OCR260314_LAMA_CACHE_DIR")
        if explicit:
            return Path(explicit).expanduser().resolve()
        return (PROJECT_ROOT / ".model_cache" / "lama").resolve()

    def _prepare_cache_dirs(self) -> None:
        cache_root = self._cache_dir
        torch_home = cache_root / "torch"
        hf_home = cache_root / "hf"

        torch_home.mkdir(parents=True, exist_ok=True)
        hf_home.mkdir(parents=True, exist_ok=True)

        os.environ["OCR260314_LAMA_CACHE_DIR"] = str(cache_root)
        os.environ["TORCH_HOME"] = str(torch_home)
        os.environ["XDG_CACHE_HOME"] = str(cache_root)
        os.environ["HF_HOME"] = str(hf_home)

    def _load(self) -> None:
        if self._model is not None:
            return

        if self._load_error is not None:
            raise self._load_error

        try:
            self._prepare_cache_dirs()
            from simple_lama_inpainting import SimpleLama

            print(f"[LaMa] loading model cache from {self._cache_dir}")
            self._model = SimpleLama()
            print("[LaMa] model ready")
        except ModuleNotFoundError as exc:
            self._load_error = RuntimeError(
                "LaMa provider requires `simple_lama_inpainting` and `torch`. "
                "Install the local LaMa dependencies on the target machine first."
            )
            raise self._load_error from exc
        except Exception as exc:
            self._load_error = RuntimeError(
                f"LaMa provider failed to initialize with cache dir `{self._cache_dir}`: {exc}"
            )
            raise self._load_error from exc

    def inpaint(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        context: Optional[dict] = None,
    ) -> InpaintResult:
        self._load()

        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(image_rgb)

        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)
        pil_mask = Image.fromarray(mask, mode="L")

        result_pil = self._model(pil_image, pil_mask)
        result_bgr = cv2.cvtColor(np.array(result_pil), cv2.COLOR_RGB2BGR)

        return InpaintResult(
            image=result_bgr,
            method="lama",
            debug_info={
                "mask_pixels": int(np.count_nonzero(mask)),
                "cache_dir": str(self._cache_dir),
            },
        )
