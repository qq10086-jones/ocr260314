import json

def convert():
    with open('ocr260314/workflow_layerstyle_260315_api.json', encoding='utf-8') as f:
        data = json.load(f)
    
    # 如果是 UI 格式，提取 nodes 列表并转为字典
    if "nodes" in data:
        nodes = data["nodes"]
        api_format = {}
        for node in nodes:
            node_id = str(node["id"])
            api_format[node_id] = {
                "inputs": {k: v for k, v in node.get("inputs", {}).items() if "link" not in str(v)},
                "class_type": node["type"],
                "_meta": {"title": node.get("title", node["type"])}
            }
            # 处理链接 (简单的回填逻辑)
            # 这里由于 ComfyUI 的链接复杂，手动转 100% 会出错
            # 所以我们还是建议从 UI 界面点击 'Save (API format)' 重新导出
        
        print("错误：此工作流是 UI 格式。请在 ComfyUI 开启 'Dev Mode' 后点击 'Save (API format)' 重新导出。")

if __name__ == "__main__":
    convert()
