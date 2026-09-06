# Manifest Schema

本文件描述运行级、页级和资产 provenance 的字段合同。所有状态由本地 CLI 推进；页面 worker 只写自己的页面目录。新字段由路由和运行时共同维护，旧 manifest 仍按兼容规则读取。

## 1. 运行级文件

### `deck_manifest.json`

由 `prepare` 创建，`run backend` 可更新 backend，`run finalize` 读取并写入完成信息。它记录输入类型、页序、画布、备注、最终输出和 `image_backend`。

```json
{
  "schema_version": 1,
  "run_id": "job-id",
  "input_type": "image|images|pdf|pptx",
  "max_concurrent_pages": 6,
  "image_backend": {
    "backend_id": "local-only",
    "tool_name": null,
    "tool_call": null,
    "model": null
  },
  "pages": [],
  "notes_manifest": "notes_manifest.json",
  "output": "final/origin_edited.pptx"
}
```

运行级 backend 合同会原样复制给每个 `page_request.json`；页级 worker 不得删减、重排或改写其中的授权和路径边界。旧运行可继续带有 `required_parameters`、`input_context_policy`、`save_path_policy` 等字段，但这些字段不能授权 fallback 或隐式联网。

`backend_id` 是显式合同，可选值：

- `local-only`：默认，本地解析、原图局部提取、SVG、VTracer（若安装）和确定性构建；
- `host-image-tool`：必须同时有用户提供的 `tool_name`、`tool_call`；
- `builtin-imagegen`：兼容显式选择的宿主 `image_gen.imagegen`；
- `external-import`：只导入用户明确提供的本地资产；
- `openai-compatible-api`：用户显式授权的 OpenAI Images-compatible 协议；
- `codex-oauth`：用户显式选择，禁止自动读取或推断 OAuth 凭据。

选择后不可静默切换。`tool_name`、`tool_call`、`model`、`input_context_policy`、`output_policy`、`producer` 和失败原因只描述实际使用的能力；它们不能扩展授权或隐藏失败。第三方 provider 按协议能力选择，不按名称、国家或语言选择。

### `page_jobs.json`

由 `prepare` 创建，由 `run next/dispatch/record/reset/finalize` 更新，是唯一页面生命周期源：

```json
{
  "schema_version": 1,
  "run_id": "job-id",
  "pages": [
    {
      "page_id": "page_001",
      "status": "pending",
      "page_dir": "pages/page_001",
      "page_request": "pages/page_001/page_request.json",
      "source": "pages/page_001/source.png",
      "dispatch": null,
      "result": null
    }
  ]
}
```

`dispatch.execution_mode` 为 `worker` 或 `local`。`local` 也适用于多页任务，但同一个 main agent 同时只能持有一个 local lease；完成 `record` 或 `reset` 后再领取下一页。超时本身不等于 worker 丢失。`max_concurrent_pages` 是并发上限，不是强制并发数。

### `page_request.json`

由 `prepare` 创建，定义页 id、页目录、源图、源像素尺寸、`slide`、`content_box`、并发上限、允许写入范围、禁止路径、必需产物、用户限制和 `image_backend`。远程 OCR 的 `--allow-remote-ocr` 是当前调用参数，不写入 page request。它不预测页面类型，也不提前决定对象来源。页面必须复制 `slide`/`content_box` 和源像素尺寸，不能自行拉伸成 16:9。

## 2. 页面结果

### `page_result.json`

由页面 worker 创建，路径均相对页面目录：

```json
{
  "page_manifest": "manifest.json",
  "imagegen_jobs": "imagegen-jobs.json",
  "page_pptx": "page.pptx",
  "preview": "preview.png",
  "contact_sheet": "split_assets_contact.png",
  "validation": "validation.json",
  "page_result": "page_result.json"
}
```

缺失产物不得虚构路径；所有路径必须相对且 resolve 在所属 page dir，绝对路径、`..` 和 symlink escape 都拒绝。`run record` 还会校验 hashes、页面 manifest 和顶层 `validation.json.passed: true`。`page.pptx` 是页级产物，最终装配仍从已记录的 manifest 按页序重建。

### `validation.json`

必须有顶层布尔值：

```json
{"passed": true}
```

结构校验、区域检查和视觉 QA 可以写入附加字段；嵌套的 `passed` 或 free-text 不能替代顶层值。没有渲染器时可以构建和做结构检查，但 `visual_review_status` 应保持 pending/unsupported，不能据此写 true。

## 3. `manifest.json`

新页使用 `schema_version: 2` 和 `typography_policy: governed`；v1 仍可读。manifest 是页面构建和最终装配的唯一来源，不是对另一个手写 PPTX 的摘要。

必需字段：

```text
schema_version, typography_policy, slide, content_box, source,
page_strategy, text_inventory, visual_inventory, background_strategy,
quality_checks, quality_evidence, text_boxes, shapes, images,
asset_provenance
```

`source.path`、资产、公式、报告和 output override 都必须位于页面目录。页面构建应在同目录临时文件中完成并成功后原子发布，失败不得留下半成品。`slide`、`content_box` 和 `source.width_px/height_px` 来自 `page_request.json`。坐标都来自 `source.png`：`box_px: [x,y,w,h]`、`points_px: [x1,y1,x2,y2]`、`polygon_px` 和 `bezier_px` 使用源像素；`bezier_px` 为连续三次 Bézier 段。每个定位文本、图片和非线形状必须有 `box_px`；线必须有 `points_px`；Bézier 必须有 `box_px` 与段数据。

## 4. 视觉来源与编辑性

新 `visual_inventory[]` 对每个视觉对象至少记录：

```json
{
  "id": "metric-icon",
  "kind": "foreground-asset",
  "source_type": "svg-reconstructed",
  "editability": "svg-image",
  "path": "assets/metric-icon.svg",
  "source_box_px": [120, 80, 48, 48],
  "identity_evidence": "轮廓、比例、负空间和颜色依据源图复核",
  "processing_method": "faithful-svg-reconstruction",
  "reason": "扁平图标作为可移动 SVG 图片保留"
}
```

`kind` 为兼容字段，允许 `background`、`foreground-asset`、`native-structure`、`formula`。新页的核心合同是 `source_type` 与 `editability`：

| `source_type` | 含义 | 合法 `editability` |
| --- | --- | --- |
| `native-object` | 由确定性构建器生成的原生文本/形状/表格/连接线 | `native-object` |
| `svg-reconstructed` | 依据源稿重建的忠实扁平 SVG | `svg-image` |
| `vector-traced` | 本地 VTracer 追踪源路径得到的 SVG | `svg-image` |
| `source-extracted` | 源稿有边界局部的原始提取 | `raster-image` 或 `svg-image` |
| `image-edited` | 显式选择的图像编辑/生成工具的输出 | `raster-image` |
| `imagegen` | 历史图像工具输出，兼容读取 | `raster-image` |
| `latex-rendered-formula` | 本地 LaTeX 渲染结果 | `svg-image` 或 `raster-image` |
| `user-provided` | 用户已提供的外部局部资产 | 按实际为 `svg-image` 或 `raster-image` |
| `user-approved-rasterization` | 用户明确批准的栅格化例外 | `raster-image` |

新页禁止用 `representation` 单字段表达编辑性；旧值可兼容映射：`native` → `native-object`，`asset-sheet-separated` → 依据 provenance 重新填写 `source_type` 与 `editability`。不确定时必须报告，而不是猜测为 native。

`svg-reconstructed`、`vector-traced` 和 `source-extracted` 必须有 `source_box_px`（或兼容的 `source_bbox_px`），表示源图中的真实局部边界。`svg-reconstructed` 与 `source-extracted` 还必须有非空 `identity_evidence`；`source-extracted` 必须有 `contamination_check: {"passed": true, "observation": "..."}`，说明邻近文字、边框或其他对象没有混入。`vector-traced` 的 `source` 必须是实际本地栅格输入（通常为 `source.png` 或页面内提取图），不能伪造为一个已经生成的 SVG。

旧 manifest 的 `representation` 仍允许 `native`、`asset-sheet-separated`、`source-preserving-local-cleanup`、`imagegen`、`latex-rendered-formula`，以及迁移期间的 `svg-reconstructed`、`vector-traced`、`source-extracted`、`image-edited`。它只用于兼容读取；新页以结构化 `source_type`/`editability` 为准。新字段的合法组合为：`native-object`→`native-object`，`svg-reconstructed`/`vector-traced`→`svg-image`，`source-extracted`→`raster-image` 或 `svg-image`，`image-edited`→`raster-image`，公式按实际 SVG/栅格格式记录。

`visual_inventory` 只盘点对象；真正定位对象仍写入 `text_boxes[]`、`shapes[]`、`images[]`。原生文字通常在 `text_inventory` 与 `text_boxes` 中记录，不需要伪造图片 provenance。

## 5. `asset_provenance`

每个 `images[].path` 都必须有一条匹配记录，且来源路径存在于页面目录：

```json
{
  "path": "assets/photo.png",
  "source": "source.png",
  "source_type": "source-extracted",
  "editability": "raster-image",
  "source_box_px": [320, 210, 260, 180],
  "identity_evidence": "照片主体和原稿局部构图逐项核对",
  "contamination_check": {
    "passed": true,
    "observation": "提取框未包含相邻文字或卡片边框"
  },
  "processing_method": "bounded-source-extraction",
  "reason": "仅保留复杂视觉的真实局部边界",
  "producer": "local-extractor",
  "model": null,
  "transform": "bounded source-region extraction",
  "provenance_note": "仅保留源稿中对应的照片局部"
}
```

图像编辑/生成时必须写实际 `producer`、精确 `model`（如有）、输入文件、提示或编辑意图、`transform: image-edit`、用户授权边界和失败/重试原因。`builtin-imagegen` 只能记录显式使用的宿主工具；`host-image-tool` 必须记录工具名/调用名；`external-import` 必须记录用户选定的本地源。禁止记录 key、OAuth 内容或机器私有路径。

SVG 资产按内容检查：拒绝脚本、远程引用和仅改名的栅格内容；记录其可移动/可替换的 `svg-image` 编辑性。复杂视觉优先 `source-extracted`，图像编辑是受控例外。整页、整卡、整表和整图表不能作为局部资产。

## 6. Typography、质量和区域证据

新页必须有：

```json
"quality_checks": {
  "font_size_calibrated": true,
  "visual_inventory_matched": true,
  "background_strategy_checked": true,
  "shape_corner_geometry_checked": true
}
```

每个检查对应 `quality_evidence`，`observation` 至少 12 个字符并指向实际 source/preview/render。`typography_policy: governed` 下，构建器不单独缩小文本来掩盖溢出；用语义换行、改框或整体同级字号修复。`text_style_id` 约束字体/字号/行高，`alignment_group` + `role` 约束源像素对齐轨道；number frame 与 number label 使用不同 role。

结构页将 `image2ppt_region_decomposition` 放入同一 manifest。每个区域记录 `source_bbox_px`、strategy、风险、manifest ids 和 protected anchors；复合图记录节点中心/尺寸、边端点/方向/线型。该字段是 QA 证据，不是第二个 plan 或 controller。

`text_inventory` 可以是字符串列表，也可以是结构化对象；用于精确文本校验的字段包括 `text`、`required_text`、`items` 和 `texts`，`id`、`decision`、`description`、`note` 只作记录。`text_boxes[].align` 接受 `left`、`center`、`right`（以及兼容 DrawingML 的 `l`、`ctr`、`r`）；`valign` 接受 `top`、`middle`、`bottom`（`center` 映射为 `middle`）。文本 inventory 不能替代 positioned `text_boxes`。

每个新页的 `quality_checks` 至少包含以下四个为 `true` 的标志，并为每项提供具体 `quality_evidence.*.observation`（至少 12 个字符，可附 `artifact`）：

```json
{
  "font_size_calibrated": true,
  "visual_inventory_matched": true,
  "background_strategy_checked": true,
  "shape_corner_geometry_checked": true
}
```

例如：

```json
{
  "font_size_calibrated": {
    "observation": "标题和正文等级与源图一致且没有裁断",
    "artifact": "render/rendered.png"
  },
  "visual_inventory_matched": {
    "observation": "源图中的五个视觉对象各出现一次"
  },
  "background_strategy_checked": {
    "observation": "背景构图、透视和颜色与源图保持一致"
  },
  "shape_corner_geometry_checked": {
    "observation": "卡片半径和表格直角按放大源图复核"
  }
}
```

`background_strategy` 至少说明 `mode`、`source_consistency_contract`、`removed_foreground` 和比较源图后的 `comparison_note`。`mode` 可为 `native-or-script`、`source-preserving-local-cleanup` 或明确的 image-edit clean base；它不能把整页源图伪装成可编辑背景。

所有 `roundRect` 必须记录 `source_corner_radius_px`，并可记录 `corner_category`（`straight`、`small-radius`、`large-radius`、`pill`）与 `corner_reason`；直角使用 `rect`。圆角是源对象属性，不按审美默认圆角。

`text_boxes[].box_px` 应是源文字边界加适度 padding，而不是整张卡、整张表或无关容器。`font_size` 是 authored points；governed 页面不允许 builder 静默缩小单个 box。`min_font_size`、`max_font_size`、`text_fit_safety`、`line_height` 等测量字段是辅助信息，不是逃避字号治理的开关。

## 7. 公式与箭头

公式图片的 provenance 使用 `latex-rendered-formula`，必须来自 `formula render-latex`；缺少 engine、转换器或编译失败是硬失败，除非 `formula_inventory` 对该公式写入 `user_approved_exception: true` 和具体 `approval_note`。

一个完整的公式记录至少包含：

```json
{
  "id": "formula_01",
  "status": "rendered",
  "editable": false,
  "image": "assets/formula_01.svg",
  "tex_source": "assets/formula_01.tex"
}
```

带有图片的公式条目还应将 `images[].path` 与 `.tex` 源文件、`asset_provenance.source_type: latex-rendered-formula` 和 `formula_inventory.image` 对齐；公式图片的视觉保真优先于方程对象编辑性。

公式失败或用户批准例外的完整形状：

```json
{
  "id": "formula_01",
  "status": "blocked",
  "user_approved_exception": true,
  "approval_note": "用户明确批准省略 formula_01，并记录批准日期和原因"
}
```

内部判断、普通 warning 或 `validation.json.passed=true` 都不能代替该具体批准。公式图片必须来自 `formula render-latex`，不能使用源图中的公式局部或大量手写文本框拼装。

`images[]`、`asset_provenance[]` 和 `formula_inventory[]` 必须互相匹配。缺失、失败或仅有 free-text 的公式条目都不能关闭页面门禁；明确批准例外时仍须记录具体公式和批准说明。

普通箭头的 `shapes[]` 必须是一条 line（原生端点箭头）或一个 filled-arrow AutoShape；箭头内文字写在同一 shape 的 `text` 字段。不要创建独立箭头头部、重复标签或整图替代。完整字段在 `manifest-arrow-extension.md`。

## 8. `imagegen-jobs.json`

`image import` 和 `image process-sheet` 记录页内资产处理；generate/edit 本身不写 ledger。新记录至少包含：

```json
{
  "job_id": "asset-01",
  "role": "source-extracted|asset|clean_base",
  "status": "recorded",
  "output": "assets/object.png",
  "output_sha256": "...",
  "backend": "local-only|host-image-tool|builtin-imagegen|external-import|openai-compatible-api|codex-oauth",
  "model": null,
  "fallback_reason": null
}
```

`backend` 必须是真实 producer；没有静默 fallback。旧版 `asset-sheet-separated` 等 source type 只为历史页面保留，不能成为新页的泛化硬规则；历史 imagegen 输出仍保留，新页的 image-edit 过程使用 `image-edited` provenance。

历史运行中的 ledger 可能还包含 `source_image`、`output_sha256`、`role` 和 `fallback_reason`。这些字段应继续保留并如实填写；`source_image` 可以是 import 时的外部输入记录，但 manifest build dependency 必须使用页面内 `output`。绝不通过扫描目录或文件时间推断实际结果。

## 9. 路径与迁移补充

页面拥有的 manifest、资产、公式、报告和 `--out` 覆盖都必须 resolve 到所属 page dir；绝对路径输入只允许在 `image import`/显式输入复制阶段使用。`..`、symlink escape 和跨页引用都是硬失败。run/final 产物必须在 prepared run 内，finalize 先写同目录临时文件，成功后原子发布。

`notes_manifest.json` 由 `prepare` 创建，由 `run finalize` 读取，保存原始 speaker-note XML/文本、页映射和 hashes。页面 worker 不翻译、摘要、重写或删除 notes。

## 10. 备注与兼容

`prepare` 提取 PPT/PPTX speaker notes，页面 worker 不翻译、不重写、不删除。`run finalize` 是唯一装配阶段，并恢复源 notes 和 hashes。删除旧字段前先检查历史页面；任何迁移都不能创建第二个状态文件或第二条装配路径。
