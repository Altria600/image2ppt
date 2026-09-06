---
name: image2ppt
description: Reconstruct existing slide images, scanned PDFs, and image-only PPT/PPTX files as high-fidelity editable PowerPoint pages with measured typography, mixed object routing, provenance, and rendered QA. Use for 图片转可编辑PPT、截图还原、扫描 PDF 恢复和图片型 PPT/PPTX 转换；不用于根据提纲创作新演示文稿。
---

# Image2PPT

这是一个本地优先的重建运行时。目标是把已有视觉页面拆成可复核的文本、原生结构、SVG 图片和有来源的局部栅格资产，再从唯一的页面 manifest 重新构建 PPTX。不要把整页截图放进 PPTX 来伪装可编辑，也不要把重建工作改成新幻灯片创作。

所有确定性操作都通过本目录内的 CLI 完成：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py <command> ...
```

建议使用 Python 3.10+ 虚拟环境。Mac/Linux 使用 `.venv/bin/python`，Windows 使用 `.venv\\Scripts\\python.exe`；不要假设全局安装了 `image2ppt` 命令。

## 先读哪些合同

每次任务先读 [references/workflow.md](references/workflow.md)。准备输入或诊断依赖时读 [references/runtime-dependencies.md](references/runtime-dependencies.md)；只有明确允许远程 OCR 时读 [references/ocr-text-hints-contract.md](references/ocr-text-hints-contract.md)。

写页面 manifest 前读 [references/page-decision-tree.md](references/page-decision-tree.md) 和 [references/manifest-schema.md](references/manifest-schema.md)。结构化页面再读 [references/region-decomposition.md](references/region-decomposition.md) 与 [references/object-routing.md](references/object-routing.md)；箭头读 [references/manifest-arrow-extension.md](references/manifest-arrow-extension.md)；资产、PDF 和复杂局部读 [references/assets-provenance-contract.md](references/assets-provenance-contract.md) 与 [references/source-fidelity-style-contract.md](references/source-fidelity-style-contract.md)；重复或密集文字读 [references/typography-alignment-contract.md](references/typography-alignment-contract.md)。

交付前必须读 [references/qa-contract.md](references/qa-contract.md)。CLI 参数以 [references/cli-helper.md](references/cli-helper.md) 和当前 `--help` 为准；文档不会替代运行时的参数校验。

## 不可改变的产品边界

- 输入是已有图片、扫描 PDF 或图片型 PPT/PPTX；不根据笔记、提纲或主题从零写 deck。
- 每页只有一个 `manifest.json` 作为构建源；`page_jobs.json` 是唯一生命周期状态源；`deck_manifest.json` 只负责运行级输入、页序、备注和最终装配。
- 原生文本、卡片、表格、普通连接线和普通箭头应保持独立 PowerPoint 对象。复杂视觉只保留实际局部，不能覆盖整页、整张卡片、整张表或整张图表。
- SVG 是可移动、可替换的 SVG 图片，不自动等于 PowerPoint 原生路径；manifest 必须分别记录 `source_type` 和 `editability`，交付时如实报告。
- 不因模型名称、国家或语言推断能力。按实际可用的本地工具、主机图像工具、协议能力和用户授权选择路径。
- 默认离线本地处理。远程 OCR、图像生成或编辑都必须由用户显式选择并提供相应授权；不可读取未被选择的凭据、静默上传、收费或自动切换 provider。

## 对象路由摘要

先按页面区域理解对象，再按对象选择来源：

| 源对象 | 首选来源 | manifest 记录 |
| --- | --- | --- |
| 可读文字、标题、标签、数字 | PowerPoint 原生文本 | `source_type: native-object`，`editability: native-object` |
| 卡片、表格、普通边框、圆形、普通连接线/箭头 | PowerPoint 原生形状/连接线 | `source_type: native-object`，`editability: native-object` |
| 可稳定识别的扁平图标或简单标记 | 保持轮廓、比例、颜色和负空间的 SVG | `source_type: svg-reconstructed`，`editability: svg-image` |
| 源文件有可追踪路径、且本地 VTracer 可复现 | VTracer 生成的 SVG，再做安全检查 | `source_type: vector-traced`，`editability: svg-image` |
| 照片、纹理、复杂插画、复杂图表局部 | 从原稿提取的有边界局部资产 | `source_type: source-extracted`，`editability: raster-image` 或 `svg-image` |
| 原稿遮挡修复或本地提取不足的局部 | 用户显式选择的图像编辑/生成工具 | `source_type: image-edited`，`editability: raster-image`，并记录 `transform: image-edit` |
| 历史或兼容输出 | 既有 imagegen/user-provided 资产 | 按实际格式保留兼容 source type，并补充 `editability` |

新 `svg-reconstructed`、`vector-traced`、`source-extracted` 资产必须记录真实 `source_box_px`；SVG 重建和源稿提取还要写 `identity_evidence`，源稿提取必须写 `contamination_check.passed: true` 与具体 observation。VTracer 的 source 应是页面内栅格输入，不是已经生成的 SVG。

扁平图标的 SVG 重建不是“重画一个相似图标”：必须能说明轮廓和视觉身份来自源稿。复杂视觉优先保留原稿身份；只有原稿局部无法干净分离或需要背景修复时才用图像编辑。任何路径都不能造成身份漂移。

可选的本地 VTracer：

```bash
python -m pip install vtracer
```

未安装时仍可走原生对象、SVG 重建或原图局部资产；不能把缺少 VTracer 自动变成远程调用或近似占位。VTracer 输入必须是页面目录内只含目标局部的栅格文件，`--box` 只记录源像素边界，不会从整页输入中截取局部。

## 图像 backend 合同

backend 是显式运行级合同，写入 `deck_manifest.json.image_backend` 和每页 `page_request.json`。新运行默认 `local-only`：不调用网络图像服务，不读取 Codex OAuth 或其他应用凭据。

| backend | 用途与边界 |
| --- | --- |
| `local-only` | 默认。使用本地解析、提取、SVG、VTracer（若安装）和确定性构建；缺工具时报告 blocked。 |
| `host-image-tool` | 用户明确提供主机图像工具名和调用名；必须显式设置 `--tool-name` 与 `--tool-call`，不得猜测工具。 |
| `builtin-imagegen` | 兼容宿主提供的 `image_gen.imagegen`；只在运行合同显式选择时使用，编辑前先检查输入，结果必须通过 `image import` 记录。 |
| `external-import` | 用户已在本地准备好资产；只导入明确路径，不在本地运行时联网或猜测最新文件。 |
| `openai-compatible-api` | 用户显式授权并提供 OpenAI Images-compatible endpoint、key 和 model；按协议能力判断，不按 provider 名称判断。 |
| `codex-oauth` | 仅用户显式选择时使用；不得自动读取或推断 OAuth 文件，也不能从其他 backend 静默回退。 |

选择某 backend 后不可无声切换。工具不可用、返回无有效本地输出、输入不可读或协议失败时，保留已完成页并把当前页标为 blocked/failed，说明准确原因和下一步；只有用户重新选择 backend 后才能重试。`builtin-imagegen` 的兼容路径也不改变这一点。

主机工具的通用配置示例：

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run backend <run> \
  --mode host-image-tool \
  --tool-name '<host tool name>' \
  --tool-call '<host tool call>'
```

`openai-compatible-api` 需要显式配置 `OPENAI_BASE_URL`、`OPENAI_API_KEY` 和精确的 `IMAGE2PPT_IMAGE_MODEL`；`codex-oauth` 不会因为 model id 看起来像 GPT Image 就被 `auto` 选中。不要把 key、token 或 OAuth 文件写进仓库、Prompt、manifest、日志或 ZIP。

## OCR 与文本提示

默认只使用本地 `builtin-ink` 测量文字几何，不上传、不读取 Paddle token。只有用户明确允许远程 OCR 时，才在当前 `prepare` 或 `run hints` 调用加 `--allow-remote-ocr`，并使用本地配置中的 token；这个授权不写入 page request，也不成为持久状态。网络失败不触发隐式上传或 provider 切换，保留本地测量并报告限制。文字字符仍须由 agent 对照源图核对，OCR 只是提示。

## 页面生命周期

### 1. 准备一次运行

```bash
python <image2ppt-root>/cli/image2ppt/cli.py prepare <input...> \
  --out-root output/image2ppt --image-backend local-only
```

`prepare` 生成唯一运行目录、页源图、`page_request.json`、`page_jobs.json`、备注清单和本地文本提示。多页任务可以选择并发 worker；没有 delegation 能力时，主 agent 也可以逐页串行执行，每次只持有一页：`run dispatch --local` → 构建/QA → `run record`，再处理下一页。不得同时为同一 main agent 持有多个 local lease。

### 2. 领取并重建页面

```bash
python <image2ppt-root>/scripts/build_page_worker_prompt.py \
  <run-dir> --page <page-id> \
  --out <absolute-page-dir>/worker-prompt.md
python <image2ppt-root>/cli/image2ppt/cli.py run dispatch \
  <run-dir> --page <page-id> --agent-id <id> \
  --prompt-file <absolute-prompt> [--local]
```

页面 worker 只能写自己的页面目录；不得改运行级 manifest、其他页、原始输入、最终输出或 notes。并发是可选的，不能因为有并发槽位就牺牲页面所有权。

### 3. 先决策，再写 manifest

先完成页面清单和 3–8 个语义区域（真正简单的页可用 1–2 个），再记录背景、前景、原生结构和公式来源。所有坐标都是 `source.png` 像素；每个定位对象必须有 `box_px` 或 `points_px`。新 manifest 使用 `schema_version: 2`、`typography_policy: governed`、结构化 `visual_inventory`、`quality_evidence`、`source_type` 和 `editability`。

保持以下原则：

- 文字默认原生；公式由 `formula render-latex` 生成有 provenance 的 SVG/PNG，渲染失败是硬失败，除非用户明确批准该公式例外。
- 普通箭头是一个连接线或一个 AutoShape，箭头头部属于同一对象；不要用多个对象拼接普通箭头。
- 每个复杂局部都绑定到真实边界；不把整页、整卡片、整表或整图表作为绕过编辑性的图片。
- 记录原始输入/提取/追踪/编辑的实际来源、producer、model、提示和限制；不能只写“已处理”。

### 4. 构建与验收页面

```bash
python <image2ppt-root>/cli/image2ppt/cli.py page build <page-dir>
python <image2ppt-root>/cli/image2ppt/cli.py page validate <page-dir>
python <image2ppt-root>/scripts/run_image2ppt_qa.py <page-dir>
python <image2ppt-root>/cli/image2ppt/cli.py page contact-sheet <page-dir>
```

`page build` 和结构验证可以在没有 Office 渲染器时运行，但不能把它们称为渲染 QA 通过。只有实际的 LibreOffice、PowerPoint 或明确可用的渲染器产出并完成源图对照，页面才可标记 `visual_review_status: reviewed`；缺少渲染器必须写明“未验收”。Windows PowerPoint、WPS 和不同字体环境的差异需要在目标环境人工复核，本 Skill 不声称已验证它们的等价渲染。

视觉证据必须绑定当前源图和 render 的 hash，并逐项说明文字、层级、对象完整性、箭头、资产、字体回退和溢出。泛泛的“看起来没问题”不能关闭 QA。

### 5. 记录、装配与修复

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run record \
  <run-dir> --page <page-id> --agent-id <id>
python <image2ppt-root>/cli/image2ppt/cli.py run finalize <run-dir>
python <image2ppt-root>/scripts/run_final_image2ppt_qa.py <run-dir>
```

`run record` 只接受页级 `validation.json.passed: true` 且全部必需产物存在的页面；缺少渲染器的页面不能伪造为通过。失败页通过 `run reset` 后按相同生命周期重做，已完成页不会被覆盖。`finalize` 只从已记录页面的 manifest 重建最终 deck，并恢复源 speaker notes；最终 QA 仍需实际 render 与结构检查。

## 交付与安装

仓库使用 Codex repo skill 方式时，把本目录放进当前项目的 `.agents/skills/image2ppt/`，再用本地 Python 运行 CLI。不要依赖全局 Skill 安装。

跨宿主分发时，用仓库脚本生成 ZIP：

```bash
python <image2ppt-root>/scripts/package_skill.py --help
python <image2ppt-root>/scripts/package_skill.py --output dist/image2ppt.zip
```

实际参数以该脚本的 `--help` 为准；ZIP 应包含本 Skill 及运行时，不应包含 `config.yaml`、凭据、运行目录或缓存。WorkBuddy 使用“本地 ZIP 导入”即可；不要在文档中编造 WorkBuddy 的自动发现目录或自动安装机制。当前文档不宣称 Windows、WorkBuddy、PowerPoint 或 WPS 已完成验证。

交付时返回最终 PPTX、页/最终 `validation.json` 和 QA 报告，并列出仍为 `svg-image` 或 `raster-image` 的复杂资产。任何 blocked 页、未渲染页、未核对页或未记录 provenance 的对象都必须明确报告。
