// 对拍 · JS 侧：用 nai-emphasis-share 的原版引擎跑同一批用例，产出 js_results.json。
// 运行：node run_js_battery.mjs   （可用环境变量 NAI_ENGINE_PATH 指定引擎文件路径）
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
// 默认用仓库内 tests/reference-engine/ 的同步副本；也可用环境变量指向任意引擎文件
const enginePath = process.env.NAI_ENGINE_PATH
    || join(here, 'reference-engine', 'prompt-emphasis.mjs');

const {
    convertNovelEmphasisToComfy,
    splitNegativeWeights,
    convertPromptPair,
    stripAllWeights,
    toNegativeOneTags,
} = await import(pathToFileURL(enginePath).href);

// prompt-emphasis.mjs 的 joinNonEmpty 是模块私有函数，逐字拷贝一份用于对拍
function joinNonEmpty(...parts) {
    return parts
        .filter(Boolean)
        .map(part => String(part).trim().replace(/[，、]/g, ',').replace(/^,+|,+$/g, ''))
        .filter(part => part.length > 0)
        .join(', ');
}

const cases = JSON.parse(readFileSync(join(here, 'cases.json'), 'utf8'));

// 节点只有 flatten 与「适配 Krea2 Prompt Weight」两个开关；
// krea2 适配 = 负面 ×(-1) + 并进正面，一步完成
const combos = [];
for (const flatten of [false, true])
    for (const krea2 of [false, true])
        combos.push({ flatten, krea2 });

const results = cases.map((c) => {
    const positive = c.positive ?? '';
    const negative = c.negative ?? '';
    const norm = c.norm ?? '';
    const pair = convertPromptPair({ positive, negative });
    const pipelines = combos.map(({ flatten, krea2 }) => {
        let p = pair.positive;
        let n = pair.negative;
        if (flatten) { p = stripAllWeights(p); n = stripAllWeights(n); }
        if (krea2) {
            n = toNegativeOneTags(n);
            if (n) { p = joinNonEmpty(p, n); }
        }
        return [p, n];
    });
    const split = splitNegativeWeights(norm);
    return {
        conv_pos: convertNovelEmphasisToComfy(positive),
        conv_neg: convertNovelEmphasisToComfy(negative),
        pair: [pair.positive, pair.negative],
        split: [split.positive, split.negative],
        strip: stripAllWeights(norm),
        neg1: toNegativeOneTags(norm),
        pipelines,
    };
});

writeFileSync(join(here, 'js_results.json'), JSON.stringify(results, null, 1));
console.log('JS battery done:', cases.length, 'cases x', combos.length, 'pipelines');
