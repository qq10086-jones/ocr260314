from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np


class RuntimeMode(Enum):
    FAST = "fast"
    BALANCED = "balanced"
    QUALITY = "quality"


@dataclass
class RouterConfig:
    mode: RuntimeMode = RuntimeMode.BALANCED
    enable_fallback: bool = True


class InpaintRouter:
    """
    M8: Inpaint Backend Router
    
    根据背景分类结果和运行模式，选择合适的 Inpaint Provider。
    
    路由表:
    
    fast mode:
      Type A/B/C/D -> OpenCV Telea (无分类，直接用最快)
    
    balanced mode:
      Type A -> SolidFillProvider
      Type B -> GradientFillProvider
      Type C -> PatchSynthesisProvider
      Type D -> OpenCV Telea
    
    quality mode:
      Type A/B/C -> 同 balanced
      Type D -> LaMa (如果有) -> Diffusers (如果有)
    """
    
    def __init__(
        self,
        config: RouterConfig,
        solid_fill_provider=None,
        gradient_fill_provider=None,
        patch_synthesis_provider=None,
        opencv_provider=None,
        lama_provider=None,
    ):
        self._config = config
        self._solid_fill = solid_fill_provider
        self._gradient_fill = gradient_fill_provider
        self._patch_synthesis = patch_synthesis_provider
        self._opencv = opencv_provider
        self._lama = lama_provider
        
        self._fallback_order = {
            "lama": ["opencv", "patch_synthesis", "solid_fill", "gradient_fill"],
            "patch_synthesis": ["opencv", "solid_fill", "gradient_fill"],
            "gradient_fill": ["solid_fill", "opencv", "patch_synthesis"],
            "solid_fill": ["opencv", "gradient_fill", "patch_synthesis"],
            "opencv": ["solid_fill", "gradient_fill", "patch_synthesis"],
        }
    
    def select_provider(self, bg_type, context: Optional[dict] = None) -> tuple:
        """
        根据背景类型选择合适的 Provider
        
        Returns:
            tuple: (provider, provider_name, fallback_reason)
        """
        mode = self._config.mode
        context = context or {}
        
        if mode == RuntimeMode.FAST:
            return self._select_fast_mode(context)
        elif mode == RuntimeMode.QUALITY:
            return self._select_quality_mode(bg_type, context)
        else:
            return self._select_balanced_mode(bg_type, context)
    
    def _select_fast_mode(self, context: dict) -> tuple:
        """Fast 模式: 直接用 OpenCV，不分类"""
        if self._opencv:
            return (self._opencv, "opencv", None)
        
        if self._solid_fill:
            return (self._solid_fill, "solid_fill", "opencv_unavailable")
        
        raise ValueError("No inpaint provider available")
    
    def _select_balanced_mode(self, bg_type, context: dict) -> tuple:
        """Balanced 模式: 根据背景类型选择。
        COMPLEX 优先用 LaMa，无 LaMa 时降级 OpenCV。
        """
        from app.providers.bg_classifier import BackgroundType

        if bg_type == BackgroundType.COMPLEX:
            if self._lama is not None:
                return (self._lama, "lama", None)
            if self._opencv is not None:
                return (self._opencv, "opencv", "lama_unavailable")

        provider_map = {
            BackgroundType.FLAT: (self._solid_fill, "solid_fill"),
            BackgroundType.GRADIENT: (self._gradient_fill, "gradient_fill"),
            BackgroundType.TEXTURE: (self._patch_synthesis, "patch_synthesis"),
        }

        provider, name = provider_map.get(bg_type, (self._opencv, "opencv"))

        if provider is None:
            provider, name = self.get_fallback_provider(name)
            return (provider, name, f"{bg_type.value}_provider_unavailable")

        return (provider, name, None)
    
    def _select_quality_mode(self, bg_type, context: dict) -> tuple:
        """Quality 模式: 优先用高质量 provider"""
        from app.providers.bg_classifier import BackgroundType
        
        if bg_type == BackgroundType.COMPLEX and self._lama:
            return (self._lama, "lama", None)
        
        return self._select_balanced_mode(bg_type, context)
    
    def get_fallback_provider(self, failed_provider: str) -> tuple:
        """获取回退 Provider"""
        if not self._config.enable_fallback:
            raise ValueError(f"Provider {failed_provider} unavailable and fallback disabled")
        
        fallback_order = self._fallback_order.get(
            failed_provider,
            ["opencv", "solid_fill", "gradient_fill", "patch_synthesis"],
        )

        for provider_name in fallback_order:
            provider = getattr(self, f"_{provider_name}", None)
            if provider:
                return (provider, provider_name)
        
        raise ValueError("No fallback provider available")
    
    def get_available_providers(self) -> dict:
        """获取可用 Provider 列表"""
        return {
            "solid_fill": self._solid_fill is not None,
            "gradient_fill": self._gradient_fill is not None,
            "patch_synthesis": self._patch_synthesis is not None,
            "opencv": self._opencv is not None,
            "lama": self._lama is not None,
        }
    
    def get_routing_table(self) -> dict:
        """获取路由表"""
        return {
            "fast": {
                "A/B/C/D": "opencv"
            },
            "balanced": {
                "flat": "solid_fill",
                "gradient": "gradient_fill",
                "texture": "patch_synthesis",
                "complex": "opencv"
            },
            "quality": {
                "flat": "solid_fill",
                "gradient": "gradient_fill",
                "texture": "patch_synthesis",
                "complex": "lama -> opencv"
            }
        }
