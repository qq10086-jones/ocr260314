# Local API Contract

## 当前状态

当前已建立 FastAPI 入口骨架，已定义以下接口：

- `GET /health`
- `POST /process`
- `POST /ocr`
- `POST /erase`
- `POST /render`

## `GET /health`

返回字段：

```json
{
  "status": "ok",
  "comfyui_available": true,
  "comfyui_degraded": false
}
```

说明：

- `comfyui_available` 当前会探测本地 ComfyUI `/system_stats`
- `comfyui_degraded` 来自运行期状态
- `resources` 会返回字体、workflow、ComfyUI 根目录、输出目录的存在性
- `warnings` 会返回当前资源缺口

## `POST /process`

请求体：

```json
{
  "image_path": "/absolute/or/relative/path/to/image.png",
  "src_lang": "auto",
  "tgt_lang": "ja",
  "mode": "fast",
  "translate": true
}
```

当前限制：

- `image_path` 当前走本地路径输入，后续再扩展文件上传
- 返回结构已对齐 `ProcessResult`
- `fast` 模式已接入真实 OCR / 翻译 / OpenCV 擦字 / 文字回填
- `hq` 模式已接入 ComfyUI provider，但仍依赖真实 workflow 与本地 ComfyUI 环境联调
- 当前已加请求级超时保护，超时返回 504
- 成功处理后会在 `runs/.../job_xxx/` 中落 `result.json` 和 `logs.txt`

## `POST /ocr`

请求体：

```json
{
  "image_path": "/absolute/or/relative/path/to/image.png"
}
```

返回：

- `count`
- `boxes`

当前限制：

- 当前已接入 RapidOCR provider

## `POST /erase`

请求体：

```json
{
  "image_path": "/absolute/or/relative/path/to/image.png",
  "mode": "fast"
}
```

返回：

- `job_id`
- `input_path`
- `output_path`
- `mask_path`

当前限制：

- 当前已接入真实 OCR + mask + OpenCV inpaint
- 返回值仍偏轻量，后续可补更细的调试信息

## `POST /render`

请求体：

```json
{
  "image_path": "/absolute/or/relative/path/to/image.png",
  "tasks": [
    {
      "box": [[0, 0], [100, 0], [100, 40], [0, 40]],
      "source_text": "原文",
      "translated_text": "译文",
      "text_color": [255, 255, 255]
    }
  ]
}
```

返回：

- `job_id`
- `input_path`
- `output_path`
