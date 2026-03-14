from __future__ import annotations

from typing import Protocol


class InpainterProvider(Protocol):
    def inpaint(self, image: object, mask: object) -> object:
        """Return image with masked regions filled."""
