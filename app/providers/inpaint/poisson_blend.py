from __future__ import annotations

from typing import Optional, Tuple

import cv2
import numpy as np


def poisson_blend(
    src: np.ndarray,
    mask: np.ndarray,
    dst: np.ndarray,
    center: Optional[Tuple[int, int]] = None,
) -> np.ndarray:
    """Blend ``src`` into ``dst`` with ``cv2.seamlessClone`` and safe fallback."""
    if src.shape[:2] != dst.shape[:2]:
        raise ValueError("src and dst must have the same spatial shape")

    if mask.shape[:2] != dst.shape[:2]:
        raise ValueError("mask and dst must have the same spatial shape")

    mask_binary = _to_binary_mask(mask)
    if not np.any(mask_binary):
        return dst.copy()

    if center is None:
        height, width = dst.shape[:2]
        center = (width // 2, height // 2)

    try:
        return cv2.seamlessClone(src, dst, mask_binary, center, cv2.NORMAL_CLONE)
    except cv2.error:
        return fallback_blend(src, mask_binary, dst)


def fallback_blend(
    src: np.ndarray,
    mask: np.ndarray,
    dst: np.ndarray,
) -> np.ndarray:
    """Simple same-shape alpha blend fallback."""
    if src.shape[:2] != dst.shape[:2]:
        raise ValueError("src and dst must have the same spatial shape")

    mask_norm = (_to_binary_mask(mask).astype(np.float32) / 255.0)[:, :, np.newaxis]
    blended = src.astype(np.float32) * mask_norm + dst.astype(np.float32) * (1.0 - mask_norm)
    return np.clip(blended, 0, 255).astype(np.uint8)


def gaussian_feather(
    mask: np.ndarray,
    feather_radius: int = 5,
) -> np.ndarray:
    """Gaussian blur helper used by non-Poisson fallbacks/debug paths."""
    if feather_radius <= 0:
        return mask

    return cv2.GaussianBlur(mask, (feather_radius * 2 + 1, feather_radius * 2 + 1), 0)


def _to_binary_mask(mask: np.ndarray) -> np.ndarray:
    if mask.ndim == 3:
        mask = cv2.cvtColor(mask, cv2.COLOR_BGR2GRAY)
    return np.where(mask > 127, 255, 0).astype(np.uint8)
