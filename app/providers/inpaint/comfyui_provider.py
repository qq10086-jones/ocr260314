from __future__ import annotations

import json
import random
import urllib.error
import urllib.request
import mimetypes
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
        try:
            return self._inpaint_impl(image, mask)
        except Exception as e:
            print(f"[严重错误] ComfyUI 调用失败: {e}")
            import traceback
            traceback.print_exc()
            return image

    def _inpaint_impl(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        height, width = image.shape[:2]

        # 1. 编码图片为内存数据 (PNG 格式)
        _, img_encoded = cv2.imencode(".png", image)
        _, msk_encoded = cv2.imencode(".png", mask)

        random_id = random.randint(1000, 9999)
        image_name = f"api_upload_{random_id}.png"
        mask_name = f"api_mask_{random_id}.png"

        # 2. 通过 API 接口上传图片到 ComfyUI (最稳的方法)
        print(f"[Debug] 正在通过 API 上传原图: {image_name}")
        self._upload_image(image_name, img_encoded.tobytes())
        print(f"[Debug] 正在通过 API 上传遮罩: {mask_name}")
        self._upload_image(mask_name, msk_encoded.tobytes())

        # 3. 加载并修改工作流
        workflow_path = Path(self._config.workflow_file)
        with workflow_path.open("r", encoding="utf-8") as f:
            workflow = json.load(f)

        if "1" in workflow:
            workflow["1"]["inputs"]["image"] = image_name
        if "8" in workflow:
            workflow["8"]["inputs"]["image"] = mask_name

        # 4. 提交任务
        print(f"[Debug] 正在提交任务到 ComfyUI 队列...")
        prompt_response = self._queue_prompt(workflow)
        prompt_id = prompt_response["prompt_id"]
        print(f"[Debug] 任务已入队，ID: {prompt_id}，显卡已开始轰鸣...")

        # 5. 等待并获取结果
        result_data = self._wait_for_images(prompt_id)
        outputs = result_data.get("outputs", {})
        
        for node_id, output in outputs.items():
            if "images" in output:
                for img_info in output["images"]:
                    file_name = img_info["filename"]
                    print(f"[Debug] 识别到输出结果: {file_name}，正在拉取图片...")
                    raw_data = self._get_image_data(file_name, img_info.get("subfolder", ""), img_info.get("type", "output"))
                    
                    nparr = np.frombuffer(raw_data, np.uint8)
                    decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if decoded is not None:
                        if decoded.shape[:2] != (height, width):
                            decoded = cv2.resize(decoded, (width, height))
                        print(f"[Debug] 恭喜！高质量擦除已完成。")
                        return decoded

        print("[警告] ComfyUI 虽然跑完了，但没吐出图片。")
        return image

    def _upload_image(self, filename: str, image_bytes: bytes):
        """使用 multipart/form-data 格式上传图片到 ComfyUI"""
        boundary = f"----WebKitFormBoundary{uuid4().hex}"
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'
            f"Content-Type: image/png\r\n\r\n"
        ).encode("utf-8") + image_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")

        request = urllib.request.Request(f"http://{self._config.server}/upload/image", data=body)
        request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
        
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())

    def _queue_prompt(self, workflow: dict) -> dict:
        payload = {"prompt": workflow, "client_id": str(uuid4())}
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(f"http://{self._config.server}/prompt", data=data)
        with urllib.request.urlopen(request) as response:
            return json.loads(response.read())

    def _get_history(self, prompt_id: str) -> dict:
        url = f"http://{self._config.server}/history/{prompt_id}"
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read())

    def _wait_for_images(self, prompt_id: str) -> dict:
        started_at = datetime.now()
        while (datetime.now() - started_at).total_seconds() < 300: # 5分钟超时
            history = self._get_history(prompt_id)
            if prompt_id in history:
                return history[prompt_id]
            time.sleep(1)
        raise TimeoutError("ComfyUI 执行超时")

    def _get_image_data(self, filename: str, subfolder: str, folder_type: str) -> bytes:
        url = f"http://{self._config.server}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"
        with urllib.request.urlopen(url) as response:
            return response.read()

    @property
    def is_degraded(self) -> bool:
        return self._state.is_degraded
