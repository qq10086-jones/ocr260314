# Local Image Translation Engine v2.0 设计文档

## 1. 文档定位

本文档面向你当前 `ocr260314` 项目的下一阶段重构与产品化演进，目标不是从零重写，而是在现有仓库基础上，把“OCR 翻译 Demo”升级成“接近象寄/白鲸/数魔体验”的本地优先图片翻译与精修引擎。

本文档特别聚焦你目前最卡的核心问题：**图片文本擦除质量差**。

---

## 2. 结论先行

### 2.1 当前核心判断

你当前项目不是卡在 OCR，也不是卡在翻译，而是卡在：

**OCR 输出的文本框 ≠ 真正应被擦除的文字像素区域。**

现有链路主要是：

1. OCR 检测出文本 polygon / box
2. 对 polygon 直接 fill mask
3. 做 dilation 扩张
4. 用 OpenCV inpaint 或 ComfyUI inpaint 擦除

这个路线能跑通，但在以下场景天然会差：

- 描边字 / 阴影字 / 发光字
- 按钮里的字
- 字与图标挨得很近
- 曲线文字 / 倾斜文字
- 复杂纹理背景
- 文本框大、真实字形细
- OCR 框包含大量背景但缺少字形细节

本质问题是：

> 你现在做的是“box-level erase”，而商用品质需要的是“glyph-level / stroke-level erase + layout-aware repaint”。

### 2.2 你应该怎么升级

不要继续在“OCR box 膨胀半径”上死磕，而应该把系统拆成四层：

1. **Text Region Detection**：先精确找到文字区域，不要求先读准内容
2. **Text Mask Refinement**：把矩形/四边形框变成更接近真实字形的像素 mask
3. **Background Reconstruction**：在更准的 mask 上做局部重建
4. **Layout Reconstruction / Re-typesetting**：重新规划文字排版，而不是只在旧框里硬塞

---

## 3. 你当前项目的真实现状

### 3.1 已经具备的资产

你仓库里已经不是空壳，已经有以下基础：

- `step2_erase.py`：RapidOCR + polygon mask + dilation + OpenCV Telea
- `step3_universal_v1.1.py`：OCR + 翻译 + mask + ComfyUI inpaint + PIL 回填
- `app/` 模块化骨架：API / providers / render / services 已经预留
- `runs/` 调试产物结构
- `workflows/` ComfyUI workflow 模板
- 设计文档和任务清单 v1.1 已有第一版治理框架

### 3.2 当前最关键的短板

#### A. mask 来源过于粗糙

你现在的擦除区域主要来自 OCR 检测框，而不是文字像素分割结果。

#### B. 擦除器被迫背锅

很多时候不是修复模型不行，而是输入 mask 本身就不准。修复器会把本不该擦的边缘一起重建，导致：

- 非文字内容被污染
- 边缘糊掉
- 图标/按钮被吃掉
- 背景纹理断裂

#### C. 排版层还不够“结构化”

现在更像“识别完原位回填”，而不是“理解原排版结构后重建”。

#### D. 缺少可量化 QA 闭环

你已经有 `qa_report.json` 骨架思路，但还没有把它上升成真正的自动评分与回退路由中心。

---

## 4. 对象寄 / 白鲸 / 数魔这类插件的技术推断

> 下面是基于公开产品能力、交互形态、性能表现与行业常见路线做的工程推断，不是其内部实现的确定披露。

### 4.1 它们大概率不是“只靠 OCR 做 mask”

原因很简单：

如果只用 OCR box 做膨胀擦除，在复杂电商图里会经常留下残字边缘、按钮破坏、图文相邻污染，且“精修工具”会变成高频刚需。商用产品能做到较高首轮通过率，说明其自动链路前面至少多了一层 **text segmentation / refined region estimation**。

### 4.2 它们大概率有两阶段检测

比较合理的工程推断是：

#### 阶段 A：文本区域检测

目标是回答“哪里是文字”，不是先回答“文字是什么”。

可能路线：

- DBNet / DBNet++ 风格文本检测
- CRAFT 风格 character/affinity 检测
- YOLO/RT-DETR 风格文本块检测（用于粗召回）
- 场景文本检测 + 特征后处理

#### 阶段 B：区域精修

将粗检测框转成更适合擦除的精细 mask：

- grayscale + 自适应阈值 / Otsu
- stroke width / connected component
- alpha matting 风格 refine
- 小型 segmentation 网络
- SAM / EfficientSAM / 边缘引导分割（更偏交互精修）

### 4.3 它们大概率做了 layout reconstruction

也就是不只知道“有一行字”，还知道：

- 字块范围
- 行数
- 对齐方式
- 字体粗细倾向
- 颜色 / 描边 / 阴影
- 是否在色块按钮内
- 是否需要换行
- 目标语言膨胀率
- 该区域更适合缩字还是扩框

因此它们能实现：

- 一次翻译后基本保持原版式
- 译文过长时自动重新分行
- 精修时可以拖拽微调而不是全部重来

### 4.4 它们大概率有双通道修复

#### 轻量通道

适合简单纯色、弱纹理背景：

- OpenCV / classical inpaint
- LaMa / patch-based inpaint
- crop-level 快速修复

#### 高质量通道

适合复杂纹理、电商图、拟真背景：

- diffusion inpaint
- crop inpaint + paste back
- 掩码外锁定保护
- 多次候选择优

### 4.5 它们大概率有“自动 + 精修”产品分层

从产品角度看，这是必然：

- 自动链路负责 80% case
- 精修工作台处理长尾 case
- 自动结果与精修结果共享同一版式对象模型

也就是说，**精修不是补丁功能，而是自动链路的可视化后处理入口**。

---

## 5. v2.0 产品目标

### 5.1 核心目标

基于现有 `ocr260314`，构建一个本地优先、可插拔的图片翻译与精修引擎，使其在电商图和一般说明图场景下达到以下能力：

1. 自动检测文字区域
2. 自动生成高质量擦除 mask
3. 自动选择合适的修复器
4. 自动翻译并尽量保留原始风格
5. 自动重新排版以适配目标语言
6. 提供可视化精修工作台能力基础
7. 产出可追踪的中间结果和 QA 评分

### 5.2 非目标

当前阶段不做：

- 端到端大一统多模态模型训练
- 云端 SaaS 平台
- 视频逐帧翻译
- PDF 高保真排版引擎
- 真正 Photoshop 级图层系统
- 一开始就做浏览器商店正式发布

---

## 6. 设计原则

1. **本地优先**：默认离线 / 本地执行
2. **先修内核，再做壳层**：先 engine 后插件
3. **先把 mask 做对，再讨论修复器上限**
4. **快速模式与高质量模式并存**
5. **自动化优先，但必须留精修入口**
6. **中间产物全部可追踪**
7. **QA 驱动路由，而不是拍脑袋切模型**
8. **员工不可自由发挥越过阶段边界**

---

## 7. v2.0 总体架构

```text
Input Image
  -> Preprocess
  -> Text Region Detector
  -> Text Mask Refiner
  -> Text Structure Builder
  -> Translation Planner
  -> Background Reconstructor
  -> Typography / Layout Planner
  -> Renderer
  -> QA Evaluator
  -> Final Output + Debug Artifacts
```

### 7.1 模块分层

#### A. Detection Layer
负责：找出文本区域、方向、行块、段落块。

#### B. Mask Layer
负责：从“文本块”收缩到“真实文字像素区域”。

#### C. Reconstruction Layer
负责：擦除原文字并恢复背景。

#### D. Translation & Layout Layer
负责：翻译、重排版、风格继承。

#### E. QA Layer
负责：检测残字、外溢、背景损伤、排版不合理，并决定是否降级 / 回退 / 进精修。

---

## 8. 最关键技术路线：从 OCR Mask 升级到 Refined Mask

这是全项目的头号重点。

### 8.1 为什么 OCR box 天然不够

OCR 检测框通常适合“读字”，不适合“擦字”。

OCR 的目标是：

- 把字包住
- 便于裁剪识别

而擦字的目标是：

- 只擦文字及其描边/阴影
- 尽量不碰邻近图标和背景细节

两者优化目标完全不同。

### 8.2 v2.0 推荐三段式 mask 生成

#### Stage 1：Text Block Detection
输入整图，输出文本块 polygon。

建议路线：

- 短期：继续复用 RapidOCR / PaddleOCR 检测结果
- 中期：引入 DBNet 或 CRAFT 检测器
- 长期：增加场景分类后按域切检测器（电商图 / 漫画 / 海报）

#### Stage 2：Block-level Refine
在每个 text ROI 内做局部 mask 精修。

建议方法组合：

1. ROI 灰度化
2. 自适应阈值 + Otsu 双结果
3. connected components 过滤
4. 根据文字颜色分布和边缘强度选 mask
5. 形态学 closing/opening 去毛刺
6. 对描边字做双层 mask（fill + outline）

#### Stage 3：Confidence-based Merge
把多个候选 mask 合并成最终 erase mask。

融合信号：

- OCR polygon
- 阈值分割结果
- 边缘检测结果
- 颜色聚类结果
- 可能的 segmentation 模型输出

### 8.3 推荐实现等级

#### Level 1（最快落地）
**无需训练新模型**，只做工程增强：

- OCR polygon
- ROI 局部阈值分割
- Canny / Sobel 边缘
- connected components
- outline 补偿
- 自适应扩张而不是固定膨胀

这是你当前项目最值得先做的一步。

#### Level 2（效果显著提升）
引入现成文本检测器 / 文本分割器：

- DBNet / CRAFT
- 漫画域可接 manga text segmentation
- 对按钮字/海报字可尝试 YOLO 文本块检测 + refine

#### Level 3（接近商用品质）
增加专门的 text segmentation 模型：

- 输入：text ROI
- 输出：glyph alpha / binary mask / outline mask
- 训练数据：原图 + 标注文字像素 / 合成数据

---

## 9. 背景修复路线

### 9.1 修复器选择原则

修复器永远不能脱离 mask 单独评估。

#### Fast 模式
适合：

- 小字
- 纯色 / 弱纹理背景
- 批量场景

建议：

- OpenCV Telea / NS
- LaMa
- crop-level classical inpaint

#### HQ 模式
适合：

- 电商详情页
- 有材质纹理
- 文字覆盖产品边缘
- 背景复杂

建议：

- ComfyUI inpaint
- diffusers inpaint
- crop inpaint + paste back
- 候选多次生成 + QA 选优

### 9.2 关键工程原则

1. **尽量 crop 级修复，不做整图扩散**
2. **mask 外区域锁定保护**
3. **给修复器上下文边界，不只给字框本身**
4. **对复杂区域允许多候选重建**
5. **修复失败时要能回退到 fast mode 或人工精修**

### 9.3 推荐修复策略

#### 策略 A：Fast path

- text ROI 扩上下文 1.5~2.5 倍
- refined mask
- LaMa / OpenCV
- paste back
- QA

#### 策略 B：HQ path

- text ROI 扩上下文
- refined mask
- diffusion inpaint
- 生成 2~4 个候选
- QA 选最优
- paste back

---

## 10. 排版规划（Layout Planning）

这部分是从“能翻译”到“像产品”的关键差异。

### 10.1 版式对象模型

建议建立 `TextRegion` 统一对象：

```python
TextRegion:
  id
  polygon
  bbox
  source_text
  translated_text
  reading_direction
  font_style_hint
  color_hint
  outline_hint
  bg_type
  anchor_type
  group_id
  block_role
  render_constraints
```

### 10.2 排版规划步骤

#### Step 1：结构分组

把 OCR line 合成 block：

- 同方向
- 同对齐
- 同色系
- 行距相近
- 距离相近

#### Step 2：语言膨胀估计

不同翻译方向文字长度变化不同：

- 中 → 英：常膨胀
- 日 → 中：可能缩短
- 英 → 日：视场景变化

需要在排版前估计目标长度和换行数。

#### Step 3：区域可用空间评估

- 原文本框
- 擦除后可扩展空间
- 是否允许轻微越界
- 是否在按钮 / 标签 / 徽章内

#### Step 4：字体与样式继承

至少继承：

- 主颜色
- 描边颜色
- 粗细倾向
- 字号范围
- 对齐方式
- 旋转角度

#### Step 5：自动换行与缩放

优先级建议：

1. 保持字号可读
2. 允许智能换行
3. 轻微调整字距/行距
4. 最后才缩字号

### 10.3 特殊区域策略

#### 按钮 / 色块文字

不要只根据文字框排版，要识别按钮背景区域，把文字锚定在按钮中心。

#### 标题型大字

优先保风格与视觉重心，不要简单压缩成多行小字。

#### 价格 / 数字标签

保留数字可视权重和对齐，不随意换行。

---

## 11. QA 与自动回退机制

### 11.1 QA 不只是报表，要参与路由

建议输出以下评分：

- residual_text_score：残字概率
- edge_damage_score：mask 外边缘损伤
- background_consistency_score：背景连续性
- typography_overflow_score：排版溢出
- style_mismatch_score：风格不一致
- final_confidence

### 11.2 自动决策

#### Case A：Fast 合格
直接输出

#### Case B：Fast 不合格但可重试
切 HQ

#### Case C：HQ 仍不合格
进入精修工作台待人工微调

#### Case D：文字太少或检测不稳定
保守输出，仅做 OCR + overlay，不做 destructive erase

---

## 12. 精修工作台设计方向

### 12.1 为什么必须做

因为长尾 case 不可能全靠自动链路吃掉。

### 12.2 精修对象应与自动链路共用数据结构

不要做两个平行世界：

- 自动模式产出的 `TextRegion`、mask、候选修复结果
- 精修模式继续基于同一对象编辑

### 12.3 最小精修功能集

1. 文本块选中
2. 改译文
3. 改字号 / 颜色 / 描边 / 角度
4. 拖拽位置
5. 重新生成局部 mask
6. 局部修复笔刷
7. 局部重跑 inpaint
8. 导出最终结果

---

## 13. 推荐技术栈

### 13.1 检测层

短期：

- RapidOCR / PaddleOCR（先复用）

中期：

- DBNet / CRAFT
- 场景专用 detector（漫画 / 电商图）

### 13.2 mask refine 层

- OpenCV
- scikit-image
- numpy
- optional: SAM / EfficientSAM（用于交互）

### 13.3 修复层

Fast：

- OpenCV inpaint
- LaMa

HQ：

- ComfyUI
- diffusers inpaint

### 13.4 翻译层

- 继续保留 provider 插拔
- glossary / term base 预留接口

### 13.5 渲染层

- PIL / Pillow
- freetype / HarfBuzz（后续复杂排版可考虑）

### 13.6 服务层

- FastAPI
- job manifest
- artifact storage
- QA evaluator

---

## 14. 推荐目录演进

```text
app/
  api/
  core/
    pipeline.py
    router.py
  providers/
    ocr/
    detector/
    translator/
    inpainter/
    segmenter/
  mask/
    coarse_mask.py
    refine_mask.py
    outline_mask.py
    merge_mask.py
  layout/
    grouping.py
    planner.py
    typography.py
    style_infer.py
  render/
    painter.py
    compositor.py
  qa/
    evaluator.py
    scoring.py
  services/
    job_store.py
    artifacts.py
    locks.py
  schemas/
    text_region.py
    job_manifest.py
```

---

## 15. 分阶段实施策略

### Phase 1：先救火（2 周目标）

目标：

把“擦字质量”明显提升一个台阶，不引入训练。

只做：

- refined mask v1
- adaptive dilation
- ROI 局部阈值分割
- outline / shadow 补偿
- mask QA 图输出
- Fast / HQ 路由更清晰

### Phase 2：结构化升级

目标：

把系统从脚本真正升级为 pipeline 引擎。

只做：

- `TextRegion` 对象模型
- grouping + layout planner
- QA 决策器
- ComfyUI 候选择优

### Phase 3：产品化增强

目标：

接近“自动 + 精修”的商用工作台体验。

只做：

- 精修画布
- 局部笔刷擦除
- 文字块交互编辑
- 批处理任务队列

---

## 16. 最重要的 PM 判断

### 16.1 不要立刻追求“完全复刻象寄”

正确路线不是一开始就追 UI，而是先把下面这条链打透：

> 更准的 text mask → 更稳的局部修复 → 更合理的重排版

### 16.2 先打赢“自动首轮通过率”

真正决定用户体验的不是精修工具有多强，而是：

- 10 张图里几张第一次就能用
- 复杂按钮字是否还在糊
- 非文字区域是否被误伤
- 换成目标语言后版式是否还像原图

### 16.3 最有投资回报比的技术点

如果只能优先做一件事：

> **先做 Mask Refine Pipeline v1，而不是继续换更多修复模型。**

因为你现在的主瓶颈，不在“不会修复”，而在“喂给修复器的擦除区域不够准”。

---

## 17. 验收标准（v2.0）

### 17.1 技术验收

- 复杂商品图样本集上残字率明显下降
- mask 外非文字损伤显著下降
- 复杂按钮/描边字 case 不再大面积误伤
- Fast 与 HQ 有可解释切换标准
- runs 目录产物完整可追踪

### 17.2 产品验收

- 用户可看到原图 / mask / 无字图 / 译图 / QA 分数
- 至少支持自动输出 + 局部精修准备态
- API / CLI 都能跑通主链路

---

## 18. 最终建议（给你这个项目当前阶段）

你接下来不要再把主要精力放在：

- 单纯换 OCR
- 单纯换翻译引擎
- 单纯调 ComfyUI prompt
- 单纯加大 dilation

而应该把头号里程碑定为：

### M1：Mask Refine Pipeline v1

交付物必须包括：

1. 粗检测 mask
2. refine 后 mask
3. mask 质量 debug 图
4. 修复前后对比
5. QA 打分
6. 失败样本归档

只要 M1 打透，你后面的：

- ComfyUI 修复
- 自动排版
- 精修工作台
- 浏览器插件壳层

都会明显顺很多。

