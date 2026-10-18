# -*- coding: utf-8 -*-
"""NovelAI V4 / V4.5 emphasis → ComfyUI A1111 (tag:weight) 转换器（Python 版）。

这是 nai-emphasis-share 项目 prompt-emphasis.mjs 的忠实移植：
源码 d:\\Users\\C\\Documents\\Coding\\nai-emphasis-share\\prompt-emphasis.mjs
移植基准：2026-09-14 版本。改动 JS 源码后必须同步这里，并跑 tests/ 对拍。

解析分两层（与 JS 同构）：
    第一层 parse_novel_sections —— 纯段落切分，只识别 `数字::` 与孤立 `::`
    第二层 extract_weighted_tokens —— 处理段落内 brace/bracket 位置权重
段落权重 × brace 因子 = 最终权重。weight===1 且非显式段落不加括号。

「转换」与「分流」是两件事：
    convert_novel_emphasis_to_comfy(text)          只改语法，不判归属
    split_negative_weights(normalized)             只判归属，不改语法
    convert_prompt_pair(positive, negative)        吃一对、吐一对
    strip_all_weights(normalized)                  权重全改 1（须在分流之后）
    to_negative_one_tags(normalized)               krea2 权重 ×(-1)（入参须已归一）

移植对齐要点（改这里时逐条自查）：
  * 数字只认 ASCII（JS 的 \\d / isAsciiDigit）→ 正则全部加 re.A
  * JS 的 `$` 只匹配串尾（无 /m），Python 的 `$` 会多吃一个行尾换行 → 全用 \\Z
  * 浮点运算顺序与 JS 完全一致（同 IEEE754 双精度，结果逐位相同）
  * format_weight 用 .4f 再剥零，等价 JS 的 Number(x.toFixed(4)).toString()，
    "-0" 归一成 "0"
"""

import math
import re

WEIGHT_STEP = 0.05
PAREN_WEIGHT_STEP = 0.10

_WEIGHT_RE = re.compile(r"\A-?\d+(?:\.\d+)?\Z", re.A)
_ASCII_DIGITS = frozenset("0123456789")

# 「自带方向的负权重壳」：`(tag:-N)`，N 为正数。组1 tag，组2 权重绝对值。
_NEGATIVE_SHELL = re.compile(r"\A\((.*):-(\d+(?:\.\d+)?)\)\Z", re.S | re.A)

# 「带符号权重的壳」：`(tag:N)` / `(tag:-N)`。组2 是带符号权重，取负即 ×(-1)。
_SIGNED_WEIGHT_SHELL = re.compile(r"\A\((.*):(-?\d+(?:\.\d+)?)\)\Z", re.S | re.A)

# 剥壳用：整体包裹的权重壳（正负都认）。tag 内部的转义括号不受影响。
_STRIP_WEIGHT_SHELL = re.compile(r"\A\((.*):-?\d+(?:\.\d+)?\)\Z", re.S | re.A)


def _match_number_at(text, start):
    """从 start 起匹配可选 `-` + 数字序列（至多一个小数点，点前须有数字）。

    返回 (value, end)；没有数字返回 None。等价 JS 的 matchNumberAt。
    """
    i = start
    n = len(text)
    has_digit = False
    has_dot = False
    if i < n and text[i] == "-":
        i += 1
    while i < n and (text[i] in _ASCII_DIGITS or text[i] == "."):
        if text[i] == ".":
            if has_dot or not has_digit:
                break
            has_dot = True
        else:
            has_digit = True
        i += 1
    if not has_digit:
        return None
    value = float(text[start:i])
    if not math.isfinite(value):
        return None
    return value, i


def _format_weight(weight):
    """等价 JS 的 Number(weight.toFixed(4)).toString()。"""
    if not math.isfinite(weight):
        return str(weight)
    s = f"{weight:.4f}"
    if "." in s:
        s = s.rstrip("0").rstrip(".")
    if s in ("-0", ""):
        s = "0"
    return s


def _clean_tag(s):
    """JS cleanTag：trim → 掐掉首尾 ASCII 逗号 → 再 trim。"""
    return str(s).strip().strip(",").strip()


def parse_novel_sections(text):
    """第一层：纯段落切分，不做警告判断。

    输出 [{weight, content, is_explicit}]：
      - `数字::` 开启新段落（可隐式接管前一段落）
      - 孤立 `::` 提前截断当前段落
      - 串尾自然结束当前段落；第一段前面允许没有 `::`
    """
    sections = []
    n = len(text)
    i = 0
    current_weight = 1.0
    section_start = 0
    is_explicit = False

    def push(end_index):
        content = text[section_start:end_index]
        if not _clean_tag(content):
            return
        sections.append({
            "weight": current_weight if is_explicit else 1.0,
            "content": content,
            "is_explicit": is_explicit,
        })

    while i < n:
        ch = text[i]
        ch2 = text[i + 1] if i + 1 < n else ""

        if ch in _ASCII_DIGITS or (ch == "-" and i + 1 < n and text[i + 1] in _ASCII_DIGITS):
            num = _match_number_at(text, i)
            if (
                num is not None
                and num[1] < n
                and text[num[1]] == ":"
                and num[1] + 1 < n
                and text[num[1] + 1] == ":"
            ):
                push(i)
                current_weight = num[0]
                section_start = num[1] + 2
                is_explicit = True
                i = num[1] + 2
                continue

        if ch == ":" and ch2 == ":":
            push(i)
            current_weight = 1.0
            section_start = i + 2
            is_explicit = False
            i += 2
            continue

        i += 1

    if section_start < n:
        push(n)

    return sections


def _find_matching_paren(text, start):
    """从 start（必须是 '('）开始，找到匹配的 ')' 索引。跳过转义字符。
    若未闭合返回 -1。
    """
    n = len(text)
    depth = 0
    i = start
    while i < n:
        ch = text[i]
        if ch == "\\":
            i += 2
            continue
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return -1


def _check_explicit_weight_paren(text, start):
    """检查以 start 处的 '(' 开头的括号块是否为显式权重 (tag:weight)。

    若是，返回 (tag_part, float(weight_part), end_index)；
    若不是（如普通强调括号 (tag) 或带有非数字冒号），返回 None。
    """
    end = _find_matching_paren(text, start)
    if end == -1:
        return None
    inner = text[start + 1:end]
    n = len(inner)
    depth = 0
    colon_idx = -1
    i = 0
    while i < n:
        ch = inner[i]
        if ch == "\\":
            i += 2
            continue
        if ch in "({[":
            depth += 1
        elif ch in ")}]":
            if depth > 0:
                depth -= 1
        elif ch == ":" and depth == 0:
            colon_idx = i
        i += 1
    if colon_idx == -1:
        return None
    tag_part = _clean_tag(inner[:colon_idx])
    weight_part = inner[colon_idx + 1:].strip()
    if not tag_part or not _WEIGHT_RE.match(weight_part):
        return None
    return tag_part, float(weight_part), end


def extract_weighted_tokens(content):
    r"""第二层：处理段落内 brace/bracket/paren 位置权重。

    输出 [(tag, brace_factor, is_explicit)]：
      - 花括号 `{}`：每层 +0.05
      - 方括号 `[]`：每层 -0.05
      - 圆括号 `()`：
          - 显式权重 `(tag:N)`：继承自身显式权重 N 及外层修饰
          - 普通强调 `(tag)`：每层 +0.10，嵌套再 +0.10
      - 转义括号 `\(` `\)`：保持字面值，不作为语法括号解析
    """
    tokens = []
    buffer = []
    multiply_count = 0
    divide_count = 0
    paren_count = 0
    depth = 0

    def flush_buffer():
        tag = _clean_tag("".join(buffer))
        del buffer[:]
        if not tag:
            return
        brace_factor = 1 + WEIGHT_STEP * multiply_count - WEIGHT_STEP * divide_count + PAREN_WEIGHT_STEP * paren_count
        tokens.append((tag, brace_factor, False))

    n = len(content)
    i = 0
    while i < n:
        ch = content[i]

        if ch == "\\":
            buffer.append(ch)
            if i + 1 < n:
                buffer.append(content[i + 1])
                i += 2
            else:
                i += 1
            continue

        if ch == "{":
            multiply_count += 1
            depth += 1
            flush_buffer()
            i += 1
            continue
        if ch == "}":
            flush_buffer()
            if depth > 0:
                depth -= 1
            multiply_count = max(0, multiply_count - 1)
            i += 1
            continue

        if ch == "[":
            divide_count += 1
            depth += 1
            flush_buffer()
            i += 1
            continue
        if ch == "]":
            flush_buffer()
            if depth > 0:
                depth -= 1
            divide_count = max(0, divide_count - 1)
            i += 1
            continue

        if ch == "(":
            explicit = _check_explicit_weight_paren(content, i)
            if explicit is not None:
                flush_buffer()
                exp_tag, exp_weight, end_idx = explicit
                delta = WEIGHT_STEP * multiply_count - WEIGHT_STEP * divide_count + PAREN_WEIGHT_STEP * paren_count
                if exp_weight >= 0:
                    final_factor = exp_weight + delta
                else:
                    final_factor = exp_weight
                if "," in exp_tag:
                    for sub in exp_tag.split(","):
                        sub_tag = _clean_tag(sub)
                        if sub_tag:
                            tokens.append((sub_tag, final_factor, True))
                else:
                    tokens.append((exp_tag, final_factor, True))
                i = end_idx + 1
                continue
            else:
                flush_buffer()
                paren_count += 1
                depth += 1
                i += 1
                continue

        if ch == ")":
            flush_buffer()
            if depth > 0:
                depth -= 1
            paren_count = max(0, paren_count - 1)
            i += 1
            continue

        if ch == ",":
            flush_buffer()
            i += 1
            continue

        buffer.append(ch)
        i += 1

    flush_buffer()
    return tokens


def convert_novel_emphasis_to_comfy(text):
    """第一步 · 转换：NAI emphasis 改写成 ComfyUI 兼容语法，只改语法不判归属。

    负权重就地写成 `(tag:-N)` 留在串里，归属由 split_negative_weights 决定。
    """
    if not isinstance(text, str) or len(text) == 0:
        return ""

    parts = []
    for section in parse_novel_sections(text):
        for tag, brace_factor, is_explicit in extract_weighted_tokens(section["content"]):
            weight = section["weight"] * brace_factor
            if weight < 0:
                parts.append(f"({tag}:-{_format_weight(abs(weight))})")
                continue
            if weight == 1 and not (section["is_explicit"] or is_explicit):
                parts.append(tag)
            else:
                parts.append(f"({tag}:{_format_weight(weight)})")

    return ", ".join(parts)


def split_negative_weights(normalized):
    """第二步 · 分流：按「壳内有没有负号」把已转换的串切成正面与负面两条。

    `(tag:-N)` → negative（摘负号、权重转正，绝对值 1 落成裸 tag）；
    其余原样进 positive。也顺带完成剥壳。
    """
    text = str(normalized or "").strip()
    if not text:
        return "", ""

    positive = []
    negative = []
    for raw in _split_top_level_tags(text):
        segment = _clean_tag(raw)
        if not segment:
            continue
        m = _NEGATIVE_SHELL.match(segment)
        if not m:
            positive.append(segment)
            continue
        tag = _clean_tag(m.group(1))
        strength = float(m.group(2))
        if not tag or not math.isfinite(strength) or strength <= 0:
            positive.append(segment)
            continue
        negative.append(tag if strength == 1 else f"({tag}:{_format_weight(strength)})")

    return ", ".join(positive), ", ".join(negative)


def _join_non_empty(*parts):
    """拼接非空串：全角逗号/顿号归一成半角，再掐首尾逗号（对齐 JS joinNonEmpty）。"""
    cleaned = []
    for part in parts:
        if not part:
            continue
        s = str(part).strip()
        s = re.sub(r"[，、]", ",", s)
        s = re.sub(r"\A,+|,+\Z", "", s)
        if s:
            cleaned.append(s)
    return ", ".join(cleaned)


def convert_prompt_pair(positive="", negative=""):
    """第三步 · 包装：吃一对、吐一对。

    正面 → 转换 → 分流；负面 → 只转换（负面不做分流，判据会把它当正面搬走）；
    最终 negative = 转换后的负面 + 分流出的负权重。
    """
    positive_converted = convert_novel_emphasis_to_comfy(str(positive or "").strip())
    negative_converted = convert_novel_emphasis_to_comfy(str(negative or "").strip())
    split_positive, split_negative = split_negative_weights(positive_converted)
    return split_positive, _join_non_empty(negative_converted, split_negative)


def _split_top_level_tags(text):
    """按顶层逗号切分（括号计数，避免切坏 `(a, b:1.2)`）。

    反斜杠转义的字符（A1111 的 `\\(` `\\)`）连同下一个字符原样带过，不参与计数。
    """
    out = []
    buffer = []
    depth = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\\":
            buffer.append(ch)
            i += 1
            if i < n:
                buffer.append(text[i])
                i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == "," and depth == 0:
            out.append("".join(buffer))
            buffer = []
            i += 1
            continue
        buffer.append(ch)
        i += 1
    out.append("".join(buffer))
    return out


def _strip_weight_shell(entry):
    """剥掉「整体包裹」的权重壳：`(tag:1.4)` → `tag`；不是权重壳则原样返回。"""
    s = str(entry).strip()
    m = _STRIP_WEIGHT_SHELL.match(s)
    return _clean_tag(m.group(1)) if m else s


def _collect_bare_tags(normalized):
    """把已归一提示词切成裸 tag 列表：顶层逗号切分 → 剥整体权重壳。

    保持原顺序、原样保留重复，不做任何去重。
    """
    tags = []
    for raw in _split_top_level_tags(normalized):
        t = _strip_weight_shell(_clean_tag(raw))
        if t:
            tags.append(t)
    return tags


def strip_all_weights(normalized_text):
    """后置工具 · 权重全改 1：剥掉所有 `(tag:N)` / `(tag:-N)` 外壳，只留裸 tag。

    入参须是 convert_novel_emphasis_to_comfy 的输出（必须在分流之后调用，
    提前剥壳会连负号一起摘掉，tag 就分不出方向了）。幂等、不去重。
    """
    normalized = str(normalized_text or "").strip()
    if not normalized:
        return ""
    return ", ".join(_collect_bare_tags(normalized))


def to_negative_one_tags(normalized):
    """krea2 适配：整条提示词权重 ×(-1)：`(tag:1.4)` → `(tag:-1.4)`，裸 tag 补 -1。

    入参必须已归一（convert_novel_emphasis_to_comfy 的产物），不要在这里再转一次。
    不去重。
    """
    text = str(normalized or "").strip()
    if not text:
        return ""
    parts = []
    for raw in _split_top_level_tags(text):
        segment = _clean_tag(raw)
        if not segment:
            continue
        m = _SIGNED_WEIGHT_SHELL.match(segment)
        if m:
            parts.append(f"({_clean_tag(m.group(1))}:{_format_weight(-float(m.group(2)))})")
        else:
            parts.append(f"({segment}:-1)")
    return ", ".join(parts)
