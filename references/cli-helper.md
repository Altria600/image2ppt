# CLI Helper

本文件只记录本地 CLI 的可复用入口；参数发生变化时以当前代码的 `--help` 为准。所有 page/run 路径都要落在对应目录内，不用临时 Python/PowerPoint 脚本绕过 manifest。

## 入口与安装

不依赖全局安装，直接使用：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py --help
python <image2ppt-root>/cli/image2ppt/cli.py doctor --json
```

运行命令树：

```text
image2ppt
|-- doctor / config / prepare
|-- run: next, status, backend, dispatch, record, reset, hints, finalize
|-- page: hints, build, contact-sheet, validate
|-- vector: trace, validate
|-- image: generate, edit, import, process-sheet
`-- formula: render-latex
```

跨平台 Python 环境和 renderer 限制见 [runtime-dependencies.md](runtime-dependencies.md)。跨宿主分发使用 `scripts/package_skill.py` 打 ZIP，不使用 pipx 或全局 Skill 安装。

## 准备、提示和状态

默认本地运行：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py prepare input.pdf \
  --out-root output/image2ppt --image-backend local-only
```

远程 OCR 必须显式允许：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py prepare input.pdf \
  --allow-remote-ocr
python <image2ppt-root>/cli/image2ppt/cli.py run hints <run-dir> \
  --allow-remote-ocr
```

默认不读取 Paddle token、不上传。`--no-text-hints` 只在明确不需要提示时使用。

读取下一动作。没有 delegation 时加 `--local`，让多页运行也一次只建议一页：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run next <run-dir> --json --local
```

JSON 的 `next_argv` 是供宿主直接执行的参数数组，适合中文名和带空格的路径；`next_command` 仅供人读，不要把它当 shell 字符串重新拼接。

生成页 Prompt 并 dispatch：

```bash
python <image2ppt-root>/scripts/build_page_worker_prompt.py \
  <run-dir> --page page_001 \
  --out <run-dir>/pages/page_001/worker-prompt.md
python <image2ppt-root>/cli/image2ppt/cli.py run dispatch <run-dir> \
  --page page_001 --agent-id <id> \
  --prompt-file <run-dir>/pages/page_001/worker-prompt.md
```

没有 delegation 时，多页也按页串行：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run dispatch <run-dir> \
  --page page_001 --agent-id main \
  --prompt-file <run-dir>/pages/page_001/worker-prompt.md --local
```

同一个 main agent 在 `record` 或 `reset` 前不能领取第二个 local page。`--prompt-file` 必须位于该页目录。

## Backend 合同

设置 run-level backend：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run backend <run-dir> \
  --mode local-only
python <image2ppt-root>/cli/image2ppt/cli.py run backend <run-dir> \
  --mode host-image-tool \
  --tool-name '<host tool name>' \
  --tool-call '<host tool call>'
```

可选模式为 `local-only`、`host-image-tool`、`builtin-imagegen`、`external-import`、`openai-compatible-api` 和显式 `codex-oauth`。后两种需要用户授权；Codex OAuth 不自动读凭据，任何模式都不静默 fallback。`builtin-imagegen` 只兼容宿主 `image_gen.imagegen`，不是默认路径。

`openai-compatible-api` 的 key、base URL 和 model 只写本机 `config.yaml` 或受控环境变量：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py config \
  --api-key '<key>' \
  --base-url 'https://example.invalid/v1' \
  --model '<provider-model-id>' \
  --image-backend openai-compatible-api
```

## 页面构建与 QA

```bash
python <image2ppt-root>/cli/image2ppt/cli.py page build pages/page_001
python <image2ppt-root>/cli/image2ppt/cli.py page validate pages/page_001
python <image2ppt-root>/scripts/run_image2ppt_qa.py pages/page_001
python <image2ppt-root>/cli/image2ppt/cli.py page contact-sheet pages/page_001
```

`page build` 从 `manifest.json` 生成 `page.pptx` 和 `preview.png`；`page validate` 执行与 `run record` 相同的结构合同。没有 renderer 时这些命令可能仍能构建/检查，但 visual review 必须保持 pending/unsupported。

完成页后：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run record \
  <run-dir> --page page_001 --agent-id <id>
python <image2ppt-root>/cli/image2ppt/cli.py run finalize <run-dir>
python <image2ppt-root>/scripts/run_final_image2ppt_qa.py <run-dir>
```

## Vector trace

本地 VTracer 是可选能力，不是 provider。先确认命令和版本：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py vector trace --help
```

`vector trace` 的实际参数如下：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py vector trace \
  pages/page_001 \
  --input assets/isolated-icon.png \
  --out assets/diagram.svg \
  --source source.png \
  --box 100,100,300,200 \
  --fragment diagram-fragment.json \
  --id diagram \
  --alt "source-faithful traced visual" \
  --z-index 220
```

可选 `--page-dir DIR` 强制路径边界，`--force` 才允许覆盖已有 SVG/fragment；输出别名为 `--output`。也可用 `vector trace INPUT OUTPUT`，但生成 page fragment 时必须让 source 位于 page dir。`vector validate SVG [--page-dir DIR]` 检查受信任 SVG 子集。

`--input` 必须是已经在 page dir 内、只包含目标局部的本地栅格输入（示例 `assets/isolated-icon.png`）；`--source` 指向原始 `source.png`。`--box` 只把源像素边界写入 fragment/provenance，不会对 `--input` 做局部截取或缩放，不能用整页输入再靠 `--box` 冒充局部资产。VTracer 仅在显式命令中运行，绝不上传或自动 fallback。生成的 SVG 记录 `source_type: vector-traced`、`editability: svg-image` 和 `source_box_px`，并通过无脚本、无远程引用、无栅格伪装的 SVG 安全检查。若 fragment 直接合并到新 manifest，补充对应的 `processing_method: local-vtracer` 与 `reason`。

## Image import/edit 与资产处理

仅在选定 backend 允许时使用 generate/edit；local-only 不调用它们。显式导入用户或工具返回的本地结果：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py image import pages/page_001 \
  --job-id object-01 \
  --source-image /absolute/path/selected.png \
  --dest assets/object.png \
  --role source-extracted \
  --backend external-import
```

`--source-image` 必须是用户选定的可读文件；不扫描目录猜“最新输出”。页面资产经 import 后才可被 manifest 引用。`image process-sheet` 只处理已导入的、页面目录内的 sheet；它不是普通对象必须经过的强制路径。

跨宿主分发：

```bash
python <image2ppt-root>/scripts/package_skill.py \
  --output dist/image2ppt.zip \
  --source <image2ppt-root>
```

`--stage <new-directory>` 可选地生成未压缩副本；ZIP/目录必须不存在，脚本拒绝覆盖。它只打包显式 Skill 文件并排除 run、cache、tests、config.yaml 和凭据，不做全局安装或宿主自动发现。

## 公式

```bash
python <image2ppt-root>/cli/image2ppt/cli.py formula render-latex \
  pages/page_001 --tex "\\sum_{i \\in N} p_{ij}x_{ij}" \
  --out assets/formula_001.svg --box 100,120,360,80 \
  --id formula_001 --fragment assets/formula_001.fragment.json
```

公式是图片资产，不是可编辑方程对象；manifest 需记录 `latex-rendered-formula` provenance。渲染失败按公式硬门禁处理。
