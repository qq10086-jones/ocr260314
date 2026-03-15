from __future__ import annotations

import cv2
import numpy as np
from app.core.models import OCRBox


class MaskRefiner:
    def __init__(self, expand_pixels: int = 2):
        self._expand_pixels = expand_pixels

    def refine_mask(self, image: np.ndarray, boxes: list[OCRBox]) -> np.ndarray:
        height, width = image.shape[:2]
        final_mask = np.zeros((height, width), dtype=np.uint8)

        for box in boxes:
            points = np.array(box.box, dtype=np.int32)
            x, y, w, h = cv2.boundingRect(points)
            
            # ROI 提取
            pad = 5
            y1, y2 = max(0, y - pad), min(height, y + h + pad)
            x1, x2 = max(0, x - pad), min(width, x + w + pad)
            roi = image[y1:y2, x1:x2]
            if roi.size == 0: continue

            # --- V3 极限精度算法 ---
            
            # 1. 局部对比度受限自适应直方图均衡化 (CLAHE)
            # 让笔画边缘在复杂背景中更锐利
            lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8,8))
            cl = clahe.apply(l)
            enhanced_roi = cv2.merge((cl, a, b))
            enhanced_roi = cv2.cvtColor(enhanced_roi, cv2.COLOR_LAB2BGR)
            
            # 2. 边缘引导分割 (Morphological Gradient)
            # 这能精准找到笔画的轮廓
            gray = cv2.cvtColor(enhanced_roi, cv2.COLOR_BGR2GRAY)
            kernel_grad = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            gradient = cv2.morphologyEx(gray, cv2.MORPH_GRADIENT, kernel_grad)
            
            # 3. 多尺度二值化融合
            # 结合大津法和自适应阈值，捕捉不同粗细的笔画
            _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            thresh_adapt = cv2.adaptiveThreshold(
                gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 15, 10
            )
            
            # 融合三路信号
            combined = cv2.bitwise_or(thresh_otsu, thresh_adapt)
            combined = cv2.bitwise_or(combined, gradient)

            # 4. 精确范围锁定 (裁剪到 OCR 框内)
            local_poly_mask = np.zeros(gray.shape, dtype=np.uint8)
            local_points = points - [x1, y1]
            cv2.fillPoly(local_poly_mask, [local_points], 255)
            
            # 关键：只在 OCR 框内进行分割，并剔除离散噪点
            refined_roi = cv2.bitwise_and(combined, local_poly_mask)
            
            # 5. 极小化精准膨胀 (Dilation)
            # 不再使用大比例膨胀，改为固定小像素或极小比例 (3% 字高)
            rad = max(1, int(h * 0.04)) 
            kernel_refine = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (rad, rad))
            refined_roi = cv2.dilate(refined_roi, kernel_refine, iterations=1)
            
            # 6. 孔洞填充 (Closing)
            # 让笔画内部更实，不漏掉字心
            refined_roi = cv2.morphologyEx(refined_roi, cv2.MORPH_CLOSE, kernel_refine)

            # 写入全局 Mask
            final_mask[y1:y2, x1:x2] = cv2.bitwise_or(final_mask[y1:y2, x1:x2], refined_roi)

        return final_mask
