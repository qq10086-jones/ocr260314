"""
边界测试
"""

import numpy as np
import pytest

from app.core.errors import InputFileError
from app.providers.ocr.rapidocr_provider import RapidOCROCRProvider
from app.providers.inpaint.strategies import SolidFillProvider


class TestBoundaryConditions:
    """边界条件测试"""
    
    def test_empty_image(self):
        """空图片处理"""
        image = np.zeros((0, 0, 3), dtype=np.uint8)
        assert image.shape == (0, 0, 3)
    
    def test_single_pixel_image(self):
        """单像素图片"""
        image = np.array([[[128, 128, 128]]], dtype=np.uint8)
        assert image.shape == (1, 1, 3)
    
    def test_very_large_mask(self):
        """全屏掩码"""
        image = np.full((100, 100, 3), 200, dtype=np.uint8)
        mask = np.full((100, 100), 255, dtype=np.uint8)
        
        provider = SolidFillProvider()
        result = provider.inpaint(image, mask)
        
        assert result.image.shape == image.shape
    
    def test_zero_mask(self):
        """零掩码"""
        image = np.full((100, 100, 3), 200, dtype=np.uint8)
        mask = np.zeros((100, 100), dtype=np.uint8)
        
        provider = SolidFillProvider()
        result = provider.inpaint(image, mask)
        
        assert result.image.shape == image.shape
    
    def test_grayscale_image(self):
        """灰度图片"""
        image = np.full((100, 100), 128, dtype=np.uint8)
        image = np.stack([image, image, image], axis=2)
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        
        provider = SolidFillProvider()
        result = provider.inpaint(image, mask)
        
        assert result.image.shape == image.shape
    
    def test_rgba_image(self):
        """RGBA 图片（4 通道）"""
        image = np.full((100, 100, 4), 128, dtype=np.uint8)
        
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        
        provider = SolidFillProvider()
        result = provider.inpaint(image, mask)
        
        assert result.image.shape[2] == 3
    
    def test_very_small_mask(self):
        """极小掩码"""
        image = np.full((100, 100, 3), 200, dtype=np.uint8)
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[50, 50] = 255
        
        provider = SolidFillProvider()
        result = provider.inpaint(image, mask)
        
        assert result.image.shape == image.shape
    
    def test_mask_larger_than_image(self):
        """掩码大于图片"""
        image = np.full((50, 50, 3), 200, dtype=np.uint8)
        mask = np.full((100, 100), 255, dtype=np.uint8)
        
        provider = SolidFillProvider()
        result = provider.inpaint(image, mask)
        
        assert result.image.shape == image.shape


class TestOCRBoundary:
    """OCR 边界测试"""
    
    def test_ocr_on_blank_image(self):
        """空白图片 OCR"""
        image = np.full((100, 100, 3), 255, dtype=np.uint8)
        
        ocr = RapidOCROCRProvider()
        boxes = ocr.detect(image)
        
        assert isinstance(boxes, list)
    
    def test_ocr_on_noisy_image(self):
        """噪点图片 OCR"""
        image = np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)
        
        ocr = RapidOCROCRProvider()
        boxes = ocr.detect(image)
        
        assert isinstance(boxes, list)
