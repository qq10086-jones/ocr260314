#!/usr/bin/env python3
"""
从公开图片源下载测试图片
"""

import os
import urllib.request
from pathlib import Path

# 公开图片源 (无需登录)
SOURCES = {
    "flat_bg": [
        "https://picsum.photos/800/800?random=1",
        "https://picsum.photos/800/800?random=2",
        "https://picsum.photos/800/800?random=3",
    ],
    "gradient_bg": [
        "https://picsum.photos/800/800?random=4",
        "https://picsum.photos/800/800?random=5",
        "https://picsum.photos/800/800?random=6",
    ],
    "product_surface": [
        "https://picsum.photos/800/800?random=7",
        "https://picsum.photos/800/800?random=8",
        "https://picsum.photos/800/800?random=9",
    ],
    "portrait": [
        "https://picsum.photos/800/800?random=10",
        "https://picsum.photos/800/800?random=11",
        "https://picsum.photos/800/800?random=12",
    ],
    "button_tag": [
        "https://picsum.photos/800/800?random=13",
        "https://picsum.photos/800/800?random=14",
        "https://picsum.photos/800/800?random=15",
    ],
    "outline_shadow": [
        "https://picsum.photos/800/800?random=16",
        "https://picsum.photos/800/800?random=17",
        "https://picsum.photos/800/800?random=18",
    ],
}

def download_images():
    base_dir = Path(__file__).parent.parent / "docs" / "samples"
    
    for category, urls in SOURCES.items():
        category_dir = base_dir / category
        category_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[{category}] 下载中...")
        
        for i, url in enumerate(urls):
            filename = f"{category}_{i+1}.jpg"
            filepath = category_dir / filename
            
            try:
                urllib.request.urlretrieve(url, filepath)
                print(f"  - {filename}")
            except Exception as e:
                print(f"  - 失败: {e}")
    
    print("\n下载完成!")

if __name__ == "__main__":
    download_images()
