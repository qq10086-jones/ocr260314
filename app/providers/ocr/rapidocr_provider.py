from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
from rapidocr_onnxruntime import RapidOCR

from app.core.models import OCRBox


class RapidOCROCRProvider:
    def __init__(self) -> None:
        self._engine: RapidOCR | None = None

    def detect(self, image: str | Path | np.ndarray) -> list[OCRBox]:
        result, _ = self._get_engine()(image)
        if not result:
            return []

        boxes: list[OCRBox] = []
        for line in result:
            coords = tuple((int(point[0]), int(point[1])) for point in line[0])
            text = str(line[1])
            score = float(line[2])
            boxes.append(OCRBox(box=coords, text=text, score=score))
        return boxes

    def _get_engine(self) -> RapidOCR:
        if self._engine is None:
            self._engine = RapidOCR()
        return self._engine
