from __future__ import annotations

import cv2
import numpy as np
from app.core.models import OCRBox


class MaskRefinerV4:
    """
    V4 专家版：基于 GrabCut (Graph Cut + GMM) 的能量最小化分割算法。
    专治复杂背景下的文字提取。
    """
    def __init__(self, iterations: int = 5):
        self._iterations = iterations

    def refine_mask(self, image: np.ndarray, boxes: list[OCRBox]) -> np.ndarray:
        print(f"[V4 GrabCut] 正在启动高级分割，处理 {len(boxes)} 个字块...")
        height, width = image.shape[:2]
        final_mask = np.zeros((height, width), dtype=np.uint8)

        for box in boxes:
            points = np.array(box.box, dtype=np.int32)
            x, y, w, h = cv2.boundingRect(points)
            
            # GrabCut 需要一定的背景上下文，padding 设为字高的 10%
            pad = max(5, int(h * 0.1))
            y1, y2 = max(0, y - pad), min(height, y + h + pad)
            x1, x2 = max(0, x - pad), min(width, x + w + pad)
            
            roi = image[y1:y2, x1:x2]
            if roi.size == 0 or roi.shape[0] < 3 or roi.shape[1] < 3:
                continue

            # 1. 初始化 GrabCut 掩码
            # GC_BGD (0): 确定背景, GC_FGD (1): 确定前景
            # GC_PR_BGD (2): 可能背景, GC_PR_FGD (3): 可能前景
            mask_gc = np.zeros(roi.shape[:2], np.uint8)
            
            # 将 ROI 全域设为“可能背景”
            mask_gc.fill(cv2.GC_PR_BGD)
            
            # 将 OCR Box 内部设为“可能前景”
            # 注意：这里的坐标要相对于 ROI
            local_x, local_y = max(0, x - x1), max(0, y - y1)
            local_w, local_h = min(w, roi.shape[1] - local_x), min(h, roi.shape[0] - local_y)
            rect = (local_x, local_y, local_w, local_h)
            
            # 2. 运行 GrabCut
            bgdModel = np.zeros((1, 65), np.float64)
            fgdModel = np.zeros((1, 65), np.float64)
            
            try:
                # 使用矩形模式初始化 GrabCut
                cv2.grabCut(roi, mask_gc, rect, bgdModel, fgdModel, self._iterations, cv2.GC_INIT_WITH_RECT)
                
                # 3. 提取结果
                # 0 和 2 代表背景，1 和 3 代表前景
                bin_mask = np.where((mask_gc == 2) | (mask_gc == 0), 0, 1).astype('uint8') * 255
                
                # 4. 后处理：只保留 OCR 框内部且具有文字特征的部分
                # 再次用矩形裁剪一次，确保没有越界
                local_poly = np.zeros(roi.shape[:2], np.uint8)
                local_points = points - [x1, y1]
                cv2.fillPoly(local_poly, [local_points], 255)
                
                refined_roi = cv2.bitwise_and(bin_mask, local_poly)
                
                # 5. 形态学精修
                # 填充字内空洞
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                refined_roi = cv2.morphologyEx(refined_roi, cv2.MORPH_CLOSE, kernel)
                
                # 极小幅度膨胀 (2% 字高)
                rad = max(1, int(h * 0.02))
                kernel_dilate = np.ones((rad, rad), np.uint8)
                refined_roi = cv2.dilate(refined_roi, kernel_dilate, iterations=1)

                # 写入全局 Mask
                final_mask[y1:y2, x1:x2] = cv2.bitwise_or(final_mask[y1:y2, x1:x2], refined_roi)
                
            except Exception as e:
                print(f"[V4] 字块处理跳过: {e}")
                continue

        print("[V4 GrabCut] 全局精细化 Mask 构建成功。")
        return final_mask
