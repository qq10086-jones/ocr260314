# Local Image Translation Engine v2.0 任务清单

## 0. 文档目的

本文档面向执行团队，目标是把 `ocr260314` 从“已能跑通的 OCR 翻译脚本集合”推进到“具备商用品质潜力的图片翻译与精修引擎”。

**当前第一优先级不是 UI，不是浏览器壳层，而是：Mask Refine Pipeline。**

---

## 1. 总体执行原则

1. 不允许跳过 mask 质量问题直接堆更多修复模型
2. 不允许在没有 QA 证据的前提下宣称“效果提升”
3. 不允许将精修工作台提前到核心 pipeline 未稳定前大规模展开
4. 不允许新增云端依赖作为默认主链路
5. 所有任务必须可回归、可产出中间结果、可比较前后差异

---

## 2. 里程碑总览

### M1：Mask Refine Pipeline v1（最高优先级）
目标：从 OCR box 擦字升级到 refined mask 擦字

### M2：Background Reconstruction Router
目标：建立 Fast/HQ 双通道路由与 QA 回退

### M3：Layout Planner v1
目标：从“原位回填”升级到“结构化排版”

### M4：Pipeline Productization
目标：主链路模块化、API/CLI 稳定、产物与日志完整

### M5：Manual Refinement Foundation
目标：为未来精修工作台建立统一对象模型和局部重跑能力

---

## 3. M1：Mask Refine Pipeline v1

### T1.1 建立基线评测集

**目标**
建立至少 50 张样本图，覆盖：

- 纯色背景文字
- 弱纹理背景文字
- 复杂纹理背景文字
- 按钮文字
- 描边文字
- 倾斜文字
- 图文相邻场景
- 电商详情图

**交付物**

- `samples/benchmark_v1/`
- `samples/benchmark_manifest.json`
- case 标签说明文档

**验收标准**

- 每张图有唯一 case id
- 可重复批量跑

---

### T1.2 提取当前基线结果

**目标**
对现有 `step2_erase.py` 与 `step3_universal_v1.1.py` 形成基线结果。

**交付物**

- baseline runs
- 当前残字、误伤、边缘损伤问题汇总
- top 20 failure case 清单

**验收标准**

- 每个样本保留：原图 / mask / clean / final
- failure 分类明确

---

### T1.3 抽象 Coarse Mask Builder

**目标**
把现有 OCR polygon mask 逻辑从脚本抽到模块层。

**子任务**

- 新建 `app/mask/coarse_mask.py`
- 输入 OCR result，输出 coarse mask
- 支持 polygon / bbox
- 支持最小 debug 图输出

**交付物**

- 模块代码
- 单测

---

### T1.4 实现 ROI Refine Mask v1

**目标**
在每个文本 ROI 内，从粗框进一步提取更接近真实字形的 mask。

**建议实现**

- grayscale
- Otsu threshold
- adaptive threshold
- Canny/Sobel 边缘
- connected components 过滤
- 与 coarse mask 交集/并集融合

**交付物**

- `app/mask/refine_mask.py`
- 候选 mask 可视化
- 参数配置项

**验收标准**

- 至少在 benchmark 上让 60% 以上 case 的 mask 视觉优于 baseline

---

### T1.5 实现描边/阴影补偿

**目标**
解决“字主体擦掉了，但描边和阴影还残留”的问题。

**建议实现**

- 基于边缘强度的外轮廓扩张
- 双层 mask：fill + outline
- 颜色反差辅助判断

**交付物**

- `app/mask/outline_mask.py`
- 参数可开关

**验收标准**

- 描边字样本集上残留明显下降

---

### T1.6 自适应膨胀替代固定膨胀

**目标**
替代 `kernel=(5,5)` 这类固定膨胀方式。

**建议规则**

根据以下信号动态确定 expand：

- 字块尺寸
- 字体粗细估计
- 背景复杂度
- 描边概率

**交付物**

- `app/mask/expand_policy.py`
- 配置项与 debug 输出

---

### T1.7 Mask QA 可视化

**目标**
让员工肉眼能快速判断 mask 对不对。

**必须输出**

- coarse mask
- refine mask
- overlay on original
- erase preview

**交付物**

- `runs/.../masks/`
- `mask_debug_board.png`

---

### T1.8 M1 验收报告

**目标**
完成 v1 mask 升级评估。

**必须包含**

- benchmark 前后对比
- 残字下降趋势
- 误伤下降趋势
- 失败样本归因
- 是否进入 M2

---

## 4. M2：Background Reconstruction Router

### T2.1 抽象统一 Inpainter 接口

**目标**
把 OpenCV / LaMa / ComfyUI 包成统一接口。

**交付物**

- `app/providers/inpainter/base.py`
- `opencv_inpainter.py`
- `comfy_inpainter.py`
- optional: `lama_inpainter.py`

---

### T2.2 实现 Fast Path

**目标**
默认先走轻量修复，提高速度。

**策略**

- crop-level inpaint
- refined mask
- paste back

**验收标准**

- 简单场景速度明显优于 HQ

---

### T2.3 实现 HQ Path

**目标**
面向复杂纹理区域。

**策略**

- crop-level diffusion inpaint
- 允许多候选生成
- 支持 prompt/template 注入

**交付物**

- HQ provider 模块
- 候选结果缓存

---

### T2.4 实现 QA 驱动路由

**目标**
不是人工指定 fast/hq，而是根据质量自动切换。

**输入信号**

- mask 复杂度
- 背景纹理复杂度
- residual_text_score
- edge_damage_score

**交付物**

- `app/core/router.py`
- 路由决策日志

---

### T2.5 实现失败回退策略

**目标**
避免 HQ 超时或失败直接整任务报废。

**交付物**

- timeout fallback
- retry policy
- 降级输出规范

---

### T2.6 输出 Reconstruction QA

**必须评分**

- residual_text_score
- edge_damage_score
- background_consistency_score

**交付物**

- `qa_report.json`
- `qa_preview.png`

---

## 5. M3：Layout Planner v1

### T3.1 定义 TextRegion 数据结构

**目标**
统一自动链路与未来精修链路的数据对象。

**交付物**

- `app/schemas/text_region.py`
- JSON schema

---

### T3.2 文本块分组

**目标**
把 OCR line 合成 block。

**规则**

- 距离
- 对齐
- 方向
- 行距
- 颜色近似

**交付物**

- `app/layout/grouping.py`

---

### T3.3 风格继承模块

**目标**
不要只拿平均色，要提取更合理的 style hint。

**至少支持**

- 主色
- 描边色
- 粗细倾向
- 对齐方式
- 角度

**交付物**

- `app/layout/style_infer.py`

---

### T3.4 自动换行与字号规划

**目标**
根据目标语言长度自动做行数与字号规划。

**交付物**

- `app/layout/planner.py`
- `app/layout/typography.py`

**验收标准**

- 英文膨胀 case 不再大量溢出
- 按钮文字不会被压成不可读小字

---

### T3.5 特殊区域识别规则

**目标**
为按钮、标题、价格标签建立专门策略。

**交付物**

- button/label/title rule pack

---

### T3.6 Layout QA

**输出评分**

- overflow score
- style mismatch score
- readability score

---

## 6. M4：Pipeline Productization

### T4.1 重构主流程到 `app/core/pipeline.py`

**目标**
结束脚本直跑式架构。

---

### T4.2 API 稳定化

**目标**
规范 `/process` `/erase` `/render` 行为与返回结构。

**交付物**

- 统一 response schema
- job id
- artifact path

---

### T4.3 CLI 批处理入口

**目标**
支持目录批量跑图。

---

### T4.4 运行产物统一

**必须包含**

- original
- OCR json
- coarse mask
- refine mask
- cleaned image
- rendered image
- qa report
- logs

---

### T4.5 配置治理

**目标**
所有 provider / threshold / path 全部配置化。

---

### T4.6 测试体系

**至少包含**

- 单测
- benchmark regression
- provider smoke test

---

## 7. M5：Manual Refinement Foundation

### T5.1 可编辑对象序列化

**目标**
将每个 text block 序列化，供后续精修画布读取。

---

### T5.2 局部重跑能力

**目标**
允许只对某个区域重做：

- mask refine
- inpaint
- render

---

### T5.3 局部笔刷接口准备

**目标**
为未来“智能消除笔”预留接口。

---

### T5.4 精修数据模型

**目标**
定义 canvas object / region object / edit action schema。

---

## 8. 优先级排序

### P0（立即做）

- T1.1 基线评测集
- T1.2 基线结果提取
- T1.3 Coarse Mask Builder
- T1.4 ROI Refine Mask v1
- T1.5 描边/阴影补偿
- T1.6 自适应膨胀
- T1.7 Mask QA 可视化
- T2.1 统一 Inpainter 接口
- T2.2 Fast Path

### P1（M1 完成后）

- T2.3 HQ Path
- T2.4 QA 驱动路由
- T2.5 失败回退
- T2.6 Reconstruction QA
- T3.1 TextRegion
- T3.2 文本块分组

### P2（主链稳定后）

- T3.3 风格继承
- T3.4 自动换行与字号规划
- T3.5 特殊区域策略
- T4.x 产品化任务
- T5.x 精修基础设施

---

## 9. 角色分工建议

### Architect / Tech Lead

负责：

- pipeline 边界
- provider 接口
- QA 评分体系
- 目录结构与配置治理

### CV Engineer

负责：

- mask refine
- outline compensation
- background reconstruction
- benchmark 评估

### Backend Engineer

负责：

- FastAPI
- job 管理
- artifact 管理
- 配置系统

### QA Engineer

负责：

- benchmark 数据集
- 回归测试
- case 分类
- 前后效果对比

### PM

负责：

- 里程碑边界控制
- 验收标准
- 长尾场景优先级
- 防止团队提前发散去做壳层/UI 花活

---

## 10. 明确禁止事项

1. 禁止在 M1 未完成前启动浏览器插件正式壳层开发
2. 禁止在 M1 未完成前把主要精力投入新翻译引擎接入
3. 禁止因为个别 case 难看就直接调大 dilation 当成“修复提升”
4. 禁止没有 benchmark 就宣称“新方法更好”
5. 禁止把 ComfyUI 工作流调参当成主线替代 mask 升级

---

## 11. M1 完成定义（Definition of Done）

满足以下条件，M1 才算完成：

1. benchmark 数据集建立完毕
2. baseline 与 refine v1 前后对比完整
3. 至少输出 coarse/refine/debug/erase preview 四类中间图
4. 在主要失败样本上可见质量提升
5. 有正式 M1 验收报告
6. 团队一致确认下一阶段主瓶颈已从“mask 不准”转移出去

---

## 12. 最后的执行建议

你这个项目当前最值得押注的，不是“再找一个更强 OCR”，也不是“再换一个更猛的 ComfyUI 模型”，而是：

> **把文本擦除从 OCR box 驱动，升级到 refined text mask 驱动。**

只要这一步完成，后面的背景修复、排版规划、精修工具，都会进入一个更健康的工程状态。

