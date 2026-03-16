# Legacy Code Mapping

当前工作区已补齐以下旧脚本文件：

- `step1_test.py`
- `step2_erase.py`
- `step3_universal_v1.1.py`

## 先行映射

基于设计文档，先定义迁移落点如下：

| 旧能力 | 目标模块 | 说明 |
|---|---|---|
| RapidOCR 识别验证 | `app/providers/ocr/rapidocr_provider.py` | 已迁移为懒加载 provider |
| polygon mask + OpenCV inpaint | `app/providers/inpaint/opencv_provider.py` | 已迁移为 fast 模式默认 provider |
| GoogleTranslator 翻译 | `app/providers/translator/local_provider.py` | 保持兼容旧脚本行为 |
| ComfyUI workflow 注入 / 轮询 / 下载 | `app/providers/inpaint/comfyui_provider.py` | 已迁移核心流程，仍待真实工作流联调 |
| 文本颜色提取 / 字号估算 / 描边 / 回填 | `app/render/` | 已拆到 `color_extractor.py` / `font_estimator.py` / `text_renderer.py` |
| 主流程 orchestration | `app/core/engine.py` | 已接入 OCR / 翻译 / mask / inpaint / render |

## 完整映射（M0-C 更新于 2026-03-16）

| 旧文件 | 函数/代码块 | 当前职责 | 新模块落点 | 迁移状态 |
|---|---|---|---|---|
| step1_test.py | RapidOCR 初始化与识别 | OCR 验证入口 | `app/providers/ocr/rapidocr_provider.py` | ✅ 已重构 |
| step2_erase.py | `erase_text` | mask + OpenCV inpaint | `app/providers/inpaint/opencv_provider.py` | ✅ 已重构 |
| step3_universal_v1.1.py | `get_smart_text_color` | 文字颜色提取 | `app/render/color_extractor.py` | ✅ 已重构 |
| step3_universal_v1.1.py | `draw_text_optimized` | 文字回填 | `app/render/text_renderer.py` | ✅ 已重构 |
| step3_universal_v1.1.py | `comfy_inpaint_universal` | HQ inpaint via ComfyUI | `app/providers/inpaint/legacy/comfyui_provider.py` | ✅ 迁至 legacy（M1） |
| step3_universal_v1.1.py | `main` | 总编排 | `app/core/engine.py` | ✅ 已重构 |
| test_v3.py | V3 mask 流程测试 | 历史验证脚本 | `scripts/legacy/test_v3.py` | ✅ 迁至 legacy（M1） |
| test_v4.py | V4 GrabCut 测试 | 历史验证脚本 | `scripts/legacy/test_v4.py` | ✅ 迁至 legacy（M1） |
| capture_baseline.py | 采集基准输出 | M0 基准采集工具 | `scripts/legacy/capture_baseline.py` | ✅ 迁至 legacy（M1） |
| run_test.py | 通用测试运行入口 | 历史调试脚本 | `scripts/legacy/run_test.py` | ✅ 迁至 legacy（M1） |
| convert_test.py | 图片格式转换测试 | 历史调试脚本 | `scripts/legacy/convert_test.py` | ✅ 迁至 legacy（M1） |

## 说明

所有迁至 `scripts/legacy/` 的脚本均**只读保留**，不再参与主流程。
对应功能已由 `app/` 目录下的模块接管。
删除前需确认 `tests/test_smoke.py` 仍然通过。
