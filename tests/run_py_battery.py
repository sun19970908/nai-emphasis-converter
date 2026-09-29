# -*- coding: utf-8 -*-
"""对拍 · Python 侧：移植版引擎跑同一批用例，与 js_results.json 逐项比对。

先跑 node run_js_battery.mjs，再跑本脚本。全部一致退出码 0，否则打印差异退出码 1。
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))

from nai_emphasis import (
    convert_novel_emphasis_to_comfy,
    convert_prompt_pair,
    split_negative_weights,
    strip_all_weights,
    to_negative_one_tags,
    _join_non_empty,
)

COMBOS = [(f, k) for f in (False, True) for k in (False, True)]


def pipeline(pair_pos, pair_neg, flatten, krea2):
    p, n = pair_pos, pair_neg
    if flatten:
        p = strip_all_weights(p)
        n = strip_all_weights(n)
    if krea2:
        # 与节点一致：负面 ×(-1) 后并进正面，一步完成
        n = to_negative_one_tags(n)
        if n:
            p = _join_non_empty(p, n)
    return p, n


def main():
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    js_results = json.loads((HERE / "js_results.json").read_text(encoding="utf-8"))
    assert len(cases) == len(js_results), "cases 与 js_results 数量不一致"

    failures = 0
    for i, (case, jr) in enumerate(zip(cases, js_results)):
        name = case.get("name", str(i))
        positive = case.get("positive", "")
        negative = case.get("negative", "")
        norm = case.get("norm", "")

        pair = convert_prompt_pair(positive=positive, negative=negative)
        split = split_negative_weights(norm)
        py = {
            "conv_pos": convert_novel_emphasis_to_comfy(positive),
            "conv_neg": convert_novel_emphasis_to_comfy(negative),
            "pair": [pair[0], pair[1]],
            "split": [split[0], split[1]],
            "strip": strip_all_weights(norm),
            "neg1": to_negative_one_tags(norm),
            "pipelines": [list(pipeline(pair[0], pair[1], f, k)) for f, k in COMBOS],
        }

        for key in ("conv_pos", "conv_neg", "pair", "split", "strip", "neg1"):
            if py[key] != jr[key]:
                failures += 1
                print(f"[{name}] {key}\n  js: {jr[key]!r}\n  py: {py[key]!r}")
        for j, (py_pair, js_pair) in enumerate(zip(py["pipelines"], jr["pipelines"])):
            if py_pair != js_pair:
                failures += 1
                print(f"[{name}] pipeline#{j} flatten={COMBOS[j][0]} krea2={COMBOS[j][1]} merge={COMBOS[j][2]}\n  js: {js_pair!r}\n  py: {py_pair!r}")

    if failures:
        print(f"FAIL: {failures} 处不一致")
        sys.exit(1)
    print(f"PASS: {len(cases)} 用例 × (6 项引擎输出 + {len(COMBOS)} 条节点管线) 全部与 JS 原版一致")


if __name__ == "__main__":
    main()
