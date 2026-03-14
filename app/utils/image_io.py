from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def ensure_image_exists(image_path: str | Path) -> Path:
    path = Path(image_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"输入图片不存在: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"输入路径不是文件: {path}")
    return path


def load_image(image_path: str | Path) -> np.ndarray:
    path = ensure_image_exists(image_path)
    image = cv2.imread(str(path))
    if image is None:
        raise ValueError(f"无法读取图片: {path}")
    return image


def save_image(image_path: str | Path, image: np.ndarray) -> Path:
    path = Path(image_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(path), image)
    if not success:
        raise ValueError(f"无法写入图片: {path}")
    return path
