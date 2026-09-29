# NovelAI 强调语法转换器

把 NovelAI V4 / V4.5 的提示词语法转成 ComfyUI / krea2 能认的写法。**零依赖**，不需要联网、不需要安装任何东西。

## 支持转换的语法

| 输入 | 含义 | 输出 |
|---|---|---|
| `1.3::tag` | 段落权重 | `(tag:1.3)` |
| `{tag}` | 加强，每层 +0.05 | `(tag:1.05)` |
| `[tag]` | 减弱，每层 −0.05 | `(tag:0.95)` |
| `-1.4::tag` | 负权重（NAI 写法） | 移出正面，进负面槽位为 `(tag:1.4)` |
| `(tag:-1)` | 负权重（A1111 写法） | 同样按方向分流，负面槽位得 `tag` |
| 权重恰为 1 | 无强调 | 不加括号，原样输出 |

转换与分流是两步：先只改语法（负权重就地写成 `(tag:-N)` 留在串里），再按「壳内有没有负号」判归属。
所以两种负权重写法最终都走同一条路，方向不会丢。

## 用法一：网页版（推荐给不装 Node 的人）

**双击 `index.html`**，浏览器打开即可用。输入提示词会自动实时转换，有「复制」按钮。

界面上是三个复选框，各自对应一条转换逻辑，**按编号顺序依次作用**，可以任意搭配：

| 勾选 | 逻辑 | 对应函数 |
|---|---|---|
| ① 转换 NAI 语法 | `::` `{}` `[]` → `(tag:N)`，负权重分流到负面 | `convertPromptPair` |
| ② 权重全部归 1 | 剥掉所有权重壳，只留裸 tag | `stripAllWeights` |
| ③ krea2 / flux | 负面串**权重 ×(-1)**：`(tag:1.4)` → `(tag:-1.4)`，裸 tag → `(tag:-1)` | `toNegativeOneTags` |

页面上下都是「正面 / 负面」两个框：上面填输入，下面实时出结果，各带一个复制按钮。
三个都不勾则原样透传。

③ 是给没有 negative 槽位的工作流用的 —— 勾上后只有负面串按原强度取反，正面保持原样；
把负面框内容拼到正面提示词后面即可。
注意 ③ 吃的是**已经 ① 转换过**的串：网页/CLI 都已在上游转换好，直接把原始提示词丢给它是没
展开 `::` / `{}` / `[]` 的，结果会不对。

> 两个文件必须在同一目录：`index.html` 依赖 `nai-emphasis.flat.js`。

### 手机上用：单文件版

`nai-emphasis.single.html` 是自包含版本 —— 引擎已经内联进页面，**一个文件就能跑**。
把它发到手机（微信/QQ 都行）、用手机浏览器打开即可，不用再凑齐两个文件。

它由 `node build-flat.mjs` 生成，**不要手改**：改了 `index.html` 或 `prompt-emphasis.mjs`
都要重跑一次，否则单文件版会停留在旧版本。

## 用法二：命令行（装了 Node 的人）

需要一个 Node 环境（建议 ≥ 18，`.mjs` 后缀保证了没有配置也能跑）：

```bash
node prompt-emphasis.mjs "masterpiece, 1girl, {detailed eyes}, 1.3::blonde hair, -1.4::watermark"
```

输出永远是 `{ positive, negative }` 两条串，负权重已经分好：

```json
{
  "positive": "masterpiece, 1girl, (detailed eyes:1.05), (blonde hair:1.3)",
  "negative": "(watermark:1.4)"
}
```

加 `--flatten`（或 `-f`）把所有权重改成 1，两条串各剥一次壳：

```bash
node prompt-emphasis.mjs --flatten "1.2::masterpiece::, (qipao:-1), -1.4::watermark"
# → { "positive": "masterpiece", "negative": "qipao, watermark" }
```

krea2 / flux 模式（`-n` 或 `--negative-one`）：

```bash
node prompt-emphasis.mjs -n "bad hands, lowres, (worst quality:1.2)"
# → (bad hands:-1), (lowres:-1), (worst quality:-1.2)   ← 原强度保留、符号取反
```

其他：`--help` 看帮助，也支持管道 `echo "1.2::1girl" | node prompt-emphasis.mjs`。

## 用法三：当模块引用

```js
// Node / 打包器：吃一对、吐一对
import { convertPromptPair } from './prompt-emphasis.mjs';
const { positive, negative } = convertPromptPair({
  positive: '1.2::masterpiece::, (forehead mark:-1)',
  negative: '1.3::bad hands',
});
// positive → '(masterpiece:1.2)'
// negative → '(bad hands:1.3), forehead mark'
```

只想单独用其中一步也可以：`convertNovelEmphasisToComfy(text)` 只改语法，
`splitNegativeWeights(normalized)` 只判归属，`stripAllWeights(text)` 权重全改 1，
`toNegativeOneTags(normalized)` 权重 ×(-1)（**入参须已归一**）：`(blurry:1.4)` → `(blurry:-1.4)`，
裸 tag → `(tag:-1)`。

```html
<!-- 浏览器：经典 script，挂到 window.NAIEmphasis -->
<script src="nai-emphasis.flat.js"></script>
<script>
  const { positive, negative } = NAIEmphasis.convertPromptPair({ positive: '1.2::masterpiece' });
  console.log(positive, negative);
</script>
```

## 修改源码后：重新生成 flat 版

`nai-emphasis.flat.js` 不是手写的，是从 `prompt-emphasis.mjs` 机械变换出来的产物
（截掉 Node 互操作层那一段 → 去掉行首的 `export ` → 追加浏览器全局挂载块）。
所以**改了 `.mjs` 就要重新跑一次**，否则两份会各自演化。

```bash
node build-flat.mjs
```

从别处的源文件同步过来再生成（例如上游仓库里那份）：

```bash
node build-flat.mjs --from /path/to/prompt-emphasis.mjs
```

只想确认产物没落后（不写任何文件，过期时退出码为 1）：

```bash
node build-flat.mjs --check
```

生成后脚本会自己在沙箱里跑一遍产物，确认 8 个成员都挂上了，并拿 6 组典型输入和源文件逐项比对结果。

## 文件说明

| 文件 | 用途 |
|---|---|
| `index.html` | 网页版界面，双击即用 |
| `nai-emphasis.single.html` | 手机用的自包含单文件版（引擎已内联），**由脚本生成，不要手改** |
| `nai-emphasis.flat.js` | 浏览器版（经典 script，挂 `window.NAIEmphasis`），**由脚本生成，不要手改** |
| `prompt-emphasis.mjs` | Node 模块 / 命令行版，源码在那里面 |
| `build-flat.mjs` | 维护用：从 `.mjs` 重新生成 flat 版并自检，顺带产出单文件版 |

`nai-emphasis.flat.js` 与 `prompt-emphasis.mjs` 是同一份源码的两种打包形式，
差别只有三处：结尾那段（浏览器全局挂载 vs Node 命令行入口）、`export` 前缀、以及被截掉的 Node 互操作层。
