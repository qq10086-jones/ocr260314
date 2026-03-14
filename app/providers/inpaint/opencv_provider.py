from __future__ import annotations

import cv2
import numpy as np

from app.core.models import OCRBox


class OpenCVInpainter:
    def __init__(self, expand_pixels: int = 8, radius: int = 3) -> None:
        self._expand_pixels = expand_pixels
        self._radius = radius

    def build_mask(self, image: np.ndarray, boxes: list[OCRBox]) -> np.ndarray:
        height, width = image.shape[:2]
        mask = np.zeros((height, width), dtype=np.uint8)

        for box in boxes:
            points = np.array(box.box, dtype=np.int32)
            cv2.fillPoly(mask, [points], 255)

        if self._expand_pixels > 0:
            kernel = np.ones((self._expand_pixels, self._expand_pixels), np.uint8)
            mask = cv2.dilate(mask, kernel, iterations=1)
        return mask

    def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        return cv2.inpaint(image, mask, self._radius, cv2.INPAINT_TELEA)
