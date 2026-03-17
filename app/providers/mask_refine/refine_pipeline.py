from __future__ import annotations

import cv2
from dataclasses import dataclass, field
from typing import Optional

import numpy as np


@dataclass
class ROIFeatures:
    gray: np.ndarray
    enhanced_gray: np.ndarray
    lab: np.ndarray
    hsv: np.ndarray
    edge_density: float
    local_contrast: float
    text_stroke_width: float
    bbox: tuple[int, int, int, int]


@dataclass
class CandidateMask:
    name: str
    mask: np.ndarray
    score: float = 0.0


@dataclass
class RefinedMaskResult:
    glyph_mask: np.ndarray
    effect_mask: np.ndarray
    final_mask: np.ndarray
    debug_info: dict = field(default_factory=dict)


class MaskRefinePipeline:
    """
    M5: Mask 精炼 Pipeline v1
    
    流程:
    1. ROI 特征提取
    2. 候选 Mask 生成
    3. 候选融合
    4. 自适应扩展
    """
    
    def __init__(
        self,
        enable_effect_detection: bool = True,
        debug: bool = False,
    ):
        self.enable_effect_detection = enable_effect_detection
        self.debug = debug
    
    def refine(
        self,
        image: np.ndarray,
        ocr_boxes: list,
        global_mask: Optional[np.ndarray] = None,
    ) -> RefinedMaskResult:
        from app.core.models import OCRBox
        
        h_img, w_img = image.shape[:2]
        final_combined = np.zeros((h_img, w_img), dtype=np.uint8)
        final_glyph = np.zeros((h_img, w_img), dtype=np.uint8)
        final_effect = np.zeros((h_img, w_img), dtype=np.uint8)
        
        debug_info = {"boxes": []}
        
        for box in ocr_boxes:
            if isinstance(box, dict):
                box = OCRBox(box=box.get("box", []), text=box.get("text", ""), score=box.get("score", 0))
            
            features = self._extract_features(image, box)
            
            candidates = self._generate_candidates(image, box, features)
            
            fused = self._fuse_candidates(candidates, features)
            
            expanded = self._adaptive_expand(fused, features)
            
            if self.enable_effect_detection:
                effect = self._detect_effect(image, box, features)
            else:
                effect = np.zeros_like(expanded)

            if effect.shape != expanded.shape:
                normalized_effect = np.zeros_like(expanded)
                overlap_h = min(effect.shape[0], expanded.shape[0])
                overlap_w = min(effect.shape[1], expanded.shape[1])
                normalized_effect[:overlap_h, :overlap_w] = effect[:overlap_h, :overlap_w]
                effect = normalized_effect
            
            points = np.array(box.box, dtype=np.int32)
            x, y, bw, bh = cv2.boundingRect(points)
            
            pad = max(5, int(bh * 0.1))
            y1, y2 = max(0, y - pad), min(h_img, y + bh + pad)
            x1, x2 = max(0, x - pad), min(w_img, x + bw + pad)
            
            if expanded.shape == (y2-y1, x2-x1):
                final_glyph[y1:y2, x1:x2] = cv2.bitwise_or(final_glyph[y1:y2, x1:x2], expanded)
                final_effect[y1:y2, x1:x2] = cv2.bitwise_or(final_effect[y1:y2, x1:x2], effect)
            
            if self.debug:
                debug_info["boxes"].append({
                    "text": box.text,
                    "edge_density": features.edge_density,
                    "stroke_width": features.text_stroke_width,
                })
        
        final_combined = cv2.bitwise_or(final_glyph, final_effect)
        
        return RefinedMaskResult(
            glyph_mask=final_glyph,
            effect_mask=final_effect,
            final_mask=final_combined,
            debug_info=debug_info,
        )
    
    def _extract_features(self, image: np.ndarray, box) -> ROIFeatures:
        import cv2
        
        points = np.array(box.box, dtype=np.int32)
        x, y, w, h = cv2.boundingRect(points)
        
        pad = max(5, int(h * 0.1))
        h_img, w_img = image.shape[:2]
        y1, y2 = max(0, y - pad), min(h_img, y + h + pad)
        x1, x2 = max(0, x - pad), min(w_img, x + w + pad)
        
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return ROIFeatures(
                gray=np.array([]),
                enhanced_gray=np.array([]),
                lab=np.array([]),
                hsv=np.array([]),
                edge_density=0.0,
                local_contrast=0.0,
                text_stroke_width=1.0,
                bbox=(x, y, w, h),
            )
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        lab = cv2.cvtColor(roi, cv2.COLOR_BGR2LAB)
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4)).apply(lab[:, :, 0])
        
        edges = cv2.Canny(gray, 50, 150)
        edge_density = edges.sum() / (255 * edges.size)
        local_contrast = enhanced.std() / 255.0
        
        text_stroke_width = max(1.0, h * 0.08)
        
        return ROIFeatures(
            gray=gray,
            enhanced_gray=enhanced,
            lab=lab,
            hsv=hsv,
            edge_density=edge_density,
            local_contrast=local_contrast,
            text_stroke_width=text_stroke_width,
            bbox=(x, y, w, h),
        )
    
    def _generate_candidates(self, image: np.ndarray, box, features: ROIFeatures) -> list[CandidateMask]:
        import cv2
        
        candidates = []
        
        h, w = features.gray.shape if features.gray.size > 0 else (1, 1)
        mask_h, mask_w = image.shape[:2]
        
        points = np.array(box.box, dtype=np.int32)
        x, y, bw, bh = cv2.boundingRect(points)
        
        pad = max(5, int(bh * 0.1))
        y1, y2 = max(0, y - pad), min(mask_h, y + bh + pad)
        x1, x2 = max(0, x - pad), min(mask_w, x + bw + pad)
        
        if features.gray.size == 0:
            poly_mask = np.zeros((mask_h, mask_w), dtype=np.uint8)
            cv2.fillPoly(poly_mask, [points], 255)
            return [CandidateMask(name="polygon", mask=poly_mask)]
        
        local_points = points - [x1, y1]
        
        poly_mask = np.zeros(features.gray.shape, dtype=np.uint8)
        cv2.fillPoly(poly_mask, [local_points], 255)
        candidates.append(CandidateMask(name="polygon", mask=poly_mask))
        
        if features.gray.size > 0:
            _, otsu = cv2.threshold(features.enhanced_gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            candidates.append(CandidateMask(name="otsu", mask=otsu))
            
            adaptive = cv2.adaptiveThreshold(
                features.enhanced_gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY_INV, 11, 2
            )
            candidates.append(CandidateMask(name="adaptive", mask=adaptive))
            
            edges = cv2.Canny(features.gray, 50, 150)
            candidates.append(CandidateMask(name="edge", mask=edges))
        
        return candidates
    
    def _fuse_candidates(self, candidates: list[CandidateMask], features: ROIFeatures) -> np.ndarray:
        import cv2
        
        if not candidates:
            return np.array([])
        
        candidate_map = {candidate.name: candidate.mask for candidate in candidates}
        polygon_mask = candidate_map.get("polygon")
        if polygon_mask is None:
            return np.array([])

        threshold_union = np.zeros_like(polygon_mask)
        for name in ("otsu", "adaptive"):
            candidate_mask = candidate_map.get(name)
            if candidate_mask is not None:
                threshold_union = cv2.bitwise_or(threshold_union, candidate_mask)

        if np.any(threshold_union):
            combined = cv2.bitwise_and(polygon_mask, threshold_union)
        else:
            combined = polygon_mask.copy()
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        combined = cv2.morphologyEx(combined, cv2.MORPH_CLOSE, kernel)
        
        return combined
    
    def _adaptive_expand(self, mask: np.ndarray, features: ROIFeatures) -> np.ndarray:
        import cv2
        
        if mask.size == 0:
            return mask
        
        h = features.bbox[3]
        expansion = max(1, int(h * 0.04))
        
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (expansion, expansion))
        expanded = cv2.dilate(mask, kernel, iterations=1)
        
        return expanded
    
    def _detect_effect(self, image: np.ndarray, box, features: ROIFeatures) -> np.ndarray:
        import cv2
        
        h_img, w_img = image.shape[:2]
        points = np.array(box.box, dtype=np.int32)
        x, y, bw, bh = cv2.boundingRect(points)
        
        pad = max(5, int(bh * 0.15))
        y1, y2 = max(0, y - pad), min(h_img, y + bh + pad)
        x1, x2 = max(0, x - pad), min(w_img, x + bw + pad)
        
        roi = image[y1:y2, x1:x2]
        if roi.size == 0:
            return np.zeros((y2 - y1, x2 - x1), dtype=np.uint8)
        
        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance_map = laplacian.var()
        
        effect_mask = np.zeros(gray.shape, dtype=np.uint8)
        
        if variance_map > 100:
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(contours) > 1:
                sorted_contours = sorted(contours, key=cv2.contourArea, reverse=True)
                if len(sorted_contours) > 1:
                    cv2.drawContours(effect_mask, [sorted_contours[1]], -1, 255, -1)
        
        return effect_mask
    
    def _combine_masks(self, glyph_masks: list[np.ndarray], effect_masks: list[np.ndarray]) -> np.ndarray:
        if not glyph_masks:
            return np.array([])
        
        h, w = glyph_masks[0].shape
        combined = np.zeros((h, w), dtype=np.uint8)
        
        for mask in glyph_masks:
            if mask.shape == (h, w):
                combined = cv2.bitwise_or(combined, mask.astype(np.uint8))
        
        for mask in effect_masks:
            if mask.shape == (h, w):
                combined = cv2.bitwise_or(combined, mask.astype(np.uint8))
        
        return combined
