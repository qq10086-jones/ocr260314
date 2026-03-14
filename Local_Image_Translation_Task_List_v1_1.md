# Local Image Translation Engine（象寄替代）任务清单 v1.1

## 变更记录

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2026-03-13 | 初始版本 |
| v1.1 | 2026-03-14 | 新增 T3.4 超时保护、T3.5 ComfyUI 熔断降级、T3.6 请求互斥锁；新增 T2.7 ADR 文档补录；调整优先级分类 |

---

## 0. 文档目的

本文档是面向执行团队的实现任务清单。目标不是讨论方向，而是确保员工可以按边界推进，不因"自由发挥"而跑偏。

---

## 1. 交付目标

本轮只交付一个结果：

**可由本地 API 调用的图片翻译引擎 MVP**

不接受以下替代性交付：
- 只交浏览器插件壳
- 只交 UI 设计稿
- 只交 OCR demo
- 只交 ComfyUI 脚本
- 只交 PPT 或想法文档

---

## 2. 范围边界

### In Scope
- OCR 模块化
- 擦字模块化
- 翻译模块可插拔
- 回填渲染模块化
- FastAPI 本地接口
- CLI 调用
- 调试产物输出
- Fast/HQ 两种模式
- ComfyUI 熔断降级（轻量实现）
- 请求超时保护
- 单请求互斥锁

### Out of Scope
- SaaS 化
- 云端账户
- 移动端
- 视频翻译
- PDF 全文排版
- 浏览器商店发布
- 权限系统
- 支付系统
- 多租户架构
- **异步任务队列系统（已记录为 v1.2+ 储备方案，本轮不实现）**
- **VRAM 显存互斥管理器（已记录为 v1.2+ 储备方案，本轮不实现）**

---

## 3. 阶段拆分

## Phase 1 — 代码资产整理

### T1.1 盘点现有代码
- 输入：`step1_test.py` / `step2_erase.py` / `step3_universal_v1.1.py`
- 输出：旧代码功能映射表
- 完成标准：明确每段逻辑归属哪个模块

### T1.2 去除硬编码
- 替换所有绝对路径与固定文件名
- 输出：可由配置控制的路径参数
- 完成标准：代码中不再保留机器相关绝对路径

### T1.3 拆分主流程
- 把单脚本拆分为：
  - OCR
  - mask/inpaint
  - translate
  - render
  - engine orchestrator
- 完成标准：主程序不超过薄 orchestration 层

---

## Phase 2 — Engine 模块化

### T2.1 定义数据模型
- OCRBox
- TranslationTask
- ProcessResult（含 warnings 字段）
- Config schema（含超时、降级相关配置）

完成标准：
- 所有跨模块入参与出参统一结构化
- ProcessResult 支持 warnings 列表
- Config schema 包含 `process_timeout_seconds`、`comfyui.max_consecutive_failures`、`comfyui.degradation_cooldown_seconds`

### T2.2 实现 OCR Provider
- RapidOCR provider
- 接口统一
- 完成标准：输入 ndarray，输出 OCRBox 列表

### T2.3 实现 Inpainter Provider
- OpenCVInpainter
- ComfyUIInpainter（含熔断降级逻辑，见 T3.5）
- 完成标准：两种 provider 均可通过统一接口调用

### T2.4 实现 Translator Provider
- 先保留兼容 provider
- 增加 NoOpTranslator
- 预留本地 translator 接口
- 完成标准：翻译模块完全独立于主流程

### T2.5 实现 Renderer
- 取色
- 字号估算
- 自动换行
- 描边
- 图层合成
- 完成标准：输入任务列表，输出最终图像

### T2.6 实现 Engine
- process(image, src, tgt, mode)
- 支持 fast/hq
- 支持 translate on/off
- 完成标准：单入口完成处理

### T2.7 补录架构决策文档（ADR-005/006/007）
- 输入：Design Doc v1.1 中 ADR-005（同步 API 决策）、ADR-006（异步/VRAM 互斥储备方案）、ADR-007（ComfyUI 熔断）
- 输出：在代码仓库 `/docs/adr/` 目录下创建独立 ADR 文件
- 完成标准：每条 ADR 包含决策内容、理由、废弃方案、复审时机
- 不做什么：不实现 ADR-006 中描述的异步队列和 VRAM 互斥

---

## Phase 3 — Local API

### T3.1 建立 FastAPI 服务
接口：
- `/health`（含 ComfyUI 可用性和降级状态字段）
- `/process`
- `/ocr`
- `/erase`

完成标准：
- 本地可启动
- Postman/curl 可调用

### T3.2 文件输入输出规范
- 上传图片
- 自动生成 job_id
- 输出 runs/job_xxx 目录
- 返回 JSON（含 elapsed_seconds 和 warnings）

### T3.3 错误处理与回退
- ComfyUI 不可用时回退 OpenCV
- 翻译失败回退原文
- 缺字体回退默认字体

### T3.4 请求超时保护
- 输入：config.yaml 中 `process_timeout_seconds` 配置
- 实现：为 `/process` 请求设置全局超时（默认 300s）
- 超时行为：返回 HTTP 504，响应体包含 `{"error": "processing_timeout", "detail": "任务处理超时"}`
- 日志：记录超时发生时的当前执行阶段
- 完成标准：超时后能正确返回 504、释放线程、记录日志
- 不做什么：不实现异步任务取消，不实现任务恢复

### T3.5 ComfyUI 熔断降级
- 输入：config.yaml 中 `comfyui.max_consecutive_failures`（默认 3）和 `comfyui.degradation_cooldown_seconds`（默认 300）
- 实现：
  - ComfyUI Provider 内部维护连续失败计数器
  - 连续 N 次失败/超时后标记为 degraded
  - degraded 期间所有 HQ 请求自动降级为 OpenCV Fast 模式
  - 冷却时间结束后自动发送健康检查请求，成功则恢复
- 暴露方式：`/health` 返回 `comfyui_degraded` 字段；`ProcessResult.warnings` 包含降级提示
- 完成标准：连续 3 次 ComfyUI 失败后自动切换 Fast 模式，冷却后自动恢复
- 不做什么：不引入外部熔断框架，不做 Circuit Breaker 抽象层

### T3.6 单请求互斥锁
- 实现：FastAPI 请求级别锁，保证同时只有一个 `/process` 在执行
- 并发请求行为：返回 HTTP 429 `{"error": "engine_busy", "detail": "当前有任务正在处理，请稍后重试"}`
- 完成标准：两个并发请求，第二个立即返回 429
- 不做什么：不实现请求排队，不实现异步等待

---

## Phase 4 — 测试与质量基线

### T4.1 准备测试集
最少包含：
- 白底黑字图
- 彩色商品图
- 中日英混排图
- 小字体图
- 多文本框图
- 背景复杂图

### T4.2 建立测试报告模板
每张图记录：
- OCR 成功率
- 擦字质量
- 回填可读性
- 总耗时
- 异常
- 是否触发降级

### T4.3 建立最小验收门槛
- Fast 模式 10 张图连续成功
- HQ 模式 5 张图连续成功
- 无阻塞级异常
- 输出目录结构一致
- 超时保护可触发
- ComfyUI 熔断降级可触发并恢复

---

## Phase 5 — Browser Shell 预研（仅预研，不实现正式版）

### T5.1 定义插件与本地服务协议
- 图片来源
- 上传方式
- 结果回填方式
- localhost 端口规范
- 超时处理约定（插件端需配合引擎的 300s 超时）

### T5.2 设计最小交互流
- 右键图片翻译
- popup 选择目标语言
- overlay 展示结果图
- 引擎忙碌时（429）的前端提示

### T5.3 评估是否需要切换异步 API
- 输入：T5.1 协议定稿后，基于实际联调的超时和等待体验
- 输出：是否触发 ADR-006 储备方案的评估报告
- 完成标准：给出明确结论——保持同步 / 启动异步改造
- 说明：此任务仅做评估，不做实现

---

## 4. 角色分工建议

## PM
- 管理范围边界
- 拦截发散需求
- 周会只看里程碑状态和风险

## Architect
- 负责模块接口
- 负责 provider 抽象
- 负责 ADR 文档维护
- 不直接沉迷 UI 或模型细节
- 不在 MVP 阶段推进异步队列或 VRAM 互斥实现

## Backend / Engine
- 负责 engine、API、配置、日志
- 优先保证主链路可调用
- 负责实现超时、熔断降级、请求锁等低成本鲁棒性措施

## Algorithm / Image
- 负责 OCR、mask、inpaint、render
- 不自行扩展无关模型试验

## QA
- 负责测试集与验收基线
- 负责异常回归
- 负责验证降级和超时行为

---

## 5. Definition of Done（DoD）

每项任务只有满足以下条件才算完成：

1. 代码已提交
2. 本地可运行
3. 有最小测试证据
4. 有 README/注释说明
5. 未引入范围外功能
6. 可被下一角色复用

---

## 6. 关键约束

1. 不允许绕开配置中心写死路径
2. 不允许在未审批情况下新增 provider
3. 不允许把插件壳当作本轮主目标
4. 不允许引入云端依赖作为默认路径
5. 不允许把"优化视觉效果"扩展成漫无边际风格化工程
6. 不允许在 MVP 阶段自建复杂工作流编排系统
7. **不允许在 MVP 阶段实现异步任务队列或 VRAM 显存管理器（已作为 ADR-006 储备方案记录，需经评估审批后方可启动）**

---

## 7. 里程碑定义

### M1：Engine Skeleton Ready
- 模块拆分完成
- 可用配置中心
- OCR / Inpaint / Translate / Render 接口成型

### M2：Local API Ready
- `/process` 可稳定调用
- Fast 模式可跑通
- 输出 JSON 正确
- 超时保护生效
- 请求互斥锁生效
- ComfyUI 熔断降级可触发

### M3：HQ Mode Ready
- ComfyUI provider 接入
- 回退机制有效
- 熔断降级机制经过测试
- 测试集通过最低门槛

### M4：Browser Contract Ready
- 插件-本地服务协议定稿
- 交互草图完成
- 是否启动异步改造的评估完成

---

## 8. 风险清单

### R1. 过度沉迷插件 UI
风险：员工会把精力花在弹窗和样式，而不是核心引擎。
对策：插件开发锁定为预研阶段。

### R2. 过度沉迷模型替换
风险：不断试新 OCR、新翻译模型，项目失控。
对策：MVP 只允许一个默认 OCR，一个默认快速修复，一个默认高质量修复。

### R3. 硬编码回潮
风险：员工为了图快重新写死路径。
对策：代码评审发现即退回。

### R4. 质量目标漂移
风险：有人追求"完美修图"导致工期爆炸。
对策：先通过基线，再谈画质提升。

### R5. 需求蔓延
风险：用户提一个翻译图片工具，员工扩成 AI 全家桶。
对策：严格执行范围冻结。

### R6. 架构过度设计
风险：在 MVP 阶段引入异步队列、显存管理器、复杂编排系统等超出当前需求的架构组件，导致工期膨胀和调试复杂度激增。
对策：所有架构增强提案必须通过审批门禁，且必须有真实场景驱动（而非假想未来需求）。已通过 ADR-006 记录储备方案，明确触发条件，杜绝"提前建设"。

---

## 9. 本轮推荐优先级

### P0
- Engine 模块化
- Config 中心
- FastAPI
- Fast 模式
- 输出结构化结果

### P1
- HQ 模式接入
- 错误回退
- 测试集与报告
- ComfyUI 熔断降级
- 请求超时保护
- 单请求互斥锁

### P2
- 浏览器协议草案
- CLI 友好化
- 批量处理雏形
- ADR 文档补录
- 异步方案评估（仅在 M4 完成后）

---

## 10. 审批规则

以下事项必须审批后才能做：
- 新增 provider
- 新增外部依赖
- 新增浏览器端功能
- 新增批量/队列系统
- 新增模型下载策略
- 新增云端服务接入
- **启动 ADR-006 储备方案（异步队列/VRAM 互斥）的实现**

---

## 11. 最终交付物清单

本轮结束必须交付：

1. 设计后的代码目录
2. 可运行 engine
3. FastAPI 本地服务（含超时、降级、互斥机制）
4. 测试样例与测试报告
5. 配置模板
6. README
7. 风险与限制说明
8. ADR 文档（ADR-005/006/007）

---

## 12. 一句话执行口径

**本轮不是做"一个看起来很炫的插件"，而是做"一个可被插件调用的稳定本地图片翻译引擎"。**
