from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class TextType(Enum):
    NORMAL = "normal"
    TITLE = "title"
    BUTTON = "button"
    TAG = "tag"
    VERTICAL = "vertical"


class Alignment(Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"


@dataclass
class TextBlock:
    id: str
    original_box: list
    translated_text: str
    text_type: TextType = TextType.NORMAL
    alignment: Alignment = Alignment.CENTER
    estimated_font_size: int = 16
    line_count: int = 1
    wrapped_lines: list[str] = None
    
    def __post_init__(self):
        if self.wrapped_lines is None:
            self.wrapped_lines = [self.translated_text]


@dataclass
class LayoutPlan:
    blocks: list[TextBlock]
    total_width: int
    total_height: int
    debug_info: Optional[dict] = None


class LayoutPlanner:
    """
    M7: 布局规划器 v1
    
    功能:
    - 文本块分组
    - 字号估算
    - 对齐估算
    - 自动换行
    - 溢出检测
    """
    
    def __init__(
        self,
        max_width_ratio: float = 0.9,
        min_font_size: int = 8,
        max_font_size: int = 72,
    ):
        self._max_width_ratio = max_width_ratio
        self._min_font_size = min_font_size
        self._max_font_size = max_font_size
    
    def plan(self, tasks: list, image_width: int, image_height: int) -> LayoutPlan:
        blocks = []
        
        for task in tasks:
            block = self._create_block(task, image_width, image_height)
            blocks.append(block)
        
        blocks = self._group_blocks(blocks)
        
        return LayoutPlan(
            blocks=blocks,
            total_width=image_width,
            total_height=image_height,
            debug_info={"block_count": len(blocks)}
        )
    
    def _create_block(self, task, image_width: int, image_height: int) -> TextBlock:
        box = task.box if hasattr(task, 'box') else task.get('box', [])
        text = task.translated_text if hasattr(task, 'translated_text') else task.get('translated_text', '')
        
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        
        x_min, y_min = min(xs), min(ys)
        x_max, y_max = max(xs), max(ys)
        width = x_max - x_min
        height = y_max - y_min
        
        text_type = self._detect_text_type(text, width, height, image_width)
        
        alignment = self._estimate_alignment(box, image_width)
        
        font_size = self._estimate_font_size(text, width, height)
        
        wrapped = self._wrap_text(text, width, font_size)
        
        return TextBlock(
            id=task.id if hasattr(task, 'id') else task.get('id', ''),
            original_box=box,
            translated_text=text,
            text_type=text_type,
            alignment=alignment,
            estimated_font_size=font_size,
            line_count=len(wrapped),
            wrapped_lines=wrapped,
        )
    
    def _detect_text_type(self, text: str, width: int, height: int, image_width: int) -> TextType:
        if len(text) <= 3 and width < image_width * 0.1:
            return TextType.TAG
        
        if width > image_width * 0.3:
            return TextType.TITLE
        
        if any(char in text for char in '按钮确认取消注册登录'):
            return TextType.BUTTON
        
        if any('\u3040' <= char <= '\u309F' or '\u30A0' <= char <= '\u30FF' for char in text):
            if height > width:
                return TextType.VERTICAL
        
        return TextType.NORMAL
    
    def _estimate_alignment(self, box: list, image_width: int) -> Alignment:
        """基于文本框中心在图片中的水平位置估算对齐方式。

        将图片水平三等分：左 1/3 → LEFT，右 1/3 → RIGHT，中间 → CENTER。
        """
        if image_width <= 0:
            return Alignment.CENTER

        xs = [p[0] for p in box]
        x_min, x_max = min(xs), max(xs)
        x_center = (x_min + x_max) / 2.0
        ratio = x_center / image_width

        if ratio < 0.35:
            return Alignment.LEFT
        if ratio > 0.65:
            return Alignment.RIGHT
        return Alignment.CENTER
    
    def _estimate_font_size(self, text: str, box_width: int, box_height: int) -> int:
        char_count = len(text)
        
        width_based = box_width / (char_count * 0.6) if char_count > 0 else box_width
        
        height_based = box_height * 0.8
        
        font_size = min(width_based, height_based)
        font_size = max(self._min_font_size, min(self._max_font_size, int(font_size)))
        
        return font_size
    
    def _wrap_text(self, text: str, max_width: int, font_size: int) -> list[str]:
        if not text:
            return [text]
        
        char_width = font_size * 0.6
        max_chars = max(1, int(max_width / char_width))
        
        if len(text) <= max_chars:
            return [text]
        
        lines = []
        current_line = []
        current_width = 0
        
        for char in text:
            char_w = char_width
            
            if current_width + char_w > max_width and current_line:
                lines.append(''.join(current_line))
                current_line = [char]
                current_width = char_w
            else:
                current_line.append(char)
                current_width += char_w
        
        if current_line:
            lines.append(''.join(current_line))
        
        return lines if lines else [text]
    
    def _group_blocks(self, blocks: list[TextBlock]) -> list[TextBlock]:
        return sorted(blocks, key=lambda b: min(p[1] for p in b.original_box))
    
    def detect_overflow(self, block: TextBlock, box_width: int) -> bool:
        total_text_width = block.estimated_font_size * 0.6 * len(block.translated_text)
        return total_text_width > box_width * 1.2
