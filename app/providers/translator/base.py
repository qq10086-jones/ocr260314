from __future__ import annotations

from typing import Protocol


class TranslatorProvider(Protocol):
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        """Translate a single text fragment."""
