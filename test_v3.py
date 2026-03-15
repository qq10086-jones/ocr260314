import cv2
import numpy as np
from app.mask.refiner import MaskRefiner
from app.core.models import OCRBox
from app.providers.ocr.rapidocr_provider import RapidOCROCRProvider

def test_v3_precision():
    img_path = "ocr260314/test.jpg"
    image = cv2.imread(img_path)
    if image is None:
        print("找不到图片")
        return

    print("--- 正在识别文字 ---")
    ocr = RapidOCROCRProvider()
    boxes = ocr.detect(image)
    print(f"找到 {len(boxes)} 个字块")

    print("--- 正在生成 V3 精度 Mask ---")
    refiner = MaskRefiner()
    mask = refiner.refine_mask(image, boxes)

    # 生成叠加图
    overlay = image.copy()
    overlay[mask > 0] = [0, 0, 255] # 红色

    # 保存
    cv2.imwrite("ocr260314/v3_mask_test.png", mask)
    cv2.imwrite("ocr260314/v3_overlay_test.png", overlay)
    print("--- 结果已保存 ---")
    print("Mask: ocr260314/v3_mask_test.png")
    print("Overlay: ocr260314/v3_overlay_test.png")

if __name__ == "__main__":
    test_v3_precision()
