# -*- coding: utf-8 -*-
"""新增圆括号权重强调 (tag) -> (tag:1.1) 及嵌套加权规则的专用单测。"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from nai_emphasis import (
    convert_novel_emphasis_to_comfy,
    convert_prompt_pair,
    strip_all_weights,
    to_negative_one_tags,
)


def run_tests():
    cases = [
        # 1. 基础单层与多层嵌套
        ("(tag)", "(tag:1.1)"),
        ("((tag))", "(tag:1.2)"),
        ("(((tag)))", "(tag:1.3)"),
        ("((((tag))))", "(tag:1.4)"),

        # 2. 与普通裸 tag 混排
        ("masterpiece, (1girl), ((blonde hair))", "masterpiece, (1girl:1.1), (blonde hair:1.2)"),

        # 3. 括号内多个 tag（按逗号拆分）
        ("(a, b)", "(a:1.1), (b:1.1)"),
        ("((a, b))", "(a:1.2), (b:1.2)"),
        ("(a, (b))", "(a:1.1), (b:1.2)"),
        ("{{{{{tribal tattoo,white bodypainting}}}}}", "(tribal tattoo:1.25), (white bodypainting:1.25)"),

        # 4. 与花括号 {}、方括号 [] 混合
        ("{tag}", "(tag:1.05)"),
        ("[tag]", "(tag:0.95)"),
        ("{(tag)}", "(tag:1.15)"),
        ("({tag})", "(tag:1.15)"),
        ("[(tag)]", "(tag:1.05)"),
        ("[[(tag)]]", "tag"),  # 1.0 - 0.10 + 0.10 = 1.0 -> 恰好为 1 输出裸 tag

        # 5. 与段落权重 1.3:: 结合
        ("1.3::(tag)", "(tag:1.43)"),
        ("-1.4::(tag)", "(tag:-1.54)"),

        # 6. 显式指定权重的保护 (tag:weight)
        ("(tag:1.2)", "(tag:1.2)"),
        ("(tag:0.8)", "(tag:0.8)"),
        ("(forehead mark:-1)", "(forehead mark:-1)"),
        ("((tag:1.2))", "(tag:1.3)"),  # 外层套普通括号 -> 1.2 + 0.1 = 1.3
        ("{(tag:1.2)}", "(tag:1.25)"), # 外层套花括号 -> 1.2 + 0.05 = 1.25

        # 7. 冒号非数字不误判为显式权重
        ("(tag with: single colon)", "(tag with: single colon:1.1)"),

        # 8. 转义括号 \( 和 \) 保留
        ("\\(literal parens\\)", "\\(literal parens\\)"),
    ]

    print("=== 开始运行圆括号规则单元测试 ===")
    failed = 0
    for inp, expected in cases:
        out = convert_novel_emphasis_to_comfy(inp)
        if out != expected:
            print(f"[FAIL] 输入: {inp!r}\n  期望: {expected!r}\n  得到: {out!r}")
            failed += 1
        else:
            print(f"[PASS] {inp} -> {out}")

    # 测试完整 pair 转换与负权重分流
    pos, neg = convert_prompt_pair(
        positive="masterpiece, 1girl, (beautiful eyes), ((smile)), (bad quality:-1), -1.4::worst quality",
        negative="lowres, {blurry}"
    )
    assert pos == "masterpiece, 1girl, (beautiful eyes:1.1), (smile:1.2)", f"pos mismatch: {pos}"
    assert neg == "lowres, (blurry:1.05), bad quality, (worst quality:1.4)", f"neg mismatch: {neg}"
    print("[PASS] 正负分流测试通过！")

    # 测试 flatten（权重归 1）
    flat_pos = strip_all_weights(pos)
    assert flat_pos == "masterpiece, 1girl, beautiful eyes, smile", f"flat_pos mismatch: {flat_pos}"
    print("[PASS] flatten 测试通过！")

    if failed:
        print(f"\n测试未完全通过，失败数: {failed}")
        sys.exit(1)
    print(f"\n全部 {len(cases)} 组测试 + 分流/flatten 测试均 100% 通过！")


if __name__ == "__main__":
    run_tests()
