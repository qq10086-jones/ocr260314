from __future__ import annotations

import cv2
import numpy as np

from app.core.models import OCRBox


class MaskRefinerV4:
    """
    V4 自适应文字 Mask 精炼器。

    算法选择逻辑（基于 Otsu 双峰分析）：

      text_brightness < 80   → dark_on_light  → Otsu 反向二值化
      text_brightness > 180  → light_on_dark  → Otsu 正向二值化
      80 ≤ brightness ≤ 180  → colored        → GrabCut (Otsu-seeded)

    阴影处理：
      将 polygon 外扩 shadow_pad (6% 字高, min 4px) 后再裁剪，
      让 mask 能覆盖字形轮廓之外的阴影/发光效果。
    """

    def __init__(self, iterations: int = 5):
        self._grabcut_iters = iterations

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def refine_mask(self, image: np.ndarray, boxes: list[OCRBox]) -> np.ndarray:
        h_img, w_img = image.shape[:2]
        final_mask = np.zeros((h_img, w_img), dtype=np.uint8)

        counts = {"dark_on_light": 0, "light_on_dark": 0, "colored": 0}

        for box in boxes:
            text_type = self._process_box(image, box, final_mask, h_img, w_img)
            if text_type:
                counts[text_type] += 1

        total = sum(counts.values())
        if total > 0:
            print(
                f"[V4] 字块算法分布 — "
                f"Otsu深色:{counts['dark_on_light']} "
                f"Otsu浅色:{counts['light_on_dark']} "
                f"GrabCut:{counts['colored']}  共{total}块"
            )
        return final_mask

    # ------------------------------------------------------------------
    # Per-box pipeline
    # ------------------------------------------------------------------

    def _process_box(
        self,
        image: np.ndarray,
        box: OCRBox,
        final_mask: np.ndarray,
        img_h: int,
        img_w: int,
    ) -> str | None:
        points = np.array(box.box, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(points)

        # GrabCut 需要足够的背景 context；Otsu 系也受益于较大 padding
        pad = max(15, int(h * 0.30))
        y1 = max(0, y - pad)
        y2 = min(img_h, y + h + pad)
        x1 = max(0, x - pad)
        x2 = min(img_w, x + w + pad)

        roi = image[y1:y2, x1:x2]
        if roi.size == 0 or roi.shape[0] < 3 or roi.shape[1] < 3:
            return None

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        local_pts = points - np.array([x1, y1], dtype=np.int32)

        # 1. 分类文字类型
        text_type = self._classify(roi_gray, local_pts)

        # 2. 生成 ROI 级 bin mask
        if text_type == "dark_on_light":
            bin_mask = self._otsu_mask(roi_gray, invert=True, box_h=h)
        elif text_type == "light_on_dark":
            bin_mask = self._otsu_mask(roi_gray, invert=False, box_h=h)
        else:
            bin_mask = self._grabcut_mask(roi, roi_gray, local_pts, w, h)

        if bin_mask is None:
            return None

        # 3. 用外扩 polygon 裁剪（保留阴影区域）
        shadow_pad = max(4, int(h * 0.06))
        clip_poly = self._expanded_poly_mask(roi_gray.shape, local_pts, shadow_pad)
        refined = cv2.bitwise_and(bin_mask, clip_poly)

        # 4. 形态学：填洞 + 轻度膨胀
        refined = self._morph_cleanup(refined, h)

        # 5. 写入全局 mask
        final_mask[y1:y2, x1:x2] = cv2.bitwise_or(
            final_mask[y1:y2, x1:x2], refined
        )
        return text_type

    # ------------------------------------------------------------------
    # Text type classification
    # ------------------------------------------------------------------

    def _classify(self, roi_gray: np.ndarray, local_pts: np.ndarray) -> str:
        """
        在 OCR polygon 内部采样像素，用 Otsu 双峰分析判断文字类型。

        Otsu 最大化类间方差：σ²_B = ω₁ω₂(μ₁ - μ₂)²
        少数派（占比 < 45%）的像素群即为笔画，其均值决定文字亮度。
        """
        poly_mask = np.zeros(roi_gray.shape, dtype=np.uint8)
        cv2.fillPoly(poly_mask, [local_pts], 1)
        text_pixels = roi_gray[poly_mask > 0]

        if len(text_pixels) < 20:
            return "colored"

        # 对文字区域像素做 Otsu 分割
        pixel_col = text_pixels.reshape(-1, 1)
        thresh_val, _ = cv2.threshold(
            pixel_col, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )

        dark_px = text_pixels[text_pixels < thresh_val]
        light_px = text_pixels[text_pixels >= thresh_val]

        if len(dark_px) == 0 or len(light_px) == 0:
            return "colored"

        dark_ratio = len(dark_px) / len(text_pixels)

        # 少数派 < 45% → 该少数派是笔画
        if dark_ratio < 0.45:
            text_brightness = float(dark_px.mean())
        elif dark_ratio > 0.55:
            text_brightness = float(light_px.mean())
        else:
            # 接近 50/50：可能是彩色字或对比度不足
            return "colored"

        if text_brightness < 80:
            return "dark_on_light"
        if text_brightness > 180:
            return "light_on_dark"
        return "colored"

    # ------------------------------------------------------------------
    # Mask generation — Otsu path
    # ------------------------------------------------------------------

    def _otsu_mask(
        self, roi_gray: np.ndarray, invert: bool, box_h: int
    ) -> np.ndarray:
        """
        对小字（< 20px）用自适应阈值；大字用全局 Otsu。
        自适应阈值对局部对比度变化更鲁棒，适合小号正文。
        """
        if box_h < 20:
            block = max(11, (box_h // 2) * 2 + 1)
            mode = (
                cv2.THRESH_BINARY_INV if invert else cv2.THRESH_BINARY
            )
            return cv2.adaptiveThreshold(
                roi_gray, 255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                mode,
                block,
                4,
            )

        flags = (
            cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            if invert
            else cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        _, mask = cv2.threshold(roi_gray, 0, 255, flags)
        return mask

    # ------------------------------------------------------------------
    # Mask generation — GrabCut path (Otsu-seeded)
    # ------------------------------------------------------------------

    def _grabcut_mask(
        self,
        roi: np.ndarray,
        roi_gray: np.ndarray,
        local_pts: np.ndarray,
        box_w: int,
        box_h: int,
    ) -> np.ndarray | None:
        """
        GrabCut 改进版：先用 Otsu 生成粗 seed，再用矩形模式精化。
        Otsu seed 给 GrabCut 提供了更准确的初始前背景估计，
        减少 GMM 被白色背景主导的问题。
        """
        mask_gc = np.zeros(roi.shape[:2], np.uint8)
        mask_gc.fill(cv2.GC_PR_BGD)

        # 框内区域标为"可能前景"
        cv2.fillPoly(mask_gc, [local_pts], cv2.GC_PR_FGD)

        # 用 Otsu 找到高置信前景像素，标为 GC_FGD
        _, otsu = cv2.threshold(
            roi_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
        )
        poly_region = np.zeros(roi_gray.shape, np.uint8)
        cv2.fillPoly(poly_region, [local_pts], 1)
        confident_fg = (otsu == 255) & (poly_region == 1)
        mask_gc[confident_fg] = cv2.GC_FGD

        lx = max(0, int(local_pts[:, 0].min()))
        ly = max(0, int(local_pts[:, 1].min()))
        lw = max(1, int(local_pts[:, 0].max()) - lx)
        lh = max(1, int(local_pts[:, 1].max()) - ly)
        rect = (lx, ly, lw, lh)

        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)

        try:
            cv2.grabCut(
                roi, mask_gc, rect, bgd, fgd,
                self._grabcut_iters, cv2.GC_INIT_WITH_RECT,
            )
            bin_mask = np.where(
                (mask_gc == cv2.GC_BGD) | (mask_gc == cv2.GC_PR_BGD), 0, 255
            ).astype(np.uint8)
            return bin_mask
        except Exception as e:
            # GrabCut 失败时回退到 Otsu
            _, fallback = cv2.threshold(
                roi_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU
            )
            return fallback

    # ------------------------------------------------------------------
    # Shadow-aware polygon clip
    # ------------------------------------------------------------------

    def _expanded_poly_mask(
        self,
        shape: tuple,
        local_pts: np.ndarray,
        expand_px: int,
    ) -> np.ndarray:
        """
        将 OCR polygon 向外膨胀 expand_px 像素，用于覆盖阴影/光晕。
        椭圆核保证各方向均匀扩展。
        """
        poly = np.zeros(shape, dtype=np.uint8)
        cv2.fillPoly(poly, [local_pts], 255)
        k = expand_px * 2 + 1
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        return cv2.dilate(poly, kernel)

    # ------------------------------------------------------------------
    # Morphological cleanup
    # ------------------------------------------------------------------

    def _morph_cleanup(self, mask: np.ndarray, box_h: int) -> np.ndarray:
        # 填洞（闭运算）
        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k_close)

        # 轻度膨胀：3% 字高，至少 2px，保证细笔画不断裂
        dil = max(2, int(box_h * 0.03))
        k_dil = np.ones((dil, dil), np.uint8)
        mask = cv2.dilate(mask, k_dil, iterations=1)

        return mask
