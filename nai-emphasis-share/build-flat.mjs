/**
 * 重新生成 nai-emphasis.flat.js（浏览器平铺版）与 nai-emphasis.single.html（手机单文件版）。
 *
 * 用法：
 *   node build-flat.mjs                       用同目录的 prompt-emphasis.mjs 重新生成 flat 版
 *   node build-flat.mjs --from <源.mjs>        先从外部源（如 LWB 里的那份）同步 prompt-emphasis.mjs，再生成
 *   node build-flat.mjs --check                只比对，不写文件：flat 版是否与源文件一致
 *
 * 变换规则（三步纯文本操作，无依赖、无打包器）：
 *   ① 截到 "Node 互操作层" 分隔线之前 —— 丢掉 CLI 与 Node 互操作层
 *   ② 去掉行首的 `export ` 前缀 —— 经典 <script> 不认 ESM 语法
 *   ③ 追加浏览器全局挂载块 —— 挂到 globalThis.NAIEmphasis
 *
 * 生成后自检：在 vm 沙箱里真跑一遍产物，确认 8 个成员都挂上了，
 * 并与 ESM 源逐项比对 6 组典型输入的结果。
 *
 * 顺带产出手机用的单文件版：把 flat 全文内联进 index.html 的 <script src> 处，
 * 得到一个自包含的 html —— 手机浏览器直接打开即可，不要求两个文件同目录。
 * 该产物同样是生成物，改了 index.html 或 .mjs 都要重跑本脚本。
 */

import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath, pathToFileURL } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(HERE, 'prompt-emphasis.mjs');
const OUT = path.join(HERE, 'nai-emphasis.flat.js');
const HTML_SRC = path.join(HERE, 'index.html');
const SINGLE_OUT = path.join(HERE, 'nai-emphasis.single.html');

/** index.html 里引用 flat 版的那一行，单文件化时就替换它。 */
const SCRIPT_TAG = '<script src="nai-emphasis.flat.js"></script>';
const SINGLE_BANNER = '<!-- 生成物，请勿手改：由 node build-flat.mjs 从 index.html 内联 nai-emphasis.flat.js 得到 -->';

const BANNER_TITLE = 'Node 互操作层';

const MOUNT = '\n\n' + `/* ---------------------------------------------------------------------------
 * 浏览器全局挂载（平铺版专用）
 * 经典 <script> 加载后即可直接用 NAIEmphasis.convertNovelEmphasisToComfy(...)
 * ------------------------------------------------------------------------- */
(function (root) {
    root.NAIEmphasis = {
        WEIGHT_STEP,
        parseNovelSections,
        extractWeightedTokens,
        convertNovelEmphasisToComfy,
        splitNegativeWeights,
        convertPromptPair,
        stripAllWeights,
        toNegativeOneTags,
    };
})(typeof globalThis !== 'undefined' ? globalThis : this);
`;

const EXPECTED_MEMBERS = [
    'WEIGHT_STEP',
    'parseNovelSections',
    'extractWeightedTokens',
    'convertNovelEmphasisToComfy',
    'splitNegativeWeights',
    'convertPromptPair',
    'stripAllWeights',
    'toNegativeOneTags',
];

const SAMPLES = [
    ['convertNovelEmphasisToComfy', ['1.2::masterpiece, {blurry}, [simple background], -1.4::watermark']],
    ['convertNovelEmphasisToComfy', ['1.6::gray eyes, white pupils::, (forehead mark:-1)']],
    ['splitNegativeWeights', ['girl, (forehead mark:-1), (qipao:-1.4), (gray eyes:1.6)']],
    ['convertPromptPair', [{ positive: '1.2::masterpiece::, (forehead mark:-1)', negative: '1.3::bad hands' }]],
    ['stripAllWeights', ['(masterpiece:1.2), 1girl, (a:-1)']],
    // 入参须是**已归一**的串（toNegativeOneTags 不再内部转换）: (tag:N) → (tag:-N)，裸 tag 补 -1
    ['toNegativeOneTags', ['(bad hands:1.3), lowres']],
];

function cutAtInteropLayer(text) {
    const lines = text.split('\n');
    let cut = lines.findIndex((line, i) =>
        line.startsWith('/* ===') && String(lines[i + 1] || '').includes(BANNER_TITLE));
    if (cut < 0) {
        const near = lines.findIndex(line => line.includes(BANNER_TITLE));
        cut = near > 0 ? near - 1 : -1;
    }
    if (cut < 0) {
        throw new Error(
            `找不到「${BANNER_TITLE}」分隔线。源文件头部的注释横幅被改动过？` +
            '请在 prompt-emphasis.mjs 里保留 `/* ==== ...` + ` * Node 互操作层` 这两行。',
        );
    }
    const head = lines.slice(0, cut).join('\n');
    if (head.includes('function runCli')) {
        throw new Error('截断位置落在了 Node 互操作层之后，产物会带上 CLI 代码，已中止。');
    }
    return head;
}

function buildFlat(mjsText) {
    const head = cutAtInteropLayer(mjsText).replace(/^export /gm, '');
    return head + MOUNT;
}

/**
 * 单文件化：把 flat 全文内联进 index.html，得到自包含的 html。
 *
 * 两处必须小心：
 *   - 锚点（那行 <script src>）找不到就抛错 —— 静默跳过会产出一个没有转换逻辑的页面
 *   - flat 内容里的 `</script` 必须转义 —— 否则 HTML 解析到这儿就提前闭合脚本块
 */
function buildStandalone(htmlText, flatCode) {
    if (!String(htmlText).includes(SCRIPT_TAG)) {
        throw new Error(
            `index.html 里找不到锚点：${SCRIPT_TAG}\n` +
            '单文件化已中止（静默跳过会产出一个没有转换逻辑的页面）。');
    }
    const inline = String(flatCode).replace(/<\/script/gi, '<\\/script');
    const merged = htmlText.replace(SCRIPT_TAG, '<script>\n' + inline + '\n</script>');
    const doctype = '<!DOCTYPE html>';
    return merged.startsWith(doctype)
        ? doctype + '\n' + SINGLE_BANNER + merged.slice(doctype.length)
        : SINGLE_BANNER + '\n' + merged;
}

/** 渲染单文件内容；没有 index.html 时返回 null（单文件是可选产物，不该因此中断主流程）。 */
function renderStandalone(flatCode) {
    if (!fs.existsSync(HTML_SRC)) return null;
    return buildStandalone(fs.readFileSync(HTML_SRC, 'utf8'), flatCode);
}

/** --check 用：单文件产物是否缺失或过期。没问题返回 null。 */
function verifyStandalone(flatCode) {
    const expected = renderStandalone(flatCode);
    if (expected === null) return null;
    if (!fs.existsSync(SINGLE_OUT)) {
        return `${path.basename(SINGLE_OUT)} 不存在，需要生成（跑一次 node build-flat.mjs）`;
    }
    const onDisk = fs.readFileSync(SINGLE_OUT, 'utf8');
    if (onDisk !== expected) return `${path.basename(SINGLE_OUT)} 已过期，需要重新生成`;
    return null;
}

function loadFlat(code) {
    const sandbox = {};
    vm.createContext(sandbox);
    vm.runInContext(code, sandbox);
    if (!sandbox.NAIEmphasis) throw new Error('产物执行后没有挂上 globalThis.NAIEmphasis');
    return sandbox.NAIEmphasis;
}

function firstDiffLine(a, b) {
    const la = a.split('\n');
    const lb = b.split('\n');
    const n = Math.max(la.length, lb.length);
    for (let i = 0; i < n; i++) {
        if (la[i] !== lb[i]) return { line: i + 1, expected: la[i], actual: lb[i] };
    }
    return null;
}

async function selfCheck(flatCode, mjsPath) {
    const problems = [];
    const flat = loadFlat(flatCode);

    const missing = EXPECTED_MEMBERS.filter(name => !(name in flat));
    if (missing.length > 0) problems.push(`产物缺少成员: ${missing.join(', ')}`);
    if (/^export /m.test(flatCode)) problems.push('产物里还有 export 残留');
    if (/^\s*import\s/m.test(flatCode)) problems.push('产物里还有 import 残留');

    const url = pathToFileURL(mjsPath).href + '?t=' + Date.now();
    const esm = await import(url);

    for (const [fn, args] of SAMPLES) {
        if (typeof esm[fn] !== 'function') {
            problems.push(`源文件没有导出 ${fn}()`);
            continue;
        }
        const want = JSON.stringify(esm[fn](...args));
        const got = JSON.stringify(flat[fn](...args));
        if (want !== got) problems.push(`${fn}() 结果不一致\n    ESM: ${want}\n    flat: ${got}`);
    }

    return problems;
}

function parseArgv(argv) {
    let from = null;
    let check = false;
    for (let i = 0; i < argv.length; i++) {
        const a = argv[i];
        if (a === '--from') {
            from = argv[++i];
            if (!from) throw new Error('--from 后面要跟源文件路径');
        } else if (a === '--check') {
            check = true;
        } else if (a === '-h' || a === '--help') {
            console.log(fs.readFileSync(fileURLToPath(import.meta.url), 'utf8')
                .split('\n').slice(1, 8).map(l => l.replace(/^ \* ?/, '')).join('\n'));
            process.exit(0);
        } else {
            throw new Error(`不认识的参数: ${a}`);
        }
    }
    return { from, check };
}

async function main() {
    const { from, check } = parseArgv(process.argv.slice(2));

    let mjsText;
    if (from) {
        const fromPath = path.resolve(from);
        if (!fs.existsSync(fromPath)) throw new Error(`源文件不存在: ${fromPath}`);
        mjsText = fs.readFileSync(fromPath, 'utf8');
        if (!check) {
            const before = fs.existsSync(SRC) ? fs.readFileSync(SRC, 'utf8') : null;
            fs.writeFileSync(SRC, mjsText, 'utf8');
            console.log(`同步源文件: ${before === mjsText ? '已是最新' : '已更新'}  ${path.basename(SRC)}`);
        }
    } else {
        mjsText = fs.readFileSync(SRC, 'utf8');
    }

    const generated = buildFlat(mjsText);
    const onDisk = fs.existsSync(OUT) ? fs.readFileSync(OUT, 'utf8') : null;
    const stale = onDisk !== generated;

    if (check) {
        if (onDisk === null) {
            console.error(`✗ 产物不存在: ${path.basename(OUT)}`);
            process.exitCode = 1;
            return;
        }
        if (stale) {
            const d = firstDiffLine(onDisk, generated);
            console.error(`✗ ${path.basename(OUT)} 已过期，需要重新生成（首个差异在第 ${d.line} 行）`);
            console.error(`    磁盘: ${JSON.stringify(d.actual)}`);
            console.error(`    应为: ${JSON.stringify(d.expected)}`);
            process.exitCode = 1;
            return;
        }
        const problems = await selfCheck(onDisk, SRC);
        if (problems.length > 0) {
            console.error('✗ 产物自检未通过:');
            for (const p of problems) console.error('  - ' + p);
            process.exitCode = 1;
            return;
        }
        const singleProblem = verifyStandalone(generated);
        if (singleProblem) {
            console.error(`✗ ${singleProblem}`);
            process.exitCode = 1;
            return;
        }
        console.log(`✓ ${path.basename(OUT)} 与 ${path.basename(SRC)} 一致，自检通过`);
        return;
    }

    fs.writeFileSync(OUT, generated, 'utf8');
    console.log(`${stale ? '已重新生成' : '内容无变化'}  ${path.basename(OUT)}  ${generated.length} 字节`);

    const problems = await selfCheck(generated, SRC);
    if (problems.length > 0) {
        console.error('✗ 自检未通过:');
        for (const p of problems) console.error('  - ' + p);
        process.exitCode = 1;
        return;
    }
    console.log(`✓ 自检通过：${EXPECTED_MEMBERS.length} 个成员已挂载，${SAMPLES.length} 组样例与源文件结果一致`);

    const standalone = renderStandalone(generated);
    if (standalone === null) {
        console.log(`· 跳过单文件版：没找到 ${path.basename(HTML_SRC)}`);
        return;
    }
    const singleOnDisk = fs.existsSync(SINGLE_OUT) ? fs.readFileSync(SINGLE_OUT, 'utf8') : null;
    fs.writeFileSync(SINGLE_OUT, standalone, 'utf8');
    console.log(`${singleOnDisk === standalone ? '内容无变化' : '已重新生成'}  ${path.basename(SINGLE_OUT)}  ${standalone.length} 字节`);
}

try {
    await main();
} catch (err) {
    console.error(`✗ ${err instanceof Error ? err.message : String(err)}`);
    process.exitCode = 1;
}
