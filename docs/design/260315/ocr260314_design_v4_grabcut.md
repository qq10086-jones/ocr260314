# Mask Refinement V4 设计文档：基于 GrabCut 的能量最小化方案

## 1. 问题诊断 (Problem Statement)
*   **当前痛点**：V3 及以前版本依赖 `Adaptive Thresholding`。在背景色彩复杂、渐变或低对比度场景下，算法无法区分“文字笔画”与“背景纹理”，导致分割结果塌陷回矩形方块（Mask Bloating）。
*   **数学本质**：一维标量（灰度）不足以描述特征空间，且缺乏空间连续性（Spatial Coherence）约束。

## 2. 数学原理 (Mathematical Theory)
V4 将引入 **GrabCut 算法**，其核心是求解马尔可夫随机场（MRF）的最小能量配置：
$$E(L) = E_{color}(L) + E_{smooth}(L)$$
*   **$E_{color}$ (Data Term)**：使用高斯混合模型（GMM）对前景（文字）和背景进行建模。
*   **$E_{smooth}$ (Smoothness Term)**：利用像素邻域的梯度信息，惩罚颜色相近但标签不同的像素，从而保证笔画的边缘锐利且连续。

## 3. 算法流程 (Algorithm Pipeline)
1.  **ROI 初始化**：以 OCR Box 为基准，向外扩展 5% 作为背景先验（Probable Background）。
2.  **交互式掩码生成**：
    *   `GC_PR_FGD` (可能的前景)：OCR 矩形内部区域。
    *   `GC_BGD` (确定的背景)：OCR 矩形外部的 Padding 区域。
3.  **迭代求解**：执行 5 轮 Graph Cut 迭代，自动收敛前景分布。
4.  **后处理滤波**：
    *   使用 **连通域分析** 过滤孤立噪点。
    *   使用 **形态学闭运算** 填充笔画内部孔洞。

## 4. 架构安全与回退机制
*   **逻辑隔离**：不直接修改 `refiner.py`，而是创建 `refiner_v4.py`。
*   **开关控制**：在 `config.yaml` 中预留版本切换参数。
*   **快照保护**：在执行前对当前稳定代码进行 Git Tag 标记。

---

# 任务清单 (Task List)

### T1：环境快照 (Snapshot)
- [ ] 对当前 V3 代码执行 Git Commit 备份。

### T2：核心算法开发 (Core Implementation)
- [ ] 创建 `app/mask/refiner_v4.py`。
- [ ] 实现基于 GMM 的 GrabCut 初始化逻辑。
- [ ] 实现笔画几何特征过滤器（长宽比、面积占比）。

### T3：一键测试与对比 (Validation)
- [ ] 更新 `test_v3.py` 为 `test_v4.py`。
- [ ] 输出 `v4_mask_compare.png`，量化 V3 vs V4 的精度提升。

### T4：集成与路由 (Integration)
- [ ] 在 `engine.py` 中通过配置动态加载 Refiner 版本。
