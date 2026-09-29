# ComfyUI NAI 强调语法转换

把 NovelAI V4 / V4.5 的提示词语法转成 ComfyUI 能认的 `(tag:N)` 写法，负权重自动分流到负面槽。
纯 Python 实现，零外部依赖，装上就能用。

## 支持的语法

| 输入 | 含义 | 输出 |
|---|---|---|
| `1.3::tag` | 段落权重 | `(tag:1.3)` |
| `{tag}` | 加强，每层 +0.05 | `(tag:1.05)` |
| `[tag]` | 减弱，每层 −0.05 | `(tag:0.95)` |
| `-1.4::tag` | 负权重（NAI 写法） | 移出正面，进负面槽为 `(tag:1.4)` |
| `(tag:-1)` | 负权重（A1111 写法） | 同样按方向分流 |
| 权重恰为 1 | 无强调 | 不加括号，原样输出 |

两种负权重写法走同一条分流规则（壳内有没有负号），方向不会丢。

## 安装

进 ComfyUI 的 `custom_nodes` 目录：

```bash
git clone https://github.com/sun19970908/nai-emphasis-converter.git
```

或者 Download ZIP 解压成 `custom_nodes/nai-emphasis-converter`。

没有需要 pip 安装的依赖，重启 ComfyUI 即生效。画布双击搜「NAI」或「强调」，
节点在 `prompt` 分类下，显示名「NAI 强调语法转换（NAI Emphasis Converter）」。

## 使用

节点有 `positive` / `negative` 两个多行文本框（可直接粘贴，也可从上游字符串节点接线）
和两个开关：

| 开关 | 默认 | 作用 |
|---|---|---|
| `flatten` | 关 | 权重全部归 1：剥掉所有 `(tag:N)` 外壳，只留裸 tag |
| `适配 Krea2 Prompt Weight` | 关 | 负面串权重 ×(-1)——`(tag:1.4)`→`(tag:-1.4)`，裸 tag→`(tag:-1)`——并把结果并进 positive 输出 |

**输出**：`positive` / `negative` 两条 STRING。

### 常规工作流（有正负两个 CLIPTextEncode）

开关全默认：`positive` 输出 → 正面编码器，`negative` 输出 → 负面编码器。

### Krea2 Prompt Weight 工作流（没有可用 negative 槽位）

勾「适配 Krea2 Prompt Weight」，只把 `positive` 输出接进文本编码器即可；
`negative` 输出仍照常给出取反后的串，想单独接也有。

### 提示词示例

输入（正面）：

```
masterpiece, 1girl, {detailed eyes}, 1.3::blonde hair, -1.4::watermark
```

输出：

```
positive: masterpiece, 1girl, (detailed eyes:1.05), (blonde hair:1.3)
negative: (watermark:1.4)
```

## 转换是两步

1. **语法转换**：`::` / `{}` / `[]` 全部展开成 `(tag:N)`，负权重就地写成 `(tag:-N)` 留在串里；
2. **分流**：顶层逗号逐段看，壳内带负号的进负面（摘掉负号、权重转正），其余留在正面。

`flatten` 与「适配 Krea2 Prompt Weight」都在这两步之后作用

## 测试

`tests/` 下两组工具，本仓库自包含，clone 下来即可跑：

```bash
# 对拍：16 组用例 × 6 项引擎输出 + 4 条开关管线组合，
# Python 版与 tests/reference-engine/ 里的 JS 参考引擎逐项比对
cd tests
node run_js_battery.mjs
python run_py_battery.py

# 工作流验证：离线跑任意工作流 JSON 里的本节点，打印实际喂给采样器的串
python verify_workflow.py <工作流.json>
```


## 文件

| 文件 | 用途 |
|---|---|
| `__init__.py` | 包入口，导出节点映射 |
| `nodes.py` | 节点定义（输入输出、开关、管线顺序） |
| `nai_emphasis.py` | 转换引擎（纯 Python，只用到标准库） |
| `tests/` | 对拍测试 + 工作流验证工具 |
| `tests/reference-engine/` | 对拍用的上游引擎同步副本 |
