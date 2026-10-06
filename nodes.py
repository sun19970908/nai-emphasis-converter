# -*- coding: utf-8 -*-
"""NAI 强调语法转换 · ComfyUI 节点。

开关与处理顺序（编号即执行顺序）：
  ⓪ 回车补逗号（默认开）      行尾补英文逗号      _ensure_comma_before_newlines，正负两侧，转换之前
  ①（始终执行）NAI 语法转换      convert_prompt_pair   ::/{} /[] → (tag:N)，负权重分流到负面
  ② flatten        权重全部归 1    strip_all_weights     剥掉所有权重壳，只留裸 tag
  ③「适配 Krea2 Prompt Weight」  一键两件事（负面串权重 ×(-1) + 并进正面输出）：
      Krea2 Prompt Weight 这类工作流没有可用的 negative 槽位（KSampler cfg=1 吃不到负面），
      负面约束只能以负权重写进正面提示词，交给下游 Krea2PromptWeight 节点处理。
      转换后的负面串仍照常从 negative 输出口输出，想单独接线也有。

输入名直接用中文（「适配 Krea2 Prompt Weight」）：前端部件标题显示的就是输入名，
BOOLEAN 没有独立的显示名选项；中文/带空格输入名在本环境可用（Apt_Preset 同款做法）。
"""

from .nai_emphasis import (
    convert_prompt_pair,
    strip_all_weights,
    to_negative_one_tags,
    _join_non_empty,
)


def _ensure_comma_before_newlines(text):
    """给每个换行前的行尾补一个英文逗号（在所有转换逻辑之前执行）。

    规则：该行 rstrip 后非空、且不以英文逗号结尾 → 行尾补一个 ","。
    空行不补；已有英文逗号不补；全角逗号/顿号不算（照样补）。
    兜住编辑器「回车吞逗号」造成的两行 tag 粘连——普通 tag 合并只是
    编码器里换行当空格的小差异，但会把 (tag:-1) 这类 A1111 负权重壳
    连进上一行、分流失效。
    """
    if not text or "\n" not in text:
        return text
    lines = text.split("\n")
    for i in range(len(lines) - 1):  # 最后一行后面没有换行，不处理
        stripped = lines[i].rstrip()
        if not stripped or stripped.endswith(","):
            continue
        lines[i] = stripped + ","
    return "\n".join(lines)


class NaiEmphasisConverter:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "positive": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "NAI 语法正面提示词，如：masterpiece, 1girl, {detailed eyes}, 1.3::blonde hair, -1.4::watermark",
                    "tooltip": "NovelAI V4/V4.5 正面提示词。支持 1.3::段落、{加强}、[减弱]、-1.4::负权重、(tag:-1)。",
                }),
                "negative": ("STRING", {
                    "multiline": True,
                    "default": "",
                    "placeholder": "NAI 语法负面提示词（可留空），如：1.3::bad hands, [blurry]",
                    "tooltip": "NovelAI 负面提示词，只做语法转换不分流。勾了「适配 Krea2 Prompt Weight」后会被 ×(-1) 并进正面。",
                }),
                "flatten": ("BOOLEAN", {
                    "default": False,
                    "label_on": "权重归 1",
                    "label_off": "保留权重",
                    "tooltip": "② 权重全部归 1：剥掉所有 (tag:N) 外壳，只留裸 tag。在转换分流之后执行。",
                }),
                "适配 Krea2 Prompt Weight": ("BOOLEAN", {
                    "default": False,
                    "label_on": "启用",
                    "label_off": "关闭",
                    "tooltip": "③ 一键适配 Krea2 Prompt Weight 工作流：负面串权重 ×(-1)（(tag:1.4)→(tag:-1.4)，裸 tag→(tag:-1)），并把结果并进 positive 输出。positive 输出直接接 Krea2PromptWeight 节点即可。",
                }),
                "回车补逗号": ("BOOLEAN", {
                    "default": True,
                    "label_on": "开启",
                    "label_off": "关闭",
                    "tooltip": "在所有转换逻辑之前执行：行尾没有英文逗号的行，在换行前自动补一个英文逗号，兜住编辑器回车吞逗号造成的 tag 粘连。空行不补；行尾已有英文逗号不补；全角逗号/顿号不算。",
                }),
            },
        }

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("positive", "negative")
    OUTPUT_TOOLTIPS = ("转换后的正面提示词（勾了「适配 Krea2 Prompt Weight」时已含并入的负权重）", "转换后的负面提示词（勾了「适配 Krea2 Prompt Weight」时已整体 ×(-1)，照常输出备用）")
    FUNCTION = "convert"
    CATEGORY = "prompt"
    DESCRIPTION = "NovelAI V4/V4.5 强调语法（:: / {} / [] / 负权重）→ ComfyUI (tag:N) 语法，负权重自动分流到负面槽。与 nai-emphasis-share 网页版同一套转换逻辑。"

    def convert(self, positive, negative, flatten, **kwargs):
        # 「适配 Krea2 Prompt Weight」「回车补逗号」名字含空格/中文，Python 形参
        # 写不出，用 **kwargs 接：调用时按输入名精确取。
        krea2_mode = bool(kwargs.get("适配 Krea2 Prompt Weight", False))
        auto_comma = bool(kwargs.get("回车补逗号", True))

        if auto_comma:
            # ⓪ 所有转换逻辑之前：给回车前的行尾补英文逗号（正负两侧都做）
            positive = _ensure_comma_before_newlines(positive)
            negative = _ensure_comma_before_newlines(negative)

        positive_out, negative_out = convert_prompt_pair(positive=positive, negative=negative)

        if flatten:
            # ② 必须排在分流之后（convert_prompt_pair 内部已完成），剥壳才不丢方向
            positive_out = strip_all_weights(positive_out)
            negative_out = strip_all_weights(negative_out)

        if krea2_mode:
            # ③ 只取反负面串，正面保持原样；入参已是归一串，直接吃
            negative_out = to_negative_one_tags(negative_out)
            if negative_out:
                positive_out = _join_non_empty(positive_out, negative_out)

        return (positive_out, negative_out)


NODE_CLASS_MAPPINGS = {
    "NaiEmphasisConverter": NaiEmphasisConverter,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "NaiEmphasisConverter": "NAI 强调语法转换（NAI Emphasis Converter）",
}
