import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR
import os

# 1. 初始化 OCR
engine = RapidOCR()

def erase_text(img_path, output_path="cleaned_image.jpg"):
    if not os.path.exists(img_path):
        print("❌ 找不到图片")
        return

    print(f"1. 正在读取图片: {img_path}")
    img = cv2.imread(img_path)
    
    # 获取图片的高、宽
    h, w = img.shape[:2]

    # 2. OCR 识别，获取坐标
    print("2. 正在识别文字坐标...")
    result, _ = engine(img_path)

    if not result:
        print("⚠️ 这张图没发现文字，无需擦除。")
        return

    # 3. 创建蒙版 (Mask)
    # 创建一张全黑的图，大小和原图一样（单通道，uint8类型）
    mask = np.zeros((h, w), dtype=np.uint8)

    for line in result:
        points = line[0] # 获取坐标 [[x1,y1], [x2,y2]...]
        
        # 将坐标转为整数格式，用于绘图
        points = np.array(points, dtype=np.int32)
        
        # 在 mask 上把文字区域填充为白色 (255)
        cv2.fillPoly(mask, [points], 255)

    # 4. 【关键步骤】蒙版膨胀 (Dilation)
    # 稍微把白色区域扩大一点，防止擦不干净留下边缘
    # kernel_size (5,5) 越大，扩大的范围越多
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)

    # 保存一下蒙版图，方便你调试观察 (看看是不是把字都盖住了)
    cv2.imwrite("debug_mask.jpg", mask)
    print("   -> 已生成蒙版图: debug_mask.jpg (请打开看看)")

    # 5. 开始修复 (Inpainting)
    # cv2.INPAINT_TELEA 是经典的修复算法，速度快，适合修补小区域文字
    # radius=3 是参考周围像素的半径
    print("3. 正在执行图像修复 (擦除文字)...")
    cleaned_img = cv2.inpaint(img, mask, 3, cv2.INPAINT_TELEA)

    # 6. 保存结果
    cv2.imwrite(output_path, cleaned_img)
    print(f"✅ 成功！已保存无字图: {output_path}")

# --- 运行测试 ---
# 请把这里的 'test.jpg' 换成你的测试图片
erase_text('test.jpg')