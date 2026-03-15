# Local Image Translation Engine - 项目进展报告 (v3.0 - De-Comfy 序章)

**日期**：2026-03-15  
**阶段**：M0 (基准采集) 已完成 | M1 (去 Comfy 依赖) 启动中  
**汇报人**：Architect/PM Agent

---

## 1. 核心进展：M0 里程碑达成

我们已经成功完成了 **De-ComfyUI 重构前** 的最后一次基准固化。这为后续所有算法优化提供了“可追溯、可量化”的标尺。

### 1.1 基准集数据
- **归档路径**：`runs/benchmark_baseline_v3/`
- **样片规模**：4 张核心场景图（包含 JPG、高分辨率 PNG）。
- **技术栈快照**：V4 GrabCut 能量模型 + ComfyUI 260315 API 工作流 + RX 7900 XTX 加速。
- **采集数据**：每个样本均包含 `manifest.json`，记录了坐标、耗时及 Mask 覆盖率。

### 1.2 质量观察
- 在复杂纹理背景下，V4 Mask 的笔画剥离能力得到了初步验证。
- ComfyUI 链路在 7900 XTX 下表现稳定，但由于依赖 Node ID 映射，存在一定的“黑盒”维护风险。

---

## 2. 战略调整：v3.0 架构升级

根据最新设计文档 `ocr260314_design_doc_decomfy_v1.md`，我们正式决定：
1. **去 ComfyUI 化**：将 ComfyUI 从“核心骨架”剥离，转变为“外挂 Provider”。
2. **原生化**：引入 LaMa 等 Python 原生 Inpaint 模型，实现真正的离线生产力。
3. **架构解耦**：实现 `InpaintProvider` 统一接口，支持 Backend Router 自动路由。

---

## 3. 下一步任务清单 (Sprint-1)

1. [ ] **M1: 移除 ComfyUI 强依赖**：修改 `/health` 逻辑，确保 ComfyUI 关闭时引擎依然能启动。
2. [ ] **M2: Provider 抽象化**：定义 `InpaintProvider` 基类，重构 `app/providers/inpaint/` 目录。
3. [ ] **M5: 精细化 Mask Pipeline v1**：实现 `coarse/glyph/effect` 四级 Mask 系统。

---

## 4. 源码保护
- 已在 Git 中标记 Tag：`v3-baseline-captured`。
- 已将所有重构前的稳定代码 Push 至远程仓库。

---
*报告生成于：2026-03-15 23:25:00*
