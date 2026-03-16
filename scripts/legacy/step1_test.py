from rapidocr_onnxruntime import RapidOCR
import os
import time

# 1. 初始化 OCR 引擎
# RapidOCR 会自动检测有没有 DirectML (AMD显卡支持库)
# 如果检测到，它会自动利用显卡加速
engine = RapidOCR()

img_path = 'test.jpg'

if not os.path.exists(img_path):
    print("❌ 错误：找不到图片 test.jpg，请确认图片在代码同级目录下！")
else:
    print(f"🚀 开始识别图片：{img_path}")
    print("正在调用 AMD 显卡进行推理...")
    
    # 记录开始时间
    start_time = time.time()
    
    # 2. 执行识别
    result, elapse = engine(img_path)
    
    # 记录结束时间
    end_time = time.time()

    # 3. 打印结果
    if result:
        print(f"✅ 识别成功！耗时: {end_time - start_time:.4f} 秒")
        print("-" * 30)
        for line in result:
            coords = line[0] # 坐标 [左上, 右上, 右下, 左下]
            text = line[1]   # 文字内容
            conf = line[2]   # 置信度
            print(f"📝 文字: {text}\n📍 坐标: {coords}\n")
    else:
        print("⚠️ 未识别到任何文字。")