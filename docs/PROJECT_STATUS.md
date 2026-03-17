# OCR260314 项目进展报告

## 更新日期
2026-03-17

## 项目概述
本地图片翻译引擎（象寄替代），支持 OCR、背景修复、文字回填。

---

## 当前里程碑状态

| 里程碑 | 状态 | 说明 |
|--------|------|------|
| M0-A 基准样本 | ⚠️ 需补充 | 当前仅 5 张样本，需 30+ 张 |
| M0-B 烟雾测试 | ✅ 已完成 | 11 个测试全部通过 |
| M0-C 遗留脚本清单 | ✅ 已完成 | 已整理到 scripts/legacy/ |
| M1 移除 ComfyUI | ✅ 已完成 | ComfyUI 移至 legacy 目录 |
| M2 Provider 抽象 | ✅ 已完成 | InpaintProvider 接口已定义 |
| M3 背景分类+多后端 | ✅ 实现完成，⚠️ 存在算法缺陷 | 见下方算法审查报告 |
| M4 LaMa 后端 | ⏳ 待实现 | 复杂背景 Type D fallback |
| M5 Mask 精炼 | ✅ 实现完成，⚠️ 未集成 + 存在算法缺陷 | Pipeline 写好但 Engine 仍用旧 refiner |
| M6 检测/OCR 解耦 | ⏳ 可选 | 预留扩展 |
| M7 布局规划 | ✅ 已完成 | LayoutPlanner v1 已实现 |
| M8 Router 路由 | ✅ 已完成 | InpaintRouter 已集成 |
| M9 QA 硬化 | ✅ 已完成 | QAEvaluator 增强 |
| M10 API 刷新 | ⏳ 可选 | 预留 |
| M11 Premium 后端 | ⏳ 可选 | 预留 |

---

## 测试状态（2026-03-17）

| 测试套件 | 测试数 | 状态 |
|----------|--------|------|
| 烟雾测试 | 11 | ✅ 全部通过 |
| Provider 单元测试 | 13 | ✅ 全部通过 |
| 边界测试 | 10 | ✅ 全部通过 |
| **总计** | **34** | ✅ |

> 注意：测试全部基于合成数据。真实电商图片上的端到端效果待验证。

---

## 实测问题（第一轮测试结论）

经过第一轮真实图片测试，发现以下问题：

1. **黑色字体擦除效果差** — mask 无法准确覆盖低对比度黑色字体笔画
2. **文字擦除残影** — 边界可见，还原区域与背景有明显分界
3. **原图还原质量差** — 复杂背景区域填充效果差，颜色不连续

根因见下方算法审查报告。

---

## 算法审查报告（2026-03-17）

### 问题 1：Mask 精炼候选融合逻辑错误（高优先级）

**位置**：`app/providers/mask_refine/refine_pipeline.py` → `_fuse_candidates`

**当前做法**：
```
final = polygon OR Otsu OR 自适应阈值 OR Canny
```

**问题**：Otsu 假设双峰直方图，在低对比度区域（黑字深色背景）直方图单峰，阈值飘移到噪声区。OR 并集把噪声全部保留，mask 质量反而更差。

**正确做法**：
```
final = MORPH_CLOSE( polygon AND (Otsu OR adaptive) )
```
polygon 作为空间约束先验，阈值方法在 polygon 内做像素级精化。AND 确保噪声不会跑出 OCR 框范围。

---

### 问题 2：黑色字体分割在错误的颜色空间（高优先级）

**位置**：`app/providers/mask_refine/refine_pipeline.py` → `_generate_candidates`

**当前做法**：对原始灰度图做 `THRESH_BINARY_INV + THRESH_OTSU`。

**问题**：`_extract_features` 已经计算了 CLAHE 增强结果，但计算完就丢弃，实际阈值分割仍用原始 `features.gray`。

**正确做法**：
```python
# 已有：clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4,4))
# 已有：enhanced = clahe.apply(gray)
# 但没有传出 enhanced，candidates 里没有用它

# 应改为：对 enhanced 做阈值
_, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
```

CLAHE 对 LAB L 通道做局部对比度均衡，使黑色字体在局部窗口内被推到 0，背景推到中值，阈值分割稳定。

---

### 问题 3：所有 Provider 没有调用 Poisson Blend（高优先级）

**位置**：
- `app/providers/inpaint/strategies/solid_fill_provider.py`
- `app/providers/inpaint/strategies/gradient_fill_provider.py`
- `app/providers/inpaint/strategies/patch_synthesis_provider.py`

**问题**：`app/providers/inpaint/poisson_blend.py` 已实现 `cv2.seamlessClone` 封装，但三个 Provider 都用 Gaussian 软掩码线性混合代替，边界处颜色是 `α·fill + (1-α)·original`，留下可见的过渡带。

**设计文档要求**（ADR-014）：Poisson blending 是所有 Provider 的强制后处理。

**正确做法**：填充完成后调用 `poisson_blend.poisson_blend(filled_roi, mask_roi, original_roi)`，而不是 Gaussian 混合。

---

### 问题 4：PatchSynthesis 填充顺序错误（中优先级）

**位置**：`app/providers/inpaint/strategies/patch_synthesis_provider.py` → `_patch_match_fill`

**当前做法**：`np.where(mask_bool)` 按行扫描，每隔 5 个像素填一个，跳过边界区域。

**问题**：
- 填充时 patch 查询窗口含有未填充的 mask 区域，匹配结果无意义
- 边界像素（视觉最重要）因 `py-half < 0 则 continue` 被跳过
- 步长 5 导致大量像素未填充

**正确做法（Criminisi 洋葱剥皮）**：
```
优先级 P(p) = 置信度C(p) × 数据项D(p)
C(p) = 已知邻域像素数 / 总邻域像素数  （边界像素优先）
填充顺序：从 mask 边界向内，每次选优先级最高的像素先填
```
这确保每个像素填充时周围都是已知像素，patch 匹配有效。

---

### 问题 5：渐变拟合坐标未归一化（中优先级）

**位置**：`app/providers/inpaint/strategies/gradient_fill_provider.py` → `_fit_gradient`
**也影响**：`app/providers/bg_classifier/classifier.py` → `_test_gradient`

**问题**：设计矩阵 `A = [x, y, 1]`，x ∈ [0, 1920]，y ∈ [0, 1080]，各列尺度差 ~1000 倍。lstsq 内部 SVD 的条件数可达 10⁴，数值精度下降。

**正确做法**：
```python
x_norm = x_vals / w  # → [0, 1]
y_norm = y_vals / h  # → [0, 1]
A = np.column_stack([x_norm, y_norm, np.ones_like(x_norm)])
# 评估时同样归一化坐标
```

**附加改进**：仅对 mask ROI 2× bounding box 范围内的背景像素做局部拟合，而不是全图。局部渐变比全局渐变拟合更准确。

---

### 问题 6：背景采样被颜色过滤污染（中优先级）

**位置**：`solid_fill_provider.py` 和 `gradient_fill_provider.py`

**当前做法**：
```python
valid_region = (expanded_mask == 0) & (image[:, :, 0] != 0)
```

**问题**：`image[:, :, 0] != 0` 假设"黑色像素 = 文字"，但产品图常有黑色背景/边框，这些合法背景像素会被排除，导致采样偏向浅色区域，颜色估计偏差。

**正确做法**：用 eroded mask 的补集作为采样区，去掉颜色过滤：
```python
safe_bg_mask = (cv2.erode(mask, large_kernel) == 0) & (expanded_mask == 0)
```

---

### 问题 7：背景分类器方差计算与设计文档不符（中优先级）

**位置**：`app/providers/bg_classifier/classifier.py` → `_compute_variance`

**设计文档**：`if max(std_R, std_G, std_B) < threshold → FLAT`
**代码实现**：`return np.std(pixels, axis=0).mean()`

用 mean 会把高方差通道稀释。单通道渐变（如只有 R 通道变化的冷暖色系产品图）被漏判为 FLAT，导致用 SolidFill 填出错误颜色。

**修复**：改为 `.max()`。

---

### 问题 8：纹理检测 FFT 在随机像素上执行（中优先级）

**位置**：`app/providers/bg_classifier/classifier.py` → `_test_texture`

**问题**：`bg_pixels` 是随机采样的像素列表，被 reshape 成方形后做 FFT。随机排列的数字没有空间结构，FFT 输出是随机噪声的频谱，检测到的"峰值"没有物理意义。

**正确做法**：从背景区域裁出一块**空间连续的** crop，对其做 FFT：
```python
# 取背景 bounding box 内的连续区域而不是随机采样像素
bg_crop = image[bg_y1:bg_y2, bg_x1:bg_x2]
gray_crop = cv2.cvtColor(bg_crop, cv2.COLOR_BGR2GRAY)
fft = np.fft.fft2(gray_crop)
```

---

### 问题 9：M5 MaskRefinePipeline 未集成到 Engine（高优先级）

Engine 仍使用旧的 `refiner_v4.py`，M5 的所有改进对真实 pipeline 没有生效。需要在 `app/core/engine.py` 中切换到 `MaskRefinePipeline`。

---

## 优先级排序（修复路线图）

### Sprint-3：算法修复（当前阶段）

| 优先级 | 任务 | 影响模块 |
|--------|------|---------|
| 🔴 P1 | 接入 Poisson blend，替换所有 Provider 的 Gaussian 混合 | solid_fill / gradient_fill / patch_synthesis |
| 🔴 P2 | mask 融合改为 `polygon AND (Otsu OR adaptive)`，用 CLAHE L 通道分割 | refine_pipeline |
| 🔴 P3 | MaskRefinePipeline 集成到 Engine（替换旧 refiner） | engine.py |
| 🟡 P4 | PatchSynthesis 改为洋葱剥皮填充顺序 | patch_synthesis_provider |
| 🟡 P5 | 渐变拟合：坐标归一化 + 局部采样 | gradient_fill_provider / classifier |
| 🟡 P6 | 背景采样去掉颜色过滤，改用 eroded mask 补集 | solid_fill / gradient_fill |
| 🟡 P7 | 分类器方差改为 `.max()` | classifier |
| 🟡 P8 | 纹理检测改为对空间连续 crop 做 FFT | classifier |

### Sprint-4：模型后端（算法修复验证后）

| 任务 | 说明 |
|------|------|
| M4 LaMa 集成 | ADR-006 re-evaluation 先行，Type D fallback |
| M0-A 基准样本补充 | 收集 30+ 真实电商产品图 |
| 端到端基准对比 | Sprint-3 修复前后对比，数据证明改进效果 |

---

## 架构总览（当前实际状态）

```
Input Image
  → OCR (RapidOCR)
  → Mask 生成 [⚠️ 仍用旧 refiner_v4，M5 Pipeline 未接入]
  → BackgroundClassifier [⚠️ 方差/纹理检测有缺陷]
  → InpaintRouter → Provider 选择
       Type A → SolidFillProvider      [⚠️ 未用 Poisson blend]
       Type B → GradientFillProvider   [⚠️ 未用 Poisson blend，坐标未归一化]
       Type C → PatchSynthesisProvider [⚠️ 未用 Poisson blend，填充顺序错误]
       Type D → OpenCV Telea           [⚠️ LaMa M4 未实现，Telea 效果差]
  → LayoutPlanner (M7)
  → TextRenderer
  → QAEvaluator (M9)
  → Output
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| API 框架 | FastAPI |
| OCR | RapidOCR |
| 翻译 | deep-translator (Google) |
| 图像处理 | OpenCV, NumPy |
| 测试 | pytest |
| 模型后端（待接入） | LaMa (PyTorch) |
