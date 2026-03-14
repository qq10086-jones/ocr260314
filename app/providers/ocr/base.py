from __future__ import annotations

from typing import Protocol

from app.core.models import OCRBox


class OCRProvider(Protocol):
    def detect(self, image: object) -> list[OCRBox]:
        """Return OCR boxes for the given image."""
