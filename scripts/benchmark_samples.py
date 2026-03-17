#!/usr/bin/env python3
"""
M0-A 基准样本批量测试脚本（离线模式）
直接调用 Engine，无需启动 HTTP Server。
"""

import json
import time
from pathlib import Path

from app.core.config import load_config
from app.core.engine import ImageTranslationEngine
from app.core.models import ProcessRequest
from app.providers.inpaint.opencv_provider import OpenCVInpainter
from app.providers.ocr.rapidocr_provider import RapidOCROCRProvider
from app.providers.translator.noop import NoOpTranslator
from app.providers.translator.local_provider import GoogleTranslatorProvider
from app.render.text_renderer import TextRenderer
from app.services.job_service import JobService
from app.services.lock_service import ProcessLockService

SAMPLES_DIR = Path(__file__).parent.parent / "docs" / "samples"
CATEGORIES = [
    "flat_bg",
    "gradient_bg",
    "product_surface",
    "portrait",
    "button_tag",
    "outline_shadow",
]


def build_engine() -> ImageTranslationEngine:
    config = load_config()

    # Renderer 使用本地 Windows 字体，完全离线免费
    font_path = str(config.render.font_path)
    try:
        renderer = TextRenderer(font_path=font_path)
        print(f"  Renderer: {font_path}")
    except Exception as e:
        print(f"  Renderer 初始化失败 ({e})，将跳过文字回填")
        renderer = None

    # Google Translate (deep-translator, 免费无需 API key)
    try:
        translator = GoogleTranslatorProvider()
        print("  翻译: Google Translate (免费)")
    except Exception:
        translator = NoOpTranslator()
        print("  翻译: 不可用，使用 NoOp")

    return ImageTranslationEngine(
        config=config,
        ocr_provider=RapidOCROCRProvider(),
        translator_provider=translator,
        fast_inpainter=OpenCVInpainter(expand_pixels=config.inpaint.expand_pixels),
        hq_inpainter=None,
        renderer=renderer,
        lock_service=ProcessLockService(),
        job_service=JobService(config),
    )


def process_image(engine: ImageTranslationEngine, image_path: Path) -> dict:
    request = ProcessRequest(
        image_path=image_path,
        src_lang="auto",
        tgt_lang="zh-CN",
        mode="smart",
        translate=True,
    )
    start = time.perf_counter()
    try:
        result = engine.process(request)
        elapsed = round(time.perf_counter() - start, 2)
        return {
            "status": "success",
            "elapsed_seconds": elapsed,
            "text_count": len(result.tasks),
            "output_path": result.output_path,
            "warnings": result.warnings,
            "qa_stats": result.timings.__dict__ if result.timings else {},
        }
    except Exception as e:
        import traceback
        elapsed = round(time.perf_counter() - start, 2)
        return {
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc(),
            "elapsed_seconds": elapsed,
        }


def main():
    print("=" * 60)
    print("M0-A 基准样本批量测试  [smart 模式 / 离线]")
    print("=" * 60)

    print("\n初始化 Engine...", flush=True)
    engine = build_engine()
    print("Engine 就绪\n")

    results = []
    total = 0
    success = 0

    for category in CATEGORIES:
        cat_dir = SAMPLES_DIR / category
        if not cat_dir.exists():
            continue

        images = sorted(
            list(cat_dir.glob("*.jpg"))
            + list(cat_dir.glob("*.png"))
            + list(cat_dir.glob("*.webp"))
        )
        if not images:
            print(f"[{category}] 无图片，跳过")
            continue

        print(f"[{category}]  {len(images)} 张")
        for img in images:
            total += 1
            print(f"  {img.name:<35}", end=" ", flush=True)
            r = process_image(engine, img)
            r["category"] = category
            r["filename"] = img.name
            results.append(r)

            if r["status"] == "success":
                success += 1
                print(f"✓  {r['elapsed_seconds']:.1f}s  {r['text_count']} 框  {r['warnings'] or ''}")
            else:
                print(f"✗  {r['error'][:80]}")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总")
    print("=" * 60)
    print(f"总图片:  {total}")
    print(f"成功:    {success}")
    print(f"失败:    {total - success}")
    if total > 0:
        print(f"成功率:  {success / total * 100:.1f}%")

    ok = [r for r in results if r["status"] == "success"]
    if ok:
        times = [r["elapsed_seconds"] for r in ok]
        print(f"平均耗时: {sum(times)/len(times):.1f}s  最慢: {max(times):.1f}s")

    print("\n按分类:")
    cat_stats: dict = {}
    for r in results:
        c = r["category"]
        cat_stats.setdefault(c, {"total": 0, "success": 0, "times": []})
        cat_stats[c]["total"] += 1
        if r["status"] == "success":
            cat_stats[c]["success"] += 1
            cat_stats[c]["times"].append(r["elapsed_seconds"])
    for c, s in sorted(cat_stats.items()):
        avg = sum(s["times"]) / len(s["times"]) if s["times"] else 0
        print(f"  {c:<20} {s['success']}/{s['total']}  avg {avg:.1f}s")

    # 保存报告
    report = {
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "mode": "smart",
        "total": total,
        "success": success,
        "failed": total - success,
        "success_rate": f"{success/total*100:.1f}%" if total else "0%",
        "results": results,
    }
    report_path = SAMPLES_DIR / "benchmark_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已保存: {report_path}")


if __name__ == "__main__":
    main()
