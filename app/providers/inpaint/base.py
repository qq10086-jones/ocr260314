from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Optional

import numpy as np


@dataclass
class InpaintResult:
    """统一 Inpaint 结果数据结构"""
    image: np.ndarray
    method: str
    debug_info: Optional[dict] = None


class InpainterProvider(Protocol):
    """Inpaint Provider 接口"""
    def inpaint(self, image: np.ndarray, mask: np.ndarray, context: Optional[dict] = None) -> InpaintResult:
        """Return image with masked regions filled."""
