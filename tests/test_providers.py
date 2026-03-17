"""
Provider unit tests.
"""

import numpy as np
import pytest

from app.providers.bg_classifier import BackgroundClassifier, BackgroundType
from app.providers.inpaint.base import InpaintResult
from app.providers.inpaint.strategies import GradientFillProvider, PatchSynthesisProvider, SolidFillProvider
from app.providers.mask_refine import CandidateMask, MaskRefinePipeline, ROIFeatures


class TestBackgroundClassifier:
    @pytest.fixture
    def flat_bg_image(self):
        return np.full((100, 100, 3), 128, dtype=np.uint8)

    @pytest.fixture
    def gradient_bg_image(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        for row in range(100):
            image[row, :, 0] = int(row * 2.55)
        return image

    def test_flat_background_classification(self, flat_bg_image):
        classifier = BackgroundClassifier()
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255

        result = classifier.classify(flat_bg_image, mask)

        assert result.bg_type == BackgroundType.FLAT
        assert result.confidence > 0.5

    def test_gradient_background_classification(self, gradient_bg_image):
        classifier = BackgroundClassifier()
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[45:55, 45:55] = 255

        result = classifier.classify(gradient_bg_image, mask)

        assert result.bg_type == BackgroundType.GRADIENT
        assert result.confidence > 0.7

    def test_gradient_classification_none_mask(self, gradient_bg_image):
        classifier = BackgroundClassifier()
        result = classifier.classify(gradient_bg_image, None)
        assert result.bg_type in list(BackgroundType)

    def test_flat_background_all_zero_mask(self, flat_bg_image):
        classifier = BackgroundClassifier()
        mask = np.zeros((100, 100), dtype=np.uint8)
        result = classifier.classify(flat_bg_image, mask)
        assert result.bg_type == BackgroundType.FLAT


class TestSolidFillProvider:
    @pytest.fixture
    def sample_image(self):
        return np.full((100, 100, 3), 200, dtype=np.uint8)

    @pytest.fixture
    def sample_mask(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[40:60, 40:60] = 255
        return mask

    def test_solid_fill_returns_inpaint_result(self, sample_image, sample_mask):
        provider = SolidFillProvider()
        result = provider.inpaint(sample_image, sample_mask)

        assert isinstance(result, InpaintResult)
        assert result.method == "solid_fill"
        assert result.image.shape == sample_image.shape

    def test_solid_fill_preserves_image_size(self, sample_image, sample_mask):
        provider = SolidFillProvider()
        result = provider.inpaint(sample_image, sample_mask)

        assert result.image.shape == sample_image.shape

    def test_solid_fill_reports_poisson_blend(self, sample_image, sample_mask):
        provider = SolidFillProvider()
        result = provider.inpaint(sample_image, sample_mask)

        assert result.debug_info["blend"] == "poisson"


class TestGradientFillProvider:
    @pytest.fixture
    def sample_image(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        for row in range(100):
            image[row, :, 0] = int(row * 2.55)
        return image

    @pytest.fixture
    def sample_mask(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[45:55, 45:55] = 255
        return mask

    def test_gradient_fill_returns_inpaint_result(self, sample_image, sample_mask):
        provider = GradientFillProvider()
        result = provider.inpaint(sample_image, sample_mask)

        assert isinstance(result, InpaintResult)
        assert result.method in ["gradient_fill", "gradient_fill_fallback"]

    def test_gradient_fill_has_debug_info(self, sample_image, sample_mask):
        provider = GradientFillProvider()
        result = provider.inpaint(sample_image, sample_mask)

        assert result.debug_info is not None
        if result.method == "gradient_fill":
            assert result.debug_info["blend"] == "poisson"


class TestPatchSynthesisProvider:
    @pytest.fixture
    def sample_image(self):
        return np.random.randint(0, 256, (100, 100, 3), dtype=np.uint8)

    @pytest.fixture
    def small_mask(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[20:40, 20:40] = 255
        return mask

    @pytest.fixture
    def edge_mask(self):
        mask = np.zeros((100, 100), dtype=np.uint8)
        mask[5:15, 5:15] = 255
        return mask

    def test_patch_synthesis_returns_inpaint_result(self, sample_image, small_mask):
        provider = PatchSynthesisProvider()
        result = provider.inpaint(sample_image, small_mask)

        assert isinstance(result, InpaintResult)

    def test_patch_synthesis_edge_case(self, sample_image, edge_mask):
        provider = PatchSynthesisProvider()
        result = provider.inpaint(sample_image, edge_mask)

        assert isinstance(result, InpaintResult)
        assert result.image.shape == sample_image.shape


class TestMaskRefinePipeline:
    def test_fuse_candidates_is_constrained_by_polygon(self):
        pipeline = MaskRefinePipeline()
        polygon = np.zeros((8, 8), dtype=np.uint8)
        polygon[2:6, 2:6] = 255

        otsu = np.zeros((8, 8), dtype=np.uint8)
        otsu[1:7, 1:7] = 255

        adaptive = np.zeros((8, 8), dtype=np.uint8)
        adaptive[3:7, 0:4] = 255

        fused = pipeline._fuse_candidates(
            [
                CandidateMask(name="polygon", mask=polygon),
                CandidateMask(name="otsu", mask=otsu),
                CandidateMask(name="adaptive", mask=adaptive),
            ],
            ROIFeatures(
                gray=np.zeros((8, 8), dtype=np.uint8),
                enhanced_gray=np.zeros((8, 8), dtype=np.uint8),
                lab=np.zeros((8, 8, 3), dtype=np.uint8),
                hsv=np.zeros((8, 8, 3), dtype=np.uint8),
                edge_density=0.0,
                local_contrast=0.0,
                text_stroke_width=1.0,
                bbox=(0, 0, 8, 8),
            ),
        )

        outside_polygon = (polygon == 0) & (fused > 0)
        assert not np.any(outside_polygon), "fused mask must stay inside polygon prior"


class TestInpaintResult:
    def test_inpaint_result_dataclass(self):
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        result = InpaintResult(
            image=image,
            method="test",
            debug_info={"key": "value"},
        )

        assert result.image.shape == (10, 10, 3)
        assert result.method == "test"
        assert result.debug_info["key"] == "value"

    def test_inpaint_result_optional_debug_info(self):
        image = np.zeros((10, 10, 3), dtype=np.uint8)
        result = InpaintResult(
            image=image,
            method="test",
        )

        assert result.debug_info is None
