from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from app.providers.inpaint.base import InpaintResult
from app.providers.inpaint.poisson_blend import poisson_blend


class SolidFillProvider:
    """Type A background reconstruction using deterministic solid fill."""

    def __init__(self, feather_radius: int = 10):
        self.feather_radius = feather_radius

    def inpaint(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        context: Optional[dict] = None,
    ) -> InpaintResult:
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        if image.shape[2] == 4:
            image = cv2.cvtColor(image, cv2.COLOR_BGRA2BGR)

        if mask.shape != image.shape[:2]:
            resized_mask = np.zeros(image.shape[:2], dtype=mask.dtype)
            resized_mask[: min(image.shape[0], mask.shape[0]), : min(image.shape[1], mask.shape[1])] = mask[
                : min(image.shape[0], mask.shape[0]),
                : min(image.shape[1], mask.shape[1]),
            ]
            mask = resized_mask

        bg_color = self._sample_background_color(image, mask)
        mask_binary = np.where(mask > 127, 255, 0).astype(np.uint8)

        filled = image.copy()
        filled[mask_binary > 0] = bg_color
        blended = poisson_blend(filled, mask_binary, image)

        return InpaintResult(
            image=blended,
            method="solid_fill",
            debug_info={
                "bg_color": bg_color.tolist(),
                "blend": "poisson",
            },
        )

    def _sample_background_color(
        self,
        image: np.ndarray,
        mask: np.ndarray,
    ) -> np.ndarray:
        height, width = image.shape[:2]

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
        expanded_mask = cv2.dilate(mask, kernel)
        valid_region = expanded_mask == 0

        bg_pixels = image[valid_region].reshape(-1, 3)
        if len(bg_pixels) < 100:
            margin_y = min(50, height // 4)
            margin_x = min(50, width // 4)
            bg_pixels = np.concatenate(
                [
                    image[:margin_y, :, :].reshape(-1, 3),
                    image[height - margin_y :, :, :].reshape(-1, 3),
                    image[:, :margin_x, :].reshape(-1, 3),
                    image[:, width - margin_x :, :].reshape(-1, 3),
                ]
            )

        if len(bg_pixels) == 0:
            return np.array([255, 255, 255], dtype=np.uint8)

        return np.median(bg_pixels, axis=0).astype(np.uint8)
