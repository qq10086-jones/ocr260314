from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from app.providers.inpaint.base import InpaintResult
from app.providers.inpaint.poisson_blend import poisson_blend


class GradientFillProvider:
    """Type B background reconstruction via per-channel 2D linear fit."""

    def __init__(self, feather_radius: int = 10):
        self.feather_radius = feather_radius

    def inpaint(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        context: Optional[dict] = None,
    ) -> InpaintResult:
        height, width = image.shape[:2]
        gradient_params = self._fit_gradient(image, mask)

        if gradient_params.get("type") == "fallback":
            return InpaintResult(
                image=image.copy(),
                method="gradient_fill_fallback",
                debug_info={"reason": "insufficient background pixels"},
            )

        y_coords, x_coords = np.mgrid[0:height, 0:width].astype(np.float32)
        x_norm = x_coords / max(width - 1, 1)
        y_norm = y_coords / max(height - 1, 1)

        gradient_channels = []
        for channel_name in ("b", "g", "r"):
            gradient_channels.append(
                gradient_params[f"a_{channel_name}"] * x_norm
                + gradient_params[f"b_{channel_name}"] * y_norm
                + gradient_params[f"c_{channel_name}"]
            )

        gradient_map = np.stack(gradient_channels, axis=2)
        gradient_map = np.clip(gradient_map, 0, 255).astype(np.uint8)

        mask_binary = np.where(mask > 127, 255, 0).astype(np.uint8)
        filled = image.copy()
        filled[mask_binary > 0] = gradient_map[mask_binary > 0]
        blended = poisson_blend(filled, mask_binary, image)

        return InpaintResult(
            image=blended,
            method="gradient_fill",
            debug_info={
                "r2": gradient_params.get("r2", 0.0),
                "gradient_type": gradient_params.get("type", "linear"),
                "blend": "poisson",
            },
        )

    def _fit_gradient(
        self,
        image: np.ndarray,
        mask: np.ndarray,
    ) -> dict:
        height, width = image.shape[:2]
        x1, y1, x2, y2 = self._gradient_roi(mask, width, height)

        region = image[y1:y2, x1:x2]
        region_mask = mask[y1:y2, x1:x2]

        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (21, 21))
        expanded_mask = cv2.dilate(region_mask, kernel)
        valid_region = expanded_mask == 0

        bg_pixels = region[valid_region]
        if len(bg_pixels) < 100:
            return self._fallback_params()

        y_coords, x_coords = np.mgrid[y1:y2, x1:x2]
        x_vals = x_coords[valid_region].astype(np.float32) / max(width - 1, 1)
        y_vals = y_coords[valid_region].astype(np.float32) / max(height - 1, 1)
        design = np.column_stack([x_vals, y_vals, np.ones_like(x_vals)])

        params: dict[str, float | str] = {"type": "linear", "r2": 0.0}
        r2_scores: list[float] = []

        for index, channel_name in enumerate(("b", "g", "r")):
            channel = bg_pixels[:, index].astype(np.float32)
            try:
                coeffs, _, _, _ = np.linalg.lstsq(design, channel, rcond=None)
            except Exception:
                return self._fallback_params()

            params[f"a_{channel_name}"] = float(coeffs[0])
            params[f"b_{channel_name}"] = float(coeffs[1])
            params[f"c_{channel_name}"] = float(coeffs[2])

            predicted = design @ coeffs
            ss_res = float(np.sum((channel - predicted) ** 2))
            ss_tot = float(np.sum((channel - np.mean(channel)) ** 2))
            r2_scores.append(1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0)

        params["r2"] = float(np.mean(r2_scores))
        return params

    def _gradient_roi(self, mask: np.ndarray, width: int, height: int) -> tuple[int, int, int, int]:
        coords = cv2.findNonZero(np.where(mask > 127, 255, 0).astype(np.uint8))
        if coords is None:
            return 0, 0, width, height

        x, y, w, h = cv2.boundingRect(coords)
        pad_x = max(w, 16)
        pad_y = max(h, 16)
        return (
            max(0, x - pad_x),
            max(0, y - pad_y),
            min(width, x + w + pad_x),
            min(height, y + h + pad_y),
        )

    def _fallback_params(self) -> dict:
        return {
            "a_b": 0.0,
            "b_b": 0.0,
            "c_b": 255.0,
            "a_g": 0.0,
            "b_g": 0.0,
            "c_g": 255.0,
            "a_r": 0.0,
            "b_r": 0.0,
            "c_r": 255.0,
            "r2": 0.0,
            "type": "fallback",
        }
