from __future__ import annotations

import cv2
import numpy as np

from app.core.models import QuadBox


def get_smart_text_color(image: np.ndarray, box: QuadBox) -> tuple[int, int, int]:
    xs = [int(point[0]) for point in box]
    ys = [int(point[1]) for point in box]
    x_min, x_max = max(0, min(xs)), min(image.shape[1], max(xs))
    y_min, y_max = max(0, min(ys)), min(image.shape[0], max(ys))

    roi = image[y_min:y_max, x_min:x_max]
    if roi.size == 0:
        return (0, 0, 0)

    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    count_white = int(np.sum(mask == 255))
    count_black = int(np.sum(mask == 0))
    text_mask = mask == 255 if count_white < count_black else mask == 0

    if int(np.sum(text_mask)) == 0:
        center = image[y_min + roi.shape[0] // 2, x_min + roi.shape[1] // 2]
        return (int(center[2]), int(center[1]), int(center[0]))

    mean_val = cv2.mean(roi, mask=text_mask.astype(np.uint8))
    return (int(mean_val[2]), int(mean_val[1]), int(mean_val[0]))
