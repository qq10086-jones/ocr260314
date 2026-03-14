# Local Image Translation Engine（象寄替代）设计文档 v1.1

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-03-13 | 初始版本 |
| v1.1 | 2026-03-14 | 补充 API 同步/异步决策说明；增加超时与降级机制；新增 ADR-005/006/007；完善性能策略演进触发条件 |

---

## 1. 文档目的

本文档定义一个**本地优先、可插拔、可扩展**的图片翻译引擎方案，目标是将现有原型脚本升级为可产品化的系统，并为后续浏览器插件、桌面工具、批处理工具提供统一底座。

本设计明确基于你现有旧项目能力演进，而不是从零重写。

---

## 2. 背景与问题定义

你现有的三个脚本已经证明以下链路可以跑通：

- `step1_test.py`：RapidOCR 识别验证
- `step2_erase.py`：OCR 框生成 mask + OpenCV inpaint 擦字
- `step3_universal_v1.1.py`：OCR → 翻译 → mask → ComfyUI 修复 → 原位回填文字

现状问题不在"能力不存在"，而在于：

1. 脚本式实现，耦合严重
2. 硬编码路径多，无法复用
3. 翻译后端不可插拔
4. 没有统一接口
5. 没有产品治理边界，容易二开时不断发散
6. 还不是插件架构，只是本地 pipeline

---

## 3. 产品目标

### 3.1 核心目标

构建一个本地图片翻译引擎，支持：

- 输入图片
- OCR 提取文字与坐标
- 生成擦字 mask
- 执行背景修复
- 翻译文本
- 将翻译文本按原位置、颜色、布局尽量自然地回填
- 输出处理后图片和中间结构化结果

### 3.2 非目标

当前阶段不做：

- 浏览器商店正式发布
- 多人协同 SaaS
- 云端账号系统
- 在线计费
- 视频逐帧翻译
- PDF 全套复杂排版引擎
- 一开始就做移动端

---

## 4. 目标用户与场景

### 4.1 用户
- 你自己
- 本地 AI 工具/浏览器插件开发者
- 电商图片翻译使用者
- 需要本地隐私控制的图像翻译场景

### 4.2 核心场景
1. 商品详情图翻译
2. 截图翻译
3. 漫画/海报/说明图翻译
4. 浏览器右键图片翻译
5. 批量图像翻译

---

## 5. 设计原则

1. **本地优先**：默认本地执行，不依赖云端
2. **引擎与壳分离**：先做 engine，再做 browser shell / desktop shell
3. **模块可插拔**：OCR、翻译、修复、渲染可替换
4. **双模式质量策略**：快速模式 / 高质量模式
5. **结构化输出优先**：中间态全部可追踪
6. **治理优先于堆功能**：防止员工发散跑偏

---

## 6. 现有资产复用分析

## 6.1 可直接复用模块

### A. OCR 验证层
现有 `step1_test.py` 已验证 RapidOCR 基本可用，可作为默认 OCR Provider。

### B. 快速擦字层
现有 `step2_erase.py` 已具备：
- OCR 结果读取
- polygon mask
- dilation
- OpenCV inpaint

可抽象为 `FastInpainter`。

### C. 高质量修复层
现有 `step3_universal_v1.1.py` 已具备：
- ComfyUI workflow 注入
- prompt queue
- history polling
- 结果下载与 resize

可抽象为 `ComfyInpainter`。

### D. 文字回填层
现有 `step3_universal_v1.1.py` 已具备：
- 智能取色
- 动态字号估算
- 描边逻辑
- PIL 回填

可抽象为 `TextRenderer`。

## 6.2 必须重构的部分

1. 硬编码路径
2. 单文件脚本结构
3. 翻译逻辑耦合到主程序
4. 输入输出协议缺失
5. 错误处理不统一
6. 缺少配置中心与 provider 接口

---

## 7. 目标架构

```text
┌──────────────────────────────────────────┐
│              Client Layer               │
│ Browser Extension / Desktop UI / CLI    │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│              Local API Layer            │
│ FastAPI / Flask                         │
│ /health /process /ocr /erase /render    │
└──────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────┐
│             Engine Orchestrator         │
│ ImageTranslationEngine                  │
│ - load image                            │
│ - call OCR                              │
│ - build tasks                           │
│ - translate                             │
│ - erase/inpaint                         │
│ - render                                │
│ - export result                         │
└──────────────────────────────────────────┘
     │                │               │
     ▼                ▼               ▼
┌──────────┐   ┌────────────┐  ┌────────────┐
│ OCR      │   │ Translator │  │ Inpainter  │
│ Provider │   │ Provider   │  │ Provider   │
└──────────┘   └────────────┘  └────────────┘
     │                                │
     ▼                                ▼
 RapidOCR                     OpenCV / ComfyUI

                    ▼
┌──────────────────────────────────────────┐
│              Render Layer               │
│ Text Color / Font Size / Stroke / Wrap  │
└──────────────────────────────────────────┘
```

---

## 8. 模块设计

## 8.1 Core Data Model

### OCRBox
```json
{
  "box": [[x1,y1],[x2,y2],[x3,y3],[x4,y4]],
  "text": "原文",
  "score": 0.98
}
```

### TranslationTask
```json
{
  "id": "task_001",
  "box": [[...]],
  "source_text": "原文",
  "translated_text": "译文",
  "text_color": [255,255,255],
  "font_size": 22
}
```

### ProcessResult
```json
{
  "job_id": "uuid",
  "status": "success",
  "mode": "fast",
  "input_path": "...",
  "output_path": "...",
  "elapsed_seconds": 12.3,
  "debug": {
    "mask_path": "...",
    "clean_bg_path": "..."
  },
  "tasks": [],
  "warnings": []
}
```

## 8.2 OCR Provider Interface

```python
class OCRProvider(Protocol):
    def detect(self, image: np.ndarray) -> list[OCRBox]:
        ...
```

默认实现：
- `RapidOCROCRProvider`

预留实现：
- PaddleOCRProvider
- MangaOCRProvider

## 8.3 Translator Provider Interface

```python
class TranslatorProvider(Protocol):
    def translate(self, text: str, src_lang: str, tgt_lang: str) -> str:
        ...
```

默认策略：
- v1 允许兼容旧逻辑
- v1.1 起切换为本地/自托管 translator

预留实现：
- LocalNLLBTranslator
- LibreTranslateProvider
- OllamaLLMTranslator
- NoOpTranslator（仅擦字不翻译）

## 8.4 Inpainter Provider Interface

```python
class InpainterProvider(Protocol):
    def inpaint(self, image: np.ndarray, mask: np.ndarray) -> np.ndarray:
        ...
```

实现：
- `OpenCVInpainter`
- `ComfyUIInpainter`

## 8.5 Renderer Module

职责：
- 提取文字颜色
- 估算字号
- 自动换行
- 文本居中
- 描边
- 透明层叠加

## 8.6 Orchestrator

```python
engine.process(
    image,
    src_lang="auto",
    tgt_lang="ja",
    mode="fast",
    output_dir="./outputs"
)
```

处理顺序：

1. 读图
2. OCR
3. 生成 TranslationTask
4. 翻译文本
5. 生成 mask
6. 选择 inpaint provider
7. 回填文字
8. 保存结果与调试产物
9. 返回结构化 JSON

---

## 9. API 设计

### 9.0 同步/异步决策说明

**v1（M2 阶段）采用同步模式。** 理由如下：

1. MVP 阶段并发数为 1，不存在资源争抢场景
2. 调用方为 CLI 和 Postman/curl 测试，不存在浏览器请求超时问题
3. 同步模式实现成本低，调试简单，符合"先稳定再扩展"原则

**v1.2+（M4 之后）评估是否切换为异步模式。** 触发条件见 ADR-006。

为确保同步模式的鲁棒性，v1 引入以下保护措施：

- **全局超时**：`POST /process` 设置 `timeout=300s`，超时返回 HTTP 504 并记录日志
- **ComfyUI 降级**：ComfyUI provider 内置连续失败计数器，连续 3 次失败/超时后自动降级为 OpenCV 模式，5 分钟后自动尝试恢复；降级期间 `ProcessResult.warnings` 中附带降级提示
- **单请求互斥**：v1 通过 FastAPI 的请求级别锁保证同一时间只有一个 `/process` 请求在执行，后续请求返回 HTTP 429 提示稍后重试

## 9.1 健康检查
`GET /health`

返回：
```json
{
  "status": "ok",
  "comfyui_available": true,
  "comfyui_degraded": false
}
```

说明：增加 ComfyUI 可用性和降级状态字段，便于调用方感知当前引擎能力。

## 9.2 图片处理
`POST /process`

参数：
- image file
- src_lang
- tgt_lang
- mode = fast | hq
- translate = true | false

返回：
- output image path
- debug artifacts
- structured tasks
- elapsed_seconds
- warnings（含降级提示等）

超时策略：
- 全局 timeout = 300s
- 超时返回 HTTP 504 `{"error": "processing_timeout", "detail": "任务处理超时，请检查 ComfyUI 服务状态或切换至 fast 模式"}`
- 超时时记录当前执行阶段至日志

## 9.3 仅 OCR
`POST /ocr`

## 9.4 仅擦字
`POST /erase`

## 9.5 仅渲染
`POST /render`

---

## 10. 浏览器插件集成思路

### 10.1 插件职责
- 获取网页图片 URL 或截图
- 把图片发给 localhost 服务
- 接收结果图
- 在网页上生成 overlay 展示

### 10.2 本地服务职责
- 执行完整 pipeline
- 返回结果和调试数据

### 10.3 为什么这样分层
因为现有旧项目最值钱的是引擎，不是浏览器前端。先把引擎 API 化，后续可以：
- Chrome 插件接
- Edge 插件接
- 本地桌面壳接
- 批处理 CLI 接

---

## 11. 配置设计

统一配置文件：`config.yaml`

建议字段：

```yaml
runtime:
  output_dir: ./outputs
  temp_dir: ./tmp
  debug: true
  process_timeout_seconds: 300

ocr:
  provider: rapidocr

translator:
  provider: local
  src_lang: auto
  tgt_lang: ja

inpaint:
  provider: opencv
  expand_pixels: 8

comfyui:
  server: 127.0.0.1:8188
  root_dir: D:\comfyui2\ComfyUI
  workflow_file: workflow.json
  request_timeout_seconds: 120
  max_consecutive_failures: 3
  degradation_cooldown_seconds: 300

render:
  font_path: ./fonts/NotoSansCJK-Regular.otf
  stroke_enabled: true
```

---

## 12. 日志与可观测性

每次任务必须记录：
- job_id
- 输入图片尺寸
- OCR 框数量
- 每个框源文本/译文
- 选择的 provider
- 总耗时
- 各阶段耗时
- 输出路径
- 异常信息
- 是否触发降级
- 降级原因

建议目录：

```text
runs/
  2026-03-14/
    job_xxx/
      input.jpg
      mask.png
      clean_bg.jpg
      result.jpg
      result.json
      logs.txt
```

---

## 13. 错误处理策略

### 可恢复错误
- 翻译失败：回退原文
- ComfyUI 不可用：回退 OpenCV inpaint
- ComfyUI 连续失败：触发熔断降级，自动切换 OpenCV 模式（见 9.0 节）
- 字体缺失：回退默认字体
- 单次请求超时：返回 504，记录当前阶段

### 不可恢复错误
- 输入图片不存在
- OCR 初始化失败
- 输出目录不可写

---

## 14. 性能策略

### v1（M1–M2）
- 单图同步处理
- 单任务串行
- 优先稳定性
- 通过请求锁保证不并发

### v1.1（M3 完成后）
- 支持批量图片队列（进程内队列，非外部 MQ）
- Provider 初始化缓存
- 文本框批处理翻译

**v1.1 启动条件**：M3 门禁通过，Fast/HQ 两种模式均稳定，测试集达到最低验收门槛。

### v1.2（M4 完成后，按需评估）
- 浏览器多图排队
- 任务状态轮询 / 异步提交（见 ADR-006）
- 失败重试

**v1.2 启动条件**：浏览器插件集成后，出现以下任一真实场景才启动——(a) 浏览器请求因超时频繁失败；(b) 用户需要同时提交多图且等待时间不可接受；(c) 引入本地 LLM 翻译导致 GPU 资源争抢。

---

## 15. 安全与隐私原则

1. 默认不上传云端
2. 默认 localhost 访问
3. 结果图片存本地
4. 敏感图片不出机
5. 第三方翻译 provider 必须显式启用

---

## 16. 里程碑建议

### M1 — Engine 重构
把旧脚本拆成 engine 模块

### M2 — Local API
提供 HTTP 接口

### M3 — Quality Upgrade
做双模式策略和回退机制

### M4 — Browser Shell MVP
做最小插件壳（含插件-本地服务协议定稿）

### M5 — Batch & Governance
支持批量与质量治理

---

## 17. 关键架构决策

### ADR-001：先引擎后插件
理由：现有资产是引擎，不是插件 UI。

### ADR-002：本地 API 中台化
理由：避免前端和算法逻辑耦合。

### ADR-003：双修复模式并存
理由：兼顾速度与质量。

### ADR-004：翻译 provider 可插拔
理由：满足本地化与可控演进。

### ADR-005：v1 采用同步 API，不引入异步任务队列
决策：M2 阶段 API 采用同步请求-响应模式，通过请求锁保证并发数=1。

理由：
- MVP 单图串行，无并发资源争抢
- 同步模式实现成本低，调试链路清晰
- 过早引入异步队列会显著扩张工程范围，违反"先稳定再扩展"原则

废弃方案：全异步提交 + 状态轮询模式（技术上合理，但 MVP 阶段无真实需求驱动）

复审时机：M4 完成后，根据浏览器插件集成的真实反馈评估。

### ADR-006：异步队列与 VRAM 互斥作为 v1.2+ 储备方案
决策：将异步任务队列（Job 提交 + 状态轮询）和 GPU 显存互斥锁列为 v1.2+ 储备架构方向，当前不实现。

触发条件（满足任一即启动设计）：
1. 浏览器插件接入后，HTTP 请求因处理耗时导致频繁超时
2. 引入本地 LLM 翻译（如 Ollama + Qwen）且需与 ComfyUI 共享 GPU
3. 用户场景明确需要多图并发提交

储备方案要点：
- API 切换为 `POST /v1/jobs`（提交）+ `GET /v1/jobs/{id}`（轮询）+ `DELETE /v1/jobs/{id}`（取消）
- 引入 `VRAMResourceManager`，通过 asyncio.Lock 实现 LLM 与 ComfyUI 的显存互斥
- Orchestrator 增加后台 worker loop，消费内部任务队列
- 所有任务附带 Watchdog 超时（默认 300s），超时强制释放资源

说明：以上方案来源于团队内部架构评审意见，技术判断有价值。但在 MVP 并发数=1 的前提下，这些机制不会被实际触发。按照"只为已有能力抽象，不为假想未来过度设计"的原则，记录但不实现。

### ADR-007：ComfyUI 熔断降级机制（v1 实现）
决策：在 ComfyUI Provider 内部实现轻量级熔断，无需引入外部框架。

实现方式：
- ComfyUI Provider 维护连续失败计数器
- 连续 3 次失败/超时后，标记为 degraded 状态
- degraded 期间所有 HQ 请求自动降级为 OpenCV Fast 模式
- 5 分钟后自动尝试恢复（发送一次健康检查请求）
- 降级状态通过 `/health` 接口和 `ProcessResult.warnings` 暴露给调用方

理由：这是低成本的鲁棒性提升，几十行代码即可实现，不需要重写架构。

---

## 18. 验收标准

### 功能验收
- 单张图片可成功输出结果图
- 输出 JSON 含 OCR/翻译/渲染任务
- fast 模式可跑通
- hq 模式可跑通
- ComfyUI 不可用时能回退
- ComfyUI 连续失败时能自动降级
- 请求超时能正确返回 504

### 质量验收
- 文本框覆盖率 ≥ 90%
- 擦字残留可控
- 回填文本位置基本正确
- 对中日英常见场景可用

### 工程验收
- 无硬编码绝对路径
- 配置中心生效
- CLI 与 API 都可调用
- 关键模块具备单元测试

---

## 19. 推荐目录结构

```text
image_translator/
  app/
    api/
      main.py
      routes_process.py
    core/
      engine.py
      models.py
      config.py
    providers/
      ocr/
        rapidocr_provider.py
      translator/
        base.py
        noop.py
        local_provider.py
      inpaint/
        opencv_provider.py
        comfyui_provider.py
    render/
      text_renderer.py
      color_extractor.py
      font_estimator.py
    utils/
      image_io.py
      logging.py
  tests/
  config.yaml
  README.md
```

---

## 20. 总结

你的旧项目不是废弃资产，而是这个产品的第一代核心引擎。正确路线不是重写，而是：

**旧脚本能力 → 模块化引擎 → 本地 API → 插件壳**

这个顺序最稳、复用率最高，也最符合你希望"本地可控、模块清晰、可持续扩展"的目标。
