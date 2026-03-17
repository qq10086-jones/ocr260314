from __future__ import annotations

from typing import Optional

import cv2
import numpy as np

from app.providers.inpaint.base import InpaintResult
from app.providers.inpaint.poisson_blend import poisson_blend


class PatchSynthesisProvider:
    """Type C background reconstruction using local patch synthesis."""

    def __init__(self, feather_radius: int = 5):
        self.feather_radius = feather_radius

    def inpaint(
        self,
        image: np.ndarray,
        mask: np.ndarray,
        context: Optional[dict] = None,
    ) -> InpaintResult:
        height, width = image.shape[:2]
        mask_binary = np.where(mask > 127, 255, 0).astype(np.uint8)

        contours, _ = cv2.findContours(mask_binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return InpaintResult(image=image, method="patch_synthesis", debug_info={"error": "no mask contours"})

        contour = max(contours, key=cv2.contourArea)
        x, y, region_width, region_height = cv2.boundingRect(contour)

        if x < 10 or y < 10 or x + region_width > width - 10 or y + region_height > height - 10:
            return self._opencv_fallback(image, mask)

        src_region = image[y : y + region_height, x : x + region_width].copy()
        mask_region = mask_binary[y : y + region_height, x : x + region_width]

        search_top = max(0, y - region_height * 2)
        search_bottom = min(height, y + region_height * 3)
        search_left = max(0, x - region_width * 2)
        search_right = min(width, x + region_width * 3)
        search_region = image[search_top:search_bottom, search_left:search_right]

        filled_region = self._patch_match_fill(src_region, mask_region, search_region)

        result = image.copy()
        result[y : y + region_height, x : x + region_width] = poisson_blend(
            filled_region,
            mask_region,
            image[y : y + region_height, x : x + region_width],
        )

        return InpaintResult(
            image=result,
            method="patch_synthesis",
            debug_info={"region": f"{x},{y},{region_width},{region_height}", "blend": "poisson"},
        )

    def _patch_match_fill(
        self,
        src_region: np.ndarray,
        mask_region: np.ndarray,
        search_region: np.ndarray,
    ) -> np.ndarray:
        height, width = src_region.shape[:2]
        mask_bool = mask_region > 0
        if not np.any(mask_bool):
            return src_region

        filled = src_region.copy()
        fill_pixels = np.column_stack(np.where(mask_bool))
        if len(fill_pixels) == 0:
            return src_region

        patch_size = 9
        half = patch_size // 2
        search_height, search_width = search_region.shape[:2]
        if search_height < patch_size or search_width < patch_size:
            return src_region

        for py, px in fill_pixels[::5]:
            if py - half < 0 or py + half >= height or px - half < 0 or px + half >= width:
                continue

            patch = filled[py - half : py + half + 1, px - half : px + half + 1]
            result = cv2.matchTemplate(search_region, patch, cv2.TM_SQDIFF_NORMED)
            min_val, _, min_loc, _ = cv2.minMaxLoc(result)
            if min_val >= 0.5:
                continue

            match_x, match_y = min_loc
            best_match = search_region[match_y : match_y + patch_size, match_x : match_x + patch_size]
            if best_match.shape == patch.shape:
                filled[py, px] = best_match[half, half]

        return filled

    def _opencv_fallback(self, image: np.ndarray, mask: np.ndarray) -> InpaintResult:
        result = cv2.inpaint(image, mask, 3, cv2.INPAINT_TELEA)
        return InpaintResult(
            image=result,
            method="opencv_telea_fallback",
            debug_info={"fallback_reason": "insufficient margin"},
        )
