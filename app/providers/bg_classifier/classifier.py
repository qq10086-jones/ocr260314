from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import cv2
import numpy as np


class BackgroundType(Enum):
    FLAT = "flat"           # 纯色背景
    GRADIENT = "gradient"   # 渐变背景
    TEXTURE = "texture"     # 纹理背景
    COMPLEX = "complex"     # 复杂背景


@dataclass
class BgClassifierResult:
    bg_type: BackgroundType
    confidence: float
    dominant_color: Optional[tuple[int, int, int]] = None
    gradient_params: Optional[dict] = None
    texture_period_px: Optional[float] = None
    debug_info: Optional[dict] = None


class BackgroundClassifier:
    def __init__(self, variance_threshold: float = 12.0, gradient_r2_threshold: float = 0.80):
        self.variance_threshold = variance_threshold
        self.gradient_r2_threshold = gradient_r2_threshold

    def classify(self, image: np.ndarray, mask: np.ndarray) -> BgClassifierResult:
        h, w = image.shape[:2]

        if mask is None:
            mask = np.zeros((h, w), dtype=np.uint8)

        bg_pixels, bg_coords = self._sample_background(image, mask)

        if len(bg_pixels) == 0:
            return BgClassifierResult(
                bg_type=BackgroundType.COMPLEX,
                confidence=0.5,
                debug_info={"error": "no background pixels sampled"}
            )

        variance = self._compute_variance(bg_pixels)

        if variance < self.variance_threshold:
            dominant = self._compute_dominant_color(bg_pixels)
            return BgClassifierResult(
                bg_type=BackgroundType.FLAT,
                confidence=1.0 - (variance / self.variance_threshold),
                dominant_color=dominant,
                debug_info={"variance": float(variance)}
            )

        gradient_result = self._test_gradient(bg_pixels, bg_coords)
        if gradient_result is not None:
            return gradient_result

        texture_result = self._test_texture(bg_pixels)
        if texture_result is not None:
            return texture_result

        return BgClassifierResult(
            bg_type=BackgroundType.COMPLEX,
            confidence=0.5,
            dominant_color=self._compute_dominant_color(bg_pixels),
            debug_info={"variance": float(variance)}
        )

    def _sample_background(self, image: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """
        返回 (pixels, coords)，coords shape=(N,2)，列为 (x, y)。
        mask 为 None 或全零时，采样图片四周边框区域作为背景。
        """
        h, w = image.shape[:2]

        if mask.sum() == 0:
            border_width = min(50, h // 4, w // 4)
            ys, xs = np.where(np.ones((h, w), dtype=bool))
            border_mask = (
                (ys < border_width) |
                (ys >= h - border_width) |
                (xs < border_width) |
                (xs >= w - border_width)
            )
            bg_ys = ys[border_mask]
            bg_xs = xs[border_mask]
        else:
            mask_expanded = cv2.dilate(mask, np.ones((21, 21), np.uint8))
            valid = mask_expanded == 0
            bg_ys, bg_xs = np.where(valid)

        if len(bg_ys) == 0:
            return np.empty((0, 3), dtype=np.uint8), np.empty((0, 2), dtype=np.int32)

        limit = min(10000, len(bg_ys))
        idx = np.random.choice(len(bg_ys), limit, replace=False) if len(bg_ys) > limit else np.arange(len(bg_ys))

        bg_ys = bg_ys[idx]
        bg_xs = bg_xs[idx]

        pixels = image[bg_ys, bg_xs].reshape(-1, 3)
        coords = np.column_stack([bg_xs, bg_ys])  # (N, 2): x, y

        return pixels, coords

    def _compute_variance(self, pixels: np.ndarray) -> float:
        return float(np.std(pixels, axis=0).max())

    def _compute_dominant_color(self, pixels: np.ndarray) -> tuple[int, int, int]:
        means = np.mean(pixels, axis=0)
        return (int(means[0]), int(means[1]), int(means[2]))

    def _test_gradient(self, bg_pixels: np.ndarray, bg_coords: np.ndarray) -> Optional[BgClassifierResult]:
        if len(bg_pixels) < 100:
            return None

        try:
            x_coords = bg_coords[:, 0].astype(np.float32)
            y_coords = bg_coords[:, 1].astype(np.float32)
            x_coords /= max(float(np.max(x_coords)) if len(x_coords) else 1.0, 1.0)
            y_coords /= max(float(np.max(y_coords)) if len(y_coords) else 1.0, 1.0)

            r2_scores = []
            A = np.column_stack([x_coords, y_coords, np.ones_like(x_coords)])

            for c in range(3):
                channel = bg_pixels[:, c].astype(np.float32)
                ss_tot = np.sum((channel - np.mean(channel)) ** 2)
                if ss_tot < 1.0:
                    # 该通道无变化，跳过（不计入 R² 平均）
                    continue
                try:
                    coeffs, _, _, _ = np.linalg.lstsq(A, channel, rcond=None)
                    predicted = A @ coeffs
                    ss_res = np.sum((channel - predicted) ** 2)
                    r2 = 1.0 - (ss_res / ss_tot)
                    r2_scores.append(r2)
                except Exception:
                    r2_scores.append(0.0)

            if not r2_scores:
                return None

            # 只要有一个通道呈明显线性梯度，就认为是渐变背景
            avg_r2 = float(np.mean(r2_scores))

            if avg_r2 >= self.gradient_r2_threshold:
                return BgClassifierResult(
                    bg_type=BackgroundType.GRADIENT,
                    confidence=avg_r2,
                    gradient_params={"r2": avg_r2, "r2_per_channel": [float(r) for r in r2_scores]},
                    debug_info={"avg_r2": avg_r2}
                )
        except Exception:
            pass

        return None

    def _test_texture(self, bg_pixels: np.ndarray) -> Optional[BgClassifierResult]:
        if len(bg_pixels) < 100:
            return None

        try:
            gray = np.mean(bg_pixels, axis=1).astype(np.uint8)
            gray = gray[:min(256, len(gray))]
            size = int(np.sqrt(len(gray)))
            if size < 32:
                return None

            gray = gray[:size * size].reshape(size, size)

            fft = np.fft.fft2(gray)
            magnitude = np.abs(np.fft.fftshift(fft))

            center = size // 2
            magnitude[center - 2:center + 2, center - 2:center + 2] = 0

            peaks = np.unravel_index(np.argsort(magnitude.ravel())[-5:], magnitude.shape)
            if len(peaks[0]) > 0:
                max_magnitude = magnitude[peaks[0][0], peaks[1][0]]
                if max_magnitude > magnitude.mean() * 3:
                    period = float(size / (abs(peaks[0][0] - center) + 1)) if peaks[0][0] != center else None
                    return BgClassifierResult(
                        bg_type=BackgroundType.TEXTURE,
                        confidence=0.7,
                        texture_period_px=period,
                        debug_info={"peak_magnitude": float(max_magnitude)}
                    )
        except Exception:
            pass

        return None
