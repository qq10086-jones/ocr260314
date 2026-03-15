from __future__ import annotations

import cv2
import numpy as np
from pathlib import Path


class QAEvaluator:
    """
    负责评估翻译/擦除任务的质量，并生成可视化调试报告。
    """
    def generate_debug_overlay(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        生成 Mask 叠加图：原图 + 半透明红色遮罩。
        """
        overlay = image.copy()
        # 创建一个全红色的图层
        red_layer = np.zeros_like(image)
        red_layer[:] = [0, 0, 255] # BGR 格式
        
        # 在 Mask 区域应用红色图层
        mask_bool = mask > 0
        overlay[mask_bool] = cv2.addWeighted(image[mask_bool], 0.3, red_layer[mask_bool], 0.7, 0)
        
        return overlay

    def calculate_mask_stats(self, mask: np.ndarray) -> dict[str, float]:
        """
        计算 Mask 的统计数据。
        """
        height, width = mask.shape[:2]
        total_pixels = height * width
        masked_pixels = np.count_nonzero(mask)
        
        # 覆盖率 (通常在 1% ~ 15% 之间是正常的)
        coverage_ratio = (masked_pixels / total_pixels) * 100
        
        return {
            "mask_coverage_ratio": round(coverage_ratio, 4),
            "masked_pixel_count": int(masked_pixels)
        }
