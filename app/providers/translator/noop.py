from __future__ import annotations


class NoOpTranslator:
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        return text
