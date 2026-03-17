from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class QAResult:
    mask_coverage: float
    residual_score: float
    boundary_consistency: float
    render_fit_score: float
    overall_score: float
    warnings: list[str]
    details: dict


class QAEvaluator:
    """
    M9: QA 质量评估器
    
    功能:
    - Mask 覆盖率计算
    - 残留 OCR 检测
    - 边界一致性检测
    - 渲染适配度评估
    - 综合质量评分
    """
    
    def __init__(self, coverage_threshold: float = 20.0):
        self._coverage_threshold = coverage_threshold
    
    def generate_debug_overlay(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """
        生成 Mask 叠加图：原图 + 半透明红色遮罩。
        mask 全零（无文字）时直接返回原图副本。
        """
        overlay = image.copy()
        if mask is None or not np.any(mask):
            return overlay

        red_layer = np.zeros_like(image)
        red_layer[:] = [0, 0, 255]

        mask_bool = mask > 0
        blended = cv2.addWeighted(
            image[mask_bool].reshape(-1, 1, 3), 0.3,
            red_layer[mask_bool].reshape(-1, 1, 3), 0.7,
            0,
        ).reshape(-1, 3)
        overlay[mask_bool] = blended

        return overlay

    def calculate_mask_stats(self, mask: np.ndarray) -> dict[str, float]:
        """
        计算 Mask 的统计数据。
        """
        height, width = mask.shape[:2]
        total_pixels = height * width
        masked_pixels = np.count_nonzero(mask)
        
        coverage_ratio = (masked_pixels / total_pixels) * 100 if total_pixels > 0 else 0
        
        return {
            "mask_coverage_ratio": round(coverage_ratio, 4),
            "masked_pixel_count": int(masked_pixels)
        }
    
    def evaluate(
        self,
        original: np.ndarray,
        processed: np.ndarray,
        mask: np.ndarray,
        ocr_result: Optional[list] = None,
    ) -> QAResult:
        """
        综合质量评估
        """
        warnings = []
        details = {}
        
        coverage = self._evaluate_coverage(mask, original)
        details["coverage"] = coverage
        
        if coverage > self._coverage_threshold:
            warnings.append(f"Mask coverage too high: {coverage:.1f}%")
        
        residual = self._evaluate_residual(original, processed, mask, ocr_result)
        details["residual"] = residual
        
        boundary = self._evaluate_boundary_consistency(processed, mask)
        details["boundary"] = boundary
        
        render_fit = self._evaluate_render_fit(processed, mask)
        details["render_fit"] = render_fit
        
        overall = self._calculate_overall_score(coverage, residual, boundary, render_fit)
        
        return QAResult(
            mask_coverage=coverage,
            residual_score=residual,
            boundary_consistency=boundary,
            render_fit_score=render_fit,
            overall_score=overall,
            warnings=warnings,
            details=details,
        )
    
    def _evaluate_coverage(self, mask: np.ndarray, image: np.ndarray) -> float:
        """评估 Mask 覆盖率"""
        total_pixels = mask.shape[0] * mask.shape[1]
        masked_pixels = np.count_nonzero(mask)
        return (masked_pixels / total_pixels) * 100 if total_pixels > 0 else 0
    
    def _evaluate_residual(
        self,
        original: np.ndarray,
        processed: np.ndarray,
        mask: np.ndarray,
        ocr_result: Optional[list],
    ) -> float:
        """评估 Mask 区域文字是否被干净抹除。

        原理：在 mask 区域内，对 processed 图做边缘检测。
        残留文字会留下高频边缘；干净背景边缘密度低。
        score=1.0 表示无残留，score=0.0 表示满是边缘（残留严重）。
        """
        if mask.sum() == 0:
            return 1.0

        mask_bool = mask > 0
        proc_gray = cv2.cvtColor(processed, cv2.COLOR_BGR2GRAY)

        edges = cv2.Canny(proc_gray, 50, 150)
        edge_density_in_mask = edges[mask_bool].mean() / 255.0

        # 以 mask 外区域的边缘密度作为自然背景基线
        bg_mask = ~mask_bool
        if bg_mask.any():
            baseline = edges[bg_mask].mean() / 255.0
        else:
            baseline = 0.05

        # 超出基线的部分视为残留，归一化到 [0,1]
        excess = max(0.0, edge_density_in_mask - baseline)
        score = 1.0 - min(1.0, excess / 0.3)

        return round(score, 4)
    
    def _evaluate_boundary_consistency(self, image: np.ndarray, mask: np.ndarray) -> float:
        """评估边界一致性"""
        if mask.sum() == 0:
            return 1.0
        
        mask_bool = (mask > 0).astype(np.uint8)
        
        contours, _ = cv2.findContours(mask_bool, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return 1.0
        
        total_perimeter = sum(cv2.arcLength(c, True) for c in contours)
        total_area = sum(cv2.contourArea(c) for c in contours)
        
        if total_area == 0:
            return 0.5
        
        compactness = (4 * np.pi * total_area) / (total_perimeter ** 2) if total_perimeter > 0 else 0
        
        score = min(1.0, compactness)
        
        return round(score, 4)
    
    def _evaluate_render_fit(self, image: np.ndarray, mask: np.ndarray) -> float:
        """评估渲染适配度"""
        if mask.sum() == 0:
            return 1.0
        
        mask_bool = mask > 0
        
        processed_region = image[mask_bool]
        
        if len(processed_region) == 0:
            return 0.5
        
        variance = np.var(processed_region, axis=0).mean()
        
        score = min(1.0, variance / 100.0)
        
        return round(score, 4)
    
    def _calculate_overall_score(
        self,
        coverage: float,
        residual: float,
        boundary: float,
        render_fit: float,
    ) -> float:
        """计算综合评分"""
        coverage_penalty = max(0, (coverage - 10) / 10) if coverage > 10 else 0
        
        overall = (
            residual * 0.4 +
            boundary * 0.3 +
            render_fit * 0.2 +
            (1 - coverage_penalty) * 0.1
        )
        
        return round(overall, 4)
    
    def generate_qa_report(
        self,
        original: np.ndarray,
        processed: np.ndarray,
        mask: np.ndarray,
        output_path: Path,
        ocr_result: Optional[list] = None,
    ) -> dict:
        """生成 QA 报告"""
        result = self.evaluate(original, processed, mask, ocr_result)
        
        report = {
            "overall_score": result.overall_score,
            "warnings": result.warnings,
            "details": result.details,
        }
        
        return report
