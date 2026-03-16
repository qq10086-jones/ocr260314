import requests
import json
import time
from pathlib import Path

def test_full_process():
    url = "http://localhost:8000/process"
    
    # 修改后的正确参数
    payload = {
        "image_path": "E:/0_zhuzhu/photo_editor/ocr260314/test.jpg",
        "mode": "hq",  # 这里的 hq 会对应 ComfyUI 模式
        "src_lang": "auto",
        "tgt_lang": "zh-CN",
        "translate": True
    }

    print(f"--- 启动翻译任务 (HQ 模式 + ComfyUI) ---")
    print(f"输入图片: {payload['image_path']}")

    try:
        # 发送请求，超时时间设长一点（ComfyUI 比较慢）
        response = requests.post(url, json=payload, timeout=600)
        
        if response.status_code == 200:
            result = response.json()
            print("\n--- 任务执行成功! ---")
            print(f"任务 ID: {result.get('job_id')}")
            print(f"运行模式: {result.get('mode')}")
            print(f"识别文字块数量: {len(result.get('tasks', []))}")
            print(f"结果图片路径: {result.get('output_path')}")
            print(f"耗时: {result.get('elapsed_seconds')} 秒")
            
            # 自动检查文件是否存在
            output_path = Path(result.get('output_path'))
            if output_path.exists():
                print(f"\n[大功告成] 图片已生成，请在此查看: {output_path.parent}")
        else:
            print(f"\n--- 任务失败! ---")
            print(f"状态码: {response.status_code}")
            print(f"详情: {response.text}")
            
    except Exception as e:
        print(f"\n[连接错误] 无法连接到服务: {e}")

if __name__ == "__main__":
    test_full_process()
