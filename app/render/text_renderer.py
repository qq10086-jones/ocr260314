from __future__ import annotations

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.core.models import TranslationTask
from app.render.font_estimator import estimate_font


class TextRenderer:
    def __init__(self, font_path: str) -> None:
        self._font_path = font_path

    def render(self, image: np.ndarray, tasks: list[TranslationTask]) -> np.ndarray:
        base = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("RGBA")
        text_layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_layer)

        for task in tasks:
            self._draw_text(draw, task)

        final = Image.alpha_composite(base, text_layer)
        return cv2.cvtColor(np.array(final.convert("RGB")), cv2.COLOR_RGB2BGR)

    def _draw_text(self, draw: ImageDraw.ImageDraw, task: TranslationTask) -> None:
        xs = [point[0] for point in task.box]
        ys = [point[1] for point in task.box]
        x_min, y_min = min(xs), min(ys)
        x_max, y_max = max(xs), max(ys)
        box_width = x_max - x_min
        box_height = y_max - y_min

        font, font_size = estimate_font(self._font_path, task.translated_text, box_width, box_height)

        try:
            left, top, right, bottom = font.getbbox(task.translated_text)
            text_width = right - left
            text_height = bottom - top
        except Exception:
            text_width = font_size * len(task.translated_text) * 0.6
            text_height = font_size

        color = task.text_color or (0, 0, 0)
        brightness = color[0] * 0.299 + color[1] * 0.587 + color[2] * 0.114
        stroke_width = 2 if font_size >= 24 else 1 if font_size >= 16 else 0
        stroke_color = (255, 255, 255) if brightness < 150 else (0, 0, 0)

        pos_x = x_min + (box_width - text_width) / 2
        pos_y = y_min + (box_height - text_height) / 2 - (text_height * 0.1)

        draw.text(
            (pos_x, pos_y),
            task.translated_text,
            font=font,
            fill=color + (255,),
            stroke_width=stroke_width,
            stroke_fill=stroke_color + (255,),
        )
