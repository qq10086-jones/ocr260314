import cv2
import numpy as np
from app.mask.refiner import MaskRefiner as MaskRefinerV3
from app.mask.refiner_v4 import MaskRefinerV4
from app.providers.ocr.rapidocr_provider import RapidOCROCRProvider

def test_v4_precision():
    img_path = "ocr260314/test.jpg"
    image = cv2.imread(img_path)
    if image is None: return

    print("--- OCR 检测中 ---")
    ocr = RapidOCROCRProvider()
    boxes = ocr.detect(image)

    print("--- 正在生成 V3 Mask (阈值分割) ---")
    v3 = MaskRefinerV3()
    mask_v3 = v3.refine_mask(image, boxes)

    print("--- 正在生成 V4 Mask (GrabCut 能量模型) ---")
    v4 = MaskRefinerV4()
    mask_v4 = v4.refine_mask(image, boxes)

    # 制作对比图
    h, w = image.shape[:2]
    compare = np.zeros((h, w * 2), dtype=np.uint8)
    compare[:, :w] = mask_v3
    compare[:, w:] = mask_v4
    
    # 在图上写字标注
    cv2.putText(compare, "V3 (Threshold)", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2)
    cv2.putText(compare, "V4 (GrabCut)", (w + 50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, 255, 2)

    cv2.imwrite("ocr260314/v4_mask_compare.png", compare)
    
    overlay_v4 = image.copy()
    overlay_v4[mask_v4 > 0] = [0, 0, 255]
    cv2.imwrite("ocr260314/v4_overlay_test.png", overlay_v4)

    print("\n--- 结果已保存 ---")
    print("对比图: ocr260314/v4_mask_compare.png")
    print("V4 叠加图: ocr260314/v4_overlay_test.png")

if __name__ == "__main__":
    test_v4_precision()
