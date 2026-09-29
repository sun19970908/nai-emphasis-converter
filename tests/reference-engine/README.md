# 对拍基准引擎

`prompt-emphasis.mjs` 是 [nai-emphasis-share](../../) 网页版/Node 版的**同步副本**，
只作为 `run_js_battery.mjs` 的对拍基准，保证 Python 移植版（`../../nai_emphasis.py`）与
JS 原版行为逐位一致。

**不要手改这个文件**。上游 JS 有改动时：用新版覆盖这里 → 同步改 `nai_emphasis.py`
→ 重跑对拍，全绿才算完成同步。
