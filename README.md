# ComfyUI NAI 强调语法转换

把 NovelAI V4 / V4.5 的提示词语法转成 ComfyUI 能认的 `(tag:N)` 写法，负权重自动分流到负面槽。
纯 Python 实现，零外部依赖，装上就能用。内含 WeiLin 提示词锚点兼容节点。

## 支持的语法

| 输入 | 含义 | 输出 |
|---|---|---|
| `1.3::tag` | 段落权重 | `(tag:1.3)` |
| `{tag}` | 加强，每层 +0.05 | `(tag:1.05)` |
| `[tag]` | 减弱，每层 −0.05 | `(tag:0.95)` |
| `(tag)` | WebUI 强调，每层 +0.1 | `(tag:1.1)` |
| `((tag))` | 嵌套再加 0.1 | `(tag:1.2)` |
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

没有需要 pip 安装的依赖，重启 ComfyUI 即生效。

## 节点说明

本扩展提供两类节点（均在 `prompt` 分类下）：

### 1. NAI 强调语法转换（NAI Emphasis Converter）

节点有 `positive` / `negative` 两个多行文本框（可直接粘贴，也可从上游字符串节点接线）和三个开关：

| 开关 | 默认 | 作用 |
|---|---|---|
| `回车补逗号` | 开 | ⓪ 所有转换之前：行尾没有英文逗号的行，在换行前自动补一个英文逗号（兜编辑器回车吞逗号造成的 tag 粘连；空行不补，已有英文逗号不补） |
| `flatten` | 关 | ② 权重全部归 1：剥掉所有 `(tag:N)` 外壳，只留裸 tag |
| `适配 Krea2 Prompt Weight` | 关 | ③ 负面串权重 ×(-1)——`(tag:1.4)`→`(tag:-1.4)`，裸 tag→`(tag:-1)`——并把结果并进 positive 输出 |

**输出**：`positive` / `negative` 两条 STRING。

- **常规工作流（有正负两个 CLIPTextEncode）**：
  开关全默认：`positive` 输出 → 正面编码器，`negative` 输出 → 负面编码器。

- **Krea2 Prompt Weight 工作流（没有可用 negative 槽位）**：
  勾「适配 Krea2 Prompt Weight」，只把 `positive` 输出接进文本编码器即可；
  `negative` 输出仍照常给出取反后的串，想单独接也有。

**提示词示例**：
- 输入（正面）：`masterpiece, 1girl, {detailed eyes}, 1.3::blonde hair, -1.4::watermark`
- 输出：
  - `positive`: `masterpiece, 1girl, (detailed eyes:1.05), (blonde hair:1.3)`
  - `negative`: `(watermark:1.4)`

### 2. 提示词锚点（WeiLin 兼容）

- **正面提示词锚点（WeiLin 兼容）** (`WeiLinComfyUIPromptAllInOneGreat`)
- **负面提示词锚点（WeiLin 兼容）** (`WeiLinComfyUIPromptAllInOneNeg`)

**用途**：
1. **旧工作流兼容**：兼容使用了原 `weilin-comfyui-prompt-all-in-one` 的工作流，加载时不再报「缺失节点」。
2. **元数据解析（spell 等咒语工具）**：spell 类解析工具扫描图片元数据中的 prompt 块时，会优先识别这两个类名并直接读取 `inputs.text`。将提示词填在锚点节点的 `text` 框里，输出接进 `NaiEmphasisConverter` 或下游编码器，生成图片即可被正确读取。

## 转换是两步

1. **语法转换**：`::` / `{}` / `[]` 全部展开成 `(tag:N)`，负权重就地写成 `(tag:-N)` 留在串里；
2. **分流**：顶层逗号逐段看，壳内带负号的进负面（摘掉负号、权重转正），其余留在正面。

`flatten` 与「适配 Krea2 Prompt Weight」都在这两步之后作用。

## 测试

`tests/` 下包含单元测试与对拍工具：

```bash
# 锚点与基础测试
python tests/test_anchor.py
python tests/test_paren_emphasis.py

# 对拍：16 组用例 × 6 项引擎输出 + 4 条开关管线组合，
# Python 版与 tests/reference-engine/ 里的 JS 参考引擎逐项比对
cd tests
node run_js_battery.mjs
python run_py_battery.py

# 工作流验证：离线跑任意工作流 JSON 里的本节点，打印实际喂给采样器的串
python verify_workflow.py <工作流.json>
```

## 文件结构

| 文件 | 用途 |
|---|---|
| `__init__.py` | 包入口，导出全部节点映射 |
| `nodes.py` | 节点定义（注册 NAI 转换节点与 WeiLin 锚点节点） |
| `prompt_anchor.py` | WeiLin 兼容提示词锚点节点实现 |
| `nai_emphasis.py` | 转换引擎（纯 Python，只用到标准库） |
| `tests/` | 单元测试、对拍测试 + 工作流验证工具 |
| `tests/reference-engine/` | 对拍用的上游引擎同步副本 |
