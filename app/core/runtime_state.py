from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class ComfyUIRuntimeState:
    consecutive_failures: int = 0
    degraded_until: datetime | None = None

    @property
    def is_degraded(self) -> bool:
        return self.degraded_until is not None and self.degraded_until > datetime.now()

