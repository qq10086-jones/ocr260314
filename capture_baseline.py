import requests
import json
import os
import time
from pathlib import Path

def capture_baseline():
    base_dir = Path(__file__).parent.absolute()
    input_dir = base_dir / "test_photo"
    output_base = base_dir / "runs" / "benchmark_baseline_v3"
    output_base.mkdir(parents=True, exist_ok=True)
    
    api_url = "http://localhost:8000/process"
    
    # 获取所有文件并过滤图片
    photos = [p for p in input_dir.iterdir() if p.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp']]
    print(f"--- 开始基准采集：共 {len(photos)} 张图片 ---")

    for idx, photo_path in enumerate(photos):
        print(f"[{idx+1}/{len(photos)}] 正在处理: {photo_path.name}")
        
        payload = {
            "image_path": str(photo_path.absolute()).replace("\\", "/"),
            "mode": "hq",
            "tgt_lang": "zh-CN"
        }
        
        try:
            start_time = time.time()
            response = requests.post(api_url, json=payload, timeout=300)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                job_id = result.get("job_id")
                
                # 建立存储目录
                sample_dir = output_base / f"sample_{photo_path.stem}"
                sample_dir.mkdir(exist_ok=True)
                
                # 保存清单
                with open(sample_dir / "manifest.json", "w", encoding="utf-8") as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                
                # 记录成功
                print(f"    成功! JobID: {job_id}, 耗时: {elapsed:.2f}s")
            else:
                print(f"    失败! 状态码: {response.status_code}, 原因: {response.text}")
                
        except Exception as e:
            print(f"    连接错误: {e}")

    print(f"\n--- 基准采集完成！产物位于: {output_base} ---")

if __name__ == "__main__":
    capture_baseline()
