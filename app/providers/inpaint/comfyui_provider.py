from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import time
from uuid import uuid4

import cv2
import numpy as np

from app.core.config import ComfyUIConfig
from app.core.runtime_state import ComfyUIRuntimeState


class ComfyUIInpainter:
    def __init__(self, config: ComfyUIConfig, state: ComfyUIRuntimeState | None = None) -> None:
        self._config = config
        self._state = state or ComfyUIRuntimeState()

    def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        if self.is_degraded:
            return image

        try:
            return self._inpaint_impl(image, mask)
        except Exception:
            self.mark_failure()
            return image

    def mark_failure(self) -> None:
        self._state.consecutive_failures += 1
        if self._state.consecutive_failures >= self._config.max_consecutive_failures:
            self._state.degraded_until = datetime.now() + timedelta(
                seconds=self._config.degradation_cooldown_seconds
            )

    def mark_recovered(self) -> None:
        self._state.consecutive_failures = 0
        self._state.degraded_until = None

    @property
    def is_degraded(self) -> bool:
        return self._state.is_degraded

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(
                f"http://{self._config.server}/system_stats",
                timeout=min(self._config.request_timeout_seconds, 5),
            ) as response:
                return response.status == 200
        except Exception:
            return False

    def _inpaint_impl(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        resized_image, _ = resize_image_smart(image)
        height, width = resized_image.shape[:2]

        resized_mask = cv2.resize(mask, (width, height), interpolation=cv2.INTER_NEAREST)
        resized_mask = cv2.bitwise_not(resized_mask)

        input_dir = self._config.root_dir / "input"
        if not input_dir.exists():
            raise FileNotFoundError(f"ComfyUI input 目录不存在: {input_dir}")

        random_suffix = random.randint(0, 99999)
        image_name = f"temp_ocr_{random_suffix}.png"
        mask_name = f"temp_mask_{random_suffix}.png"

        cv2.imwrite(str(input_dir / image_name), resized_image)

        mask_rgba = np.zeros((height, width, 4), dtype=np.uint8)
        mask_rgba[:, :, 3] = resized_mask
        cv2.imwrite(str(input_dir / mask_name), mask_rgba)

        workflow_path = Path(self._config.workflow_file)
        with workflow_path.open("r", encoding="utf-8") as file:
            workflow = json.load(file)

        if "1" in workflow:
            workflow["1"]["inputs"]["image"] = image_name
        if "8" in workflow:
            workflow["8"]["inputs"]["image"] = mask_name

        prompt_response = self._queue_prompt(workflow)
        result_data = self._wait_for_images(prompt_response["prompt_id"])

        final_image = image
        outputs = result_data.get("outputs", {})
        for output in outputs.values():
            if "images" not in output:
                continue
            for image_info in output["images"]:
                raw_data = self._get_image_data(
                    image_info["filename"],
                    image_info["subfolder"],
                    image_info["type"],
                )
                final_array = np.asarray(bytearray(raw_data), dtype=np.uint8)
                decoded = cv2.imdecode(final_array, cv2.IMREAD_COLOR)
                if decoded is not None:
                    final_image = cv2.resize(decoded, (image.shape[1], image.shape[0]))
                    self.mark_recovered()
                    return final_image

        self.mark_failure()
        return final_image

    def _queue_prompt(self, workflow: dict) -> dict:
        payload = {"prompt": workflow, "client_id": str(uuid4())}
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"http://{self._config.server}/prompt", data=data)
        with urllib.request.urlopen(request, timeout=self._config.request_timeout_seconds) as response:
            return json.loads(response.read())

    def _get_history(self, prompt_id: str) -> dict:
        url = f"http://{self._config.server}/history/{prompt_id}"
        with urllib.request.urlopen(url, timeout=self._config.request_timeout_seconds) as response:
            return json.loads(response.read())

    def _wait_for_images(self, prompt_id: str) -> dict:
        started_at = datetime.now()
        while (datetime.now() - started_at).total_seconds() <= self._config.request_timeout_seconds:
            history = self._get_history(prompt_id)
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(1)
        raise TimeoutError("等待 ComfyUI 结果超时")

    def _get_image_data(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        url = (
            f"http://{self._config.server}/view?"
            f"filename={filename}&subfolder={subfolder}&type={folder_type}"
        )
        with urllib.request.urlopen(url, timeout=self._config.request_timeout_seconds) as response:
            return response.read()


def resize_image_smart(image: np.ndarray, max_side: int = 1280) -> tuple[np.ndarray, float]:
    height, width = image.shape[:2]
    if max(height, width) <= max_side:
        return image, 1.0

    scale = max_side / max(height, width)
    new_width = int(width * scale)
    new_height = int(height * scale)
    return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA), scale
