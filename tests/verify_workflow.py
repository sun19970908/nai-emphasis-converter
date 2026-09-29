# -*- coding: utf-8 -*-
"""验证工具：从 ComfyUI 工作流 JSON 里找 NaiEmphasisConverter 节点，
抽出它的真实输入（正/负提示词原文）和开关，用真实节点类跑一遍，打印输出。

用法：python verify_workflow.py [工作流.json]
"""
import importlib.util
import json
import os
import sys

# 本脚本位于 <节点目录>/tests/ 下，节点目录即上一级（仓库放在 custom_nodes 里即为安装位置）
NODE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_node_class():
    sys_module_name = NODE_DIR.replace(".", "_x_")
    spec = importlib.util.spec_from_file_location(
        sys_module_name, os.path.join(NODE_DIR, "__init__.py")
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[sys_module_name] = module
    spec.loader.exec_module(module)
    return module.NODE_CLASS_MAPPINGS["NaiEmphasisConverter"]


def widget_text(node):
    named = node.get("widgets_values_named") or {}
    if "text" in named:
        return named["text"]
    vals = node.get("widgets_values") or []
    return vals[0] if vals else ""


def main():
    if len(sys.argv) < 2:
        print("用法：python verify_workflow.py <工作流.json>")
        sys.exit(1)
    wf_path = sys.argv[1]
    with open(wf_path, encoding="utf-8") as f:
        wf = json.load(f)

    nodes = {n["id"]: n for n in wf["nodes"]}
    links = {l[0]: l for l in wf["links"]}
    converters = [n for n in wf["nodes"] if n.get("type") == "NaiEmphasisConverter"]
    if not converters:
        print("工作流里没有 NaiEmphasisConverter 节点")
        sys.exit(1)
    conv = converters[0]

    named = conv.get("widgets_values_named") or {}
    # 新版开关名「适配 Krea2 Prompt Weight」；旧工作流文件回退读 krea2_negative_one
    krea2 = bool(named.get("适配 Krea2 Prompt Weight", named.get("krea2_negative_one", False)))
    flags = {
        "flatten": bool(named.get("flatten", False)),
        "krea2_适配": krea2,
    }
    if not any(k in named for k in ("适配 Krea2 Prompt Weight", "krea2_negative_one")):
        print("警告：工作流里没存到 krea2 开关值，按关闭处理")
    print(f"工作流: {wf_path}")
    print(f"节点 #{conv['id']} 开关: {flags}")

    src_texts = {}
    for inp in conv.get("inputs", []):
        if inp.get("link") is None:
            continue
        link = links[inp["link"]]
        src_node = nodes[link[1]]
        src_texts[inp["name"]] = widget_text(src_node)
        print(f'输入 {inp["name"]} <- 节点 #{link[1]} ({src_node.get("type")})')

    positive = src_texts.get("positive", "")
    negative = src_texts.get("negative", "")

    node_cls = load_node_class()
    out_pos, out_neg = node_cls().convert(
        positive,
        negative,
        flags["flatten"],
        **{"适配 Krea2 Prompt Weight": flags["krea2_适配"]},
    )

    print("\n=== positive 输出（实际喂给采样器的串） ===")
    print(out_pos or "(空)")
    print("\n=== negative 输出 ===")
    print(out_neg or "(空)")


if __name__ == "__main__":
    main()
