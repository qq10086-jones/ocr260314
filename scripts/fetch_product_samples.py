#!/usr/bin/env python3
"""
电商产品图片采集脚本 — 内测基准样本用
===========================================
用途：为 OCR/Inpaint 管道收集带真实文字的电商产品图，供 benchmark 使用。

数据来源：
  1. 楽天市場 API（官方免费，需注册 applicationId）
     注册：https://developers.rakuten.com  → 应用管理 → 新建应用 → 拿 applicationId
  2. DuckDuckGo 图片搜索（无需注册，用于中文/英文商品图补充）

免责说明：
  本脚本仅用于内部测试，下载图片仅用于 QA benchmark，不用于商业用途。
  使用前请确认符合当地法律及各平台服务条款。

用法：
  # 不带 Rakuten key（只用 DuckDuckGo）
  python scripts/fetch_product_samples.py --count 30

  # 带 Rakuten key（质量更高的日文商品图）
  python scripts/fetch_product_samples.py --rakuten-key YOUR_APP_ID --count 30

  # 只跑某个分类
  python scripts/fetch_product_samples.py --category flat_bg --count 5
"""

import argparse
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# 目录配置
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
SAMPLES_DIR = REPO_ROOT / "docs" / "samples"
MANIFEST_PATH = SAMPLES_DIR / "manifest.json"

# ---------------------------------------------------------------------------
# 每个分类对应的搜索关键词
# flat_bg      → 纯色/白底商品图（电商最常见）
# gradient_bg  → 渐变背景商品图
# product_surface → 有材质/图案背景的商品图
# portrait     → 人物/模特穿搭图
# button_tag   → 含按钮/标签/价格牌的图
# outline_shadow → 有描边或阴影文字的商品图
# ---------------------------------------------------------------------------
CATEGORY_QUERIES = {
    "flat_bg": [
        "白背景 商品写真 日本語テキスト",
        "白底商品图 中文价格标签",
        "product photo white background japanese text",
    ],
    "gradient_bg": [
        "グラデーション背景 商品 日本語",
        "渐变背景 商品图 中文文字",
        "gradient background product banner chinese",
    ],
    "product_surface": [
        "商品パッケージ 日本語テキスト",
        "商品包装 中文说明文字",
        "product packaging japanese kanji text",
    ],
    "portrait": [
        "ファッション モデル 日本語テキスト",
        "服装模特 中文价格文字",
        "fashion model outfit japanese text overlay",
    ],
    "button_tag": [
        "通販 バナー 価格タグ 日本語",
        "电商 促销 价格标签 中文",
        "ecommerce banner price tag japanese",
    ],
    "outline_shadow": [
        "アウトライン 文字 商品 日本語",
        "描边文字 商品图 中文",
        "outlined text product image japanese chinese",
    ],
}


# ---------------------------------------------------------------------------
# Rakuten Ichiba API
# ---------------------------------------------------------------------------
RAKUTEN_SEARCH_URL = "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20220601"


def fetch_rakuten_images(
    app_id: str,
    keyword: str,
    count: int = 5,
) -> list[str]:
    """楽天商品検索 API から商品画像 URL リストを返す。"""
    params = {
        "applicationId": app_id,
        "keyword": keyword,
        "hits": min(count, 30),
        "imageFlag": 1,
        "availability": 1,
        "sort": "-reviewCount",
    }
    url = RAKUTEN_SEARCH_URL + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "ocr260314-benchmark/1.0 (internal QA tool)"}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    [Rakuten] 请求失败: {e}")
        return []

    urls = []
    for item_wrapper in data.get("Items", []):
        item = item_wrapper.get("Item", {})
        img_url = item.get("mediumImageUrls", [{}])[0].get("imageUrl", "")
        if img_url:
            # 楽天は //images.rakuten.co.jp/ から始まる場合あり
            if img_url.startswith("//"):
                img_url = "https:" + img_url
            urls.append(img_url)

    return urls[:count]


# ---------------------------------------------------------------------------
# DuckDuckGo Image Search（非公式 API、研究用途）
# ---------------------------------------------------------------------------
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "ja-JP,ja;q=0.9,zh-CN;q=0.8,en;q=0.7",
    "Accept-Encoding": "identity",
}


def fetch_bing_images(query: str, count: int = 10) -> list[str]:
    """Bing 图片搜索（解析 HTML），返回原始图片 URL 列表。"""
    params = urllib.parse.urlencode({"q": query, "first": 1, "count": count + 5})
    url = "https://www.bing.com/images/search?" + params
    try:
        req = urllib.request.Request(url, headers=_BROWSER_HEADERS)
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except Exception as e:
        print(f"    [Bing] 请求失败: {e}")
        return []

    # Bing 把原图 URL 编码在 murl 字段里
    urls = re.findall(r'murl&quot;:&quot;(https?://[^&<"]+?)&quot;', html)
    # 过滤掉水印图库（通常不可直接使用）
    skip_domains = ("shutterstock", "gettyimages", "istockphoto", "alamy", "dreamstime")
    urls = [u for u in urls if not any(d in u for d in skip_domains)]
    return urls[:count]


# ---------------------------------------------------------------------------
# 下载单张图片
# ---------------------------------------------------------------------------
def download_image(url: str, dest: Path, timeout: int = 15) -> bool:
    headers = {**_BROWSER_HEADERS, "Referer": "https://www.bing.com/"}
    try:
        # 处理 URL 中含非 ASCII 字符（如中文路径）的情况
        url = urllib.parse.quote(url, safe=":/?=&%#@!$'()*+,;[]")
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type.lower() and not url.lower().endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            ):
                return False
            data = resp.read()
        # 最小 10KB，过滤掉占位图
        if len(data) < 10_000:
            return False
        dest.write_bytes(data)
        return True
    except Exception as e:
        print(f"      下载失败 {url[:60]}… — {e}")
        return False


# ---------------------------------------------------------------------------
# manifest.json 更新
# ---------------------------------------------------------------------------
def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"samples": [], "created": "2026-03-17", "total": 0}


def save_manifest(manifest: dict) -> None:
    manifest["total"] = len(manifest["samples"])
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_to_manifest(manifest: dict, filename: str, category: str, source: str) -> None:
    # 避免重复
    for s in manifest["samples"]:
        if s["filename"] == filename:
            return
    manifest["samples"].append({
        "filename": filename,
        "category": category,
        "source": source,
        "expected_text_count": -1,   # -1 = 待手动标注
        "notes": "",
    })


# ---------------------------------------------------------------------------
# 主逻辑
# ---------------------------------------------------------------------------
def fetch_category(
    category: str,
    target_count: int,
    rakuten_key: Optional[str],
    rate_limit: float = 2.0,
) -> int:
    dest_dir = SAMPLES_DIR / category
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 计算已有图片数
    existing = list(dest_dir.glob("*.jpg")) + list(dest_dir.glob("*.png")) + list(dest_dir.glob("*.webp"))
    already = len(existing)
    need = target_count - already
    if need <= 0:
        print(f"  [{category}] 已有 {already} 张，跳过")
        return 0

    print(f"  [{category}] 已有 {already} 张，还需 {need} 张")
    manifest = load_manifest()
    queries = CATEGORY_QUERIES.get(category, [])
    downloaded = 0
    img_index = already + 1

    for query in queries:
        if downloaded >= need:
            break

        print(f"    搜索: {query!r}")

        # 来源 1：楽天 API
        urls = []
        if rakuten_key:
            urls = fetch_rakuten_images(rakuten_key, query, count=min(need - downloaded + 2, 10))
            time.sleep(rate_limit)

        # 来源 2：Bing Image Search 补充
        if len(urls) < (need - downloaded):
            bing_urls = fetch_bing_images(query, count=min(need - downloaded + 3, 12))
            urls.extend(bing_urls)
            time.sleep(rate_limit)

        for url in urls:
            if downloaded >= need:
                break

            ext = ".jpg"
            for candidate in (".png", ".webp", ".jpeg"):
                if candidate in url.lower():
                    ext = candidate if candidate != ".jpeg" else ".jpg"
                    break

            filename = f"{category}_{img_index:03d}{ext}"
            dest = dest_dir / filename

            if dest.exists():
                img_index += 1
                continue

            print(f"      [{img_index}] {url[:70]}…")
            ok = download_image(url, dest)
            if ok:
                src_label = "rakuten" if (rakuten_key and url in urls[:5]) else "bing"
                add_to_manifest(manifest, f"{category}/{filename}", category, src_label)
                downloaded += 1
                img_index += 1
                print(f"      ✓ 已保存 {filename}")
            time.sleep(rate_limit)

    save_manifest(manifest)
    print(f"  [{category}] 本次下载 {downloaded} 张")
    return downloaded


def main():
    parser = argparse.ArgumentParser(description="电商产品图片基准样本采集")
    parser.add_argument(
        "--rakuten-key",
        default=None,
        help="楽天 applicationId（在 developers.rakuten.com 免费注册获取）",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=30,
        help="每个分类的目标图片数量（默认 30）",
    )
    parser.add_argument(
        "--category",
        default=None,
        choices=list(CATEGORY_QUERIES.keys()),
        help="只采集指定分类（不填则采集全部）",
    )
    parser.add_argument(
        "--rate-limit",
        type=float,
        default=2.5,
        help="请求间隔秒数（默认 2.5，过低可能被封）",
    )
    args = parser.parse_args()

    if not args.rakuten_key:
        print(
            "[提示] 未提供 --rakuten-key，将只使用 DuckDuckGo。\n"
            "       楽天 API 可免费注册：https://developers.rakuten.com\n"
            "       注册后加上 --rakuten-key YOUR_ID 可获得更高质量的日文商品图。\n"
        )

    categories = [args.category] if args.category else list(CATEGORY_QUERIES.keys())
    per_category = args.count

    print(f"目标: {len(categories)} 个分类 × {per_category} 张/分类")
    print(f"保存到: {SAMPLES_DIR}\n")

    total = 0
    for cat in categories:
        total += fetch_category(
            cat,
            per_category,
            args.rakuten_key,
            args.rate_limit,
        )

    manifest = load_manifest()
    print(f"\n完成。共下载 {total} 张，manifest 总计 {manifest['total']} 条记录。")
    print(f"manifest 路径: {MANIFEST_PATH}")
    print("\n[下一步] 手动检查图片质量，在 manifest.json 中填写 expected_text_count。")


if __name__ == "__main__":
    main()
