# -*- coding: utf-8 -*-
"""WeiLin 提示词锚点节点（占位兼容 + 元数据可读）。

背景：原 weilin-comfyui-prompt-all-in-one 在 ComfyUI 0.37 + Python 3.12 嵌入环境
加载失败（pkg_resources / comfy storage 撞名），已停用。
本包注册与真节点相同的两个类名，用途有二：
  1. 旧工作流里的 WeiLin 节点不再报「缺失节点」；
  2. ⭐ spell（魔法咒语解析）类元数据工具可以直接从出图 PNG 里读出提示词——
     spell 扫描 prompt 块时优先认 WeiLinComfyUIPromptAllInOneGreat/Neg 这两个
     class_type，并直接取 inputs.text，不穿透链接。

用法（方案 b · 文本源头）：
  提示词填在本节点的 text 框里作为唯一源头，STRING 输出接进下游
  （NaiEmphasisConverter / Krea2PromptWeight / CLIPTextEncode 均可）。
  ⚠️ text 不要从外面接线进来——一旦变成链接，PNG 元数据里存的就是
  [节点id, 槽位] 数组，spell 就读不到文字了。
"""

_TEXT_TOOLTIP = (
    "提示词填在这里（唯一源头，不要接线进来）。"
    "文字会原样输出给下游，并被 spell 等解析工具从出图 PNG 元数据里直接读出。"
)


class WeiLinPromptAnchor:
    """text 透传节点：widget 文本 → STRING 输出。正负面共用一个类。"""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "提示词填这里，作为唯一源头（不要接线进来）",
                    "tooltip": _TEXT_TOOLTIP,
                }),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    OUTPUT_TOOLTIPS = ("原样输出 text 框里的内容",)
    FUNCTION = "passthrough"
    CATEGORY = "prompt"
    DESCRIPTION = (
        "WeiLin 提示词锚点：原 weilin prompt-all-in-one 的占位兼容节点。"
        "text 框是提示词唯一源头，原样透传输出；出图 PNG 的元数据里会带 "
        "WeiLinComfyUIPromptAllInOneGreat/Neg 标记，spell 等解析工具可直接读出文字。"
    )

    def passthrough(self, text):
        return (text,)
