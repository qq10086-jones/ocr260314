from __future__ import annotations

from PIL import ImageFont


def estimate_font(font_path: str, text: str, box_width: float, box_height: float) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, int]:
    target_height = box_height * 0.6 if box_height > 50 else box_height * 0.75
    font_size = max(int(target_height), 10)

    font = _load_font(font_path, font_size)
    avg_char_width = font_size * 0.5

    if len(text) * avg_char_width > box_width * 1.2:
        scale_factor = (box_width * 0.95) / max(len(text) * avg_char_width, 1)
        font_size = max(int(font_size * scale_factor), 10)
        font = _load_font(font_path, font_size)

    return font, font_size


def _load_font(font_path: str, font_size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(font_path, font_size)
    except Exception:
        return ImageFont.load_default()
