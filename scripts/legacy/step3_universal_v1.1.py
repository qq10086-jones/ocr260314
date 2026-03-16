import cv2
import numpy as np
from rapidocr_onnxruntime import RapidOCR 
from deep_translator import GoogleTranslator
from PIL import Image, ImageDraw, ImageFont
import os
import json
import urllib.request
import urllib.error
import uuid
import time
import textwrap
import random

# --- ⚙️ 配置中心 ---
COMFY_SERVER = "127.0.0.1:8188"
COMFY_ROOT_DIR = "D:\\comfyui2\\ComfyUI" 
IMG_PATH = "test.jpg"  
# ⚠️ 必须使用支持中文/日语的字体文件！推荐 'msyh.ttc' (微软雅黑) 或 'NotoSansCJK.otf'
FONT_PATH = "font.ttf" 
WORKFLOW_FILE = "workflow_layerstyle_251221_api.json"
EXPAND_PIXELS = 10     
INVERT_MASK_FOR_COMFYUI = True 

# --- 🌐 语言翻译模式选择 ---
# 可选模式: 
# 'auto2zh' (自动转中文), 'auto2en' (自动转英文), 'auto2ja' (自动转日文)
# 'en2zh', 'zh2en', 'zh2ja', 'ja2zh', 'en2ja', 'ja2en'
TRANSLATE_MODE = 'auto2zh'  # 👈 在这里修改你的目标

# --- 🛠️ 图像处理工具 ---
def resize_image_smart(img, max_side=1280):
    """智能缩放：保持比例，限制最长边"""
    h, w = img.shape[:2]
    if max(h, w) <= max_side: 
        return img, 1.0
    scale = max_side / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA), scale

def get_smart_text_color(img, box):
    """
    🎨 智能取色算法 v2.0
    不再傻傻取平均值，而是通过 Otsu 阈值分离前景和背景，
    精准提取文字的真实颜色。
    """
    xs = [int(p[0]) for p in box]; ys = [int(p[1]) for p in box]
    x_min, x_max = max(0, min(xs)), min(img.shape[1], max(xs))
    y_min, y_max = max(0, min(ys)), min(img.shape[0], max(ys))
    
    # 截取 ROI
    roi = img[y_min:y_max, x_min:x_max]
    if roi.size == 0: return (0, 0, 0) # 默认黑色

    # 转灰度
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # 使用 Otsu 自动阈值分割前景和背景
    # mask: 255=前景(或背景), 0=背景(或前景)
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # 统计 0 和 255 的数量
    count_white = np.sum(mask == 255)
    count_black = np.sum(mask == 0)
    
    # 假设：文字的面积通常小于背景面积
    # 如果白色像素少，说明白色是文字；反之黑色是文字
    if count_white < count_black:
        text_mask = (mask == 255)
    else:
        text_mask = (mask == 0)
    
    # 如果没分离出来（比如纯色块），回退到取中心点
    if np.sum(text_mask) == 0:
        return (int(img[y_min+roi.shape[0]//2, x_min+roi.shape[1]//2][2]), 
                int(img[y_min+roi.shape[0]//2, x_min+roi.shape[1]//2][1]), 
                int(img[y_min+roi.shape[0]//2, x_min+roi.shape[1]//2][0]))

    # 计算文字区域的平均颜色
    # roi[text_mask] 得到所有文字像素的 BGR 值
    mean_val = cv2.mean(roi, mask=text_mask.astype(np.uint8))
    
    # 返回 RGB
    return (int(mean_val[2]), int(mean_val[1]), int(mean_val[0]))

# --- ComfyUI 核心逻辑 ---
def queue_prompt(prompt_workflow):
    p = {"prompt": prompt_workflow, "client_id": str(uuid.uuid4())}
    data = json.dumps(p).encode('utf-8')
    try:
        req = urllib.request.Request(f"http://{COMFY_SERVER}/prompt", data=data)
        return json.loads(urllib.request.urlopen(req).read())
    except Exception as e:
        print(f"❌ 任务发送失败: {e}")
        return None

def get_history(prompt_id):
    try:
        url = f"http://{COMFY_SERVER}/history/{prompt_id}"
        with urllib.request.urlopen(url) as response:
            return json.loads(response.read())
    except:
        return {}

def wait_for_images(prompt_id, timeout=120):
    print(f"   ⏳ 任务已提交 (ID: {prompt_id})，正在等待生成结果...")
    start_time = time.time()
    while True:
        if time.time() - start_time > timeout:
            print("❌ 等待超时！")
            return {}
        history = get_history(prompt_id)
        if prompt_id in history:
            print(f"   ✅ 检测到任务完成！耗时: {time.time() - start_time:.1f}s")
            return history[prompt_id]
        time.sleep(1)

def get_image_data(filename, subfolder, folder_type):
    try:
        data = urllib.request.urlopen(
            f"http://{COMFY_SERVER}/view?filename={filename}&subfolder={subfolder}&type={folder_type}"
        ).read()
        return data
    except Exception as e:
        print(f"❌ 图片下载失败: {e}")
        return None

def comfy_inpaint_universal(image_cv, mask_cv):
    # 1. 缩放
    resized_img, _ = resize_image_smart(image_cv)
    h, w = resized_img.shape[:2]
    
    resized_mask = cv2.resize(mask_cv, (w, h), interpolation=cv2.INTER_NEAREST)
    if INVERT_MASK_FOR_COMFYUI:
        resized_mask = cv2.bitwise_not(resized_mask)

    # 2. 保存临时文件
    input_dir = os.path.join(COMFY_ROOT_DIR, "input")
    if not os.path.exists(input_dir):
        print(f"❌ 路径不存在: {input_dir}")
        return image_cv
    
    rnd = random.randint(0, 99999)
    fname_img = f"temp_ocr_{rnd}.png"
    fname_mask = f"temp_mask_{rnd}.png"
    
    cv2.imwrite(os.path.join(input_dir, fname_img), resized_img)
    
    mask_rgba = np.zeros((h, w, 4), dtype=np.uint8)
    mask_rgba[:, :, 3] = resized_mask 
    
    cv2.imwrite(os.path.join(input_dir, fname_mask), mask_rgba)

    # 3. 加载 workflow
    if not os.path.exists(WORKFLOW_FILE):
        print(f"❌ 找不到 {WORKFLOW_FILE}")
        return image_cv
    
    with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
        workflow = json.load(f)

    # 4. 节点注入
    IMAGE_NODE_ID = "1"
    MASK_NODE_ID = "8"
    
    if IMAGE_NODE_ID in workflow:
        workflow[IMAGE_NODE_ID]['inputs']['image'] = fname_img
    if MASK_NODE_ID in workflow:
        workflow[MASK_NODE_ID]['inputs']['image'] = fname_mask

    # 5. 执行
    res = queue_prompt(workflow)
    if not res: return image_cv
    result_data = wait_for_images(res['prompt_id'])
    
    if not result_data or 'outputs' not in result_data:
        return image_cv

    # 6. 获取结果
    final_img = image_cv
    for node_id, output in result_data['outputs'].items():
        if 'images' in output:
            for img_info in output['images']:
                raw_data = get_image_data(img_info['filename'], img_info['subfolder'], img_info['type'])
                if raw_data:
                    final_arr = np.asarray(bytearray(raw_data), dtype=np.uint8)
                    decoded = cv2.imdecode(final_arr, cv2.IMREAD_COLOR)
                    final_img = cv2.resize(decoded, (image_cv.shape[1], image_cv.shape[0]))
                    return final_img
    return final_img

def draw_text_optimized(draw, text, box, color):
    """
    🎨 优化的文字绘制：
    1. 动态描边：小字不描边，大字描边。
    2. 增加行间距。
    3. 垂直水平更精准居中。
    """
    xs = [p[0] for p in box]; ys = [p[1] for p in box]
    x_min, y_min = min(xs), min(ys)
    x_max, y_max = max(xs), max(ys)
    box_w = x_max - x_min
    box_h = y_max - y_min
    
    # --- 1. 字号估算策略优化 ---
    # 标题类（框很大）：用 60% 高度
    # 正文类（框很小）：用 75% 高度 (因为小字需要更大才看得清)
    if box_h > 50:
        target_h = box_h * 0.6
    else:
        target_h = box_h * 0.75
        
    font_size = int(target_h)
    if font_size < 10: font_size = 10 
    
    try: font = ImageFont.truetype(FONT_PATH, font_size)
    except: font = ImageFont.load_default()
    
    # --- 2. 计算多行文本宽高 ---
    # 如果文字太长，进行换行处理，或者缩小字号
    # 这里我们采用“先尝试缩小字号，实在不行再换行”的策略
    
    avg_char_w = font_size * 0.5 # 估算
    if len(text) * avg_char_w > box_w * 1.2: # 如果文字明显比框宽
        # 缩小字号
        scale_factor = (box_w * 0.95) / (len(text) * avg_char_w)
        font_size = int(font_size * scale_factor)
        if font_size < 10: font_size = 10 # 最小字号底线
        try: font = ImageFont.truetype(FONT_PATH, font_size)
        except: pass

    # 计算文字的实际边界
    try:
        left, top, right, bottom = font.getbbox(text)
        text_w = right - left
        text_h = bottom - top
        ascent, descent = font.getmetrics()
        line_height = ascent + descent
    except:
        text_w = font_size * len(text) * 0.6
        text_h = font_size
        line_height = font_size * 1.2

    # --- 3. 动态描边策略 (美感的关键！) ---
    # 只有当字号足够大时，才加描边，否则小字会糊成一团
    stroke_width = 0
    if font_size >= 24: 
        stroke_width = 2
    elif font_size >= 16:
        stroke_width = 1
    else:
        stroke_width = 0 # 小字保持清爽，不要描边

    # 描边颜色：如果字是深色，描边用白色；字是浅色，描边用黑色
    # 简单计算亮度 (0.299R + 0.587G + 0.114B)
    brightness = color[0]*0.299 + color[1]*0.587 + color[2]*0.114
    stroke_color = (255, 255, 255) if brightness < 150 else (0, 0, 0)

    # --- 4. 最终坐标计算 ---
    # 修正 Y 轴：Pillow 的绘制坐标是基线，需要视觉修正
    pos_x = x_min + (box_w - text_w) / 2
    pos_y = y_min + (box_h - text_h) / 2 - (text_h * 0.1) # 稍微往上提一点点，视觉更平衡
    
    # 绘制
    draw.text((pos_x, pos_y), text, font=font, fill=color+(255,), 
              stroke_width=stroke_width, stroke_fill=stroke_color+(255,))

# --- ✨ 主程序 ---
def main():
    if not os.path.exists(IMG_PATH):
        print(f"❌ 找不到图片: {IMG_PATH}")
        return
    
    print(f"📷 正在加载图片: {IMG_PATH}")
    original_img = cv2.imread(IMG_PATH)
    h, w = original_img.shape[:2]

    print("🚀 初始化 RapidOCR...")
    ocr = RapidOCR()
    
    # --- 🌐 初始化翻译器 ---
    print(f"🌍 正在初始化翻译器，模式: {TRANSLATE_MODE} ...")
    
    # 解析模式
    src_lang = 'auto'
    tgt_lang = 'en'
    
    if TRANSLATE_MODE == 'auto2zh': tgt_lang = 'zh-CN'
    elif TRANSLATE_MODE == 'auto2en': tgt_lang = 'en'
    elif TRANSLATE_MODE == 'auto2ja': tgt_lang = 'ja'
    elif TRANSLATE_MODE == 'en2zh': src_lang='en'; tgt_lang='zh-CN'
    elif TRANSLATE_MODE == 'zh2en': src_lang='zh-CN'; tgt_lang='en'
    elif TRANSLATE_MODE == 'zh2ja': src_lang='zh-CN'; tgt_lang='ja'
    elif TRANSLATE_MODE == 'ja2zh': src_lang='ja'; tgt_lang='zh-CN'
    elif TRANSLATE_MODE == 'en2ja': src_lang='en'; tgt_lang='ja'
    elif TRANSLATE_MODE == 'ja2en': src_lang='ja'; tgt_lang='en'
    
    translator = GoogleTranslator(source=src_lang, target=tgt_lang)
    
    print("🔍 正在识别...")
    result, elapse = ocr(IMG_PATH)

    raw_tasks = []
    mask = np.zeros((h, w), dtype=np.uint8)

    if result:
        print(f"✅ 识别到 {len(result)} 处文字！")
        
        for i, line in enumerate(result):
            coords = line[0]; text = line[1]
            
            # 翻译
            try: trans = translator.translate(text)
            except Exception as e: 
                print(f"⚠️ 翻译失败: {e}")
                trans = text
            
            print(f"   📝 [{i+1}] {text} -> {trans}")

            pts = np.array(coords, dtype=np.int32)
            
            # 🎨 使用新版智能取色
            color = get_smart_text_color(original_img, coords)

            raw_tasks.append({"box": coords, "text": trans, "color": color})
            cv2.fillPoly(mask, [pts], 255)
    else:
        print("⚠️ 未识别到文字。")
        return

    if EXPAND_PIXELS > 0:
        kernel = np.ones((EXPAND_PIXELS, EXPAND_PIXELS), np.uint8)
        mask = cv2.dilate(mask, kernel, iterations=1)
    
    cv2.imwrite("debug_mask_auto.png", mask)

    print("✨ 呼叫 ComfyUI...")
    cleaned_bg = comfy_inpaint_universal(original_img, mask)
    cv2.imwrite("debug_cleaned_bg.jpg", cleaned_bg)

    print("✍️ 原位回填文字...")
    base = Image.fromarray(cv2.cvtColor(cleaned_bg, cv2.COLOR_BGR2RGB)).convert("RGBA")
    txt_layer = Image.new("RGBA", base.size, (0,0,0,0))
    draw = ImageDraw.Draw(txt_layer)
    
    for task in raw_tasks:
        draw_text_optimized(draw, task['text'], task['box'], task['color'])
        
    final = Image.alpha_composite(base, txt_layer)
    res = cv2.cvtColor(np.array(final.convert("RGB")), cv2.COLOR_RGB2BGR)
    
    save_name = f"final_result_{int(time.time())}.jpg"
    cv2.imwrite(save_name, res)
    print(f"🎉 全部完成！结果已保存为: {save_name}")

if __name__ == "__main__":
    main()