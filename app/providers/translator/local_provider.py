from __future__ import annotations

from deep_translator import GoogleTranslator


LANGUAGE_MODE_MAP = {
    "auto2zh": ("auto", "zh-CN"),
    "auto2en": ("auto", "en"),
    "auto2ja": ("auto", "ja"),
    "en2zh": ("en", "zh-CN"),
    "zh2en": ("zh-CN", "en"),
    "zh2ja": ("zh-CN", "ja"),
    "ja2zh": ("ja", "zh-CN"),
    "en2ja": ("en", "ja"),
    "ja2en": ("ja", "en"),
}


class GoogleTranslatorProvider:
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        translator = GoogleTranslator(source=src_lang, target=tgt_lang)
        return translator.translate(text)

    def translate_with_mode(self, text: str, mode: str) -> str:
        src_lang, tgt_lang = LANGUAGE_MODE_MAP.get(mode, ("auto", "zh-CN"))
        return self.translate(text, src_lang, tgt_lang)
