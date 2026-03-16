from __future__ import annotations

import json
import random
import requests
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
        self.base_url = f"http://{self._config.server}"

    def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        print(f"\n[ComfyUI] >>> 启动高质量擦除流程 <<<")
        try:
            return self._inpaint_impl(image, mask)
        except Exception as e:
            print(f"[ComfyUI] ❌ 流程中断: {e}")
            import traceback
            traceback.print_exc()
            return image

    def _inpaint_impl(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]

        # 1. 编码
        _, img_encoded = cv2.imencode(".png", image)
        
        # 处理 Mask 为 RGBA 适配 LoadImageMask
        mask_rgba = np.zeros((height, width, 4), dtype=np.uint8)
        mask_rgba[:, :, 0:3] = 0 
        mask_rgba[:, :, 3] = mask # Alpha 通道
        _, msk_encoded = cv2.imencode(".png", mask_rgba)

        random_id = random.randint(1000, 9999)
        img_name = f"api_img_{random_id}.png"
        msk_name = f"api_msk_{random_id}.png"

        # 2. 上传
        print(f"[ComfyUI] 正在上传图片...")
        self._upload(img_name, img_encoded.tobytes())
        self._upload(msk_name, msk_encoded.tobytes())

        # 3. 构造 Workflow
        workflow_path = Path(self._config.workflow_file)
        print(f"[ComfyUI] 加载工作流: {workflow_path.name}")
        with workflow_path.open("r", encoding="utf-8") as f:
            workflow = json.load(f)

        # 映射 ID (1 和 13)
        if "1" in workflow: workflow["1"]["inputs"]["image"] = img_name
        if "13" in workflow: workflow["13"]["inputs"]["image"] = msk_name

        # 4. 提交任务
        print(f"[ComfyUI] 正在提交 Queue Prompt...")
        res = requests.post(f"{self.base_url}/prompt", json={"prompt": workflow, "client_id": str(uuid4())})
        res.raise_for_status()
        prompt_id = res.json()["prompt_id"]
        print(f"[ComfyUI] 任务已入队 ID: {prompt_id} (显卡应开始工作)")

        # 5. 等待
        result_data = self._wait_for_images(prompt_id)
        
        # 6. 获取结果
        outputs = result_data.get("outputs", {})
        for node_id, output in outputs.items():
            if "images" in output:
                for img_info in output["images"]:
                    file_name = img_info["filename"]
                    print(f"[ComfyUI] 正在拉取结果图: {file_name}")
                    img_res = requests.get(f"{self.base_url}/view", params={
                        "filename": file_name,
                        "subfolder": img_info.get("subfolder", ""),
                        "type": img_info.get("type", "output")
                    })
                    img_res.raise_for_status()
                    
                    nparr = np.frombuffer(img_res.content, np.uint8)
                    decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if decoded is not None:
                        if decoded.shape[:2] != (height, width):
                            decoded = cv2.resize(decoded, (width, height))
                        print(f"[ComfyUI] ✅ 擦除成功。")
                        return decoded

        print("[ComfyUI] ⚠️ 任务完成但未找到结果图。")
        return image

    def _upload(self, name: str, data: bytes):
        files = {"image": (name, data, "image/png")}
        res = requests.post(f"{self.base_url}/upload/image", files=files)
        res.raise_for_status()

    def _wait_for_images(self, prompt_id: str) -> dict:
        start = time.time()
        while time.time() - start < 300:
            res = requests.get(f"{self.base_url}/history/{prompt_id}")
            res.raise_for_status()
            history = res.json()
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(1)
        raise TimeoutError("ComfyUI 超时")

    @property
    def is_degraded(self) -> bool:
        return self._state.is_degraded
