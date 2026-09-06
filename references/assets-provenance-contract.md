# Assets and Provenance Contract

资产来源和 PPT 编辑性是两件事，必须分别记录。原生对象直接由 manifest 构建；SVG 和栅格文件是独立图片资产，必须有真实边界、来源和内容检查。

## 来源优先级

1. 可测量的文字、卡片、表格、普通线条、普通箭头和基础图表结构使用 `native-object`。
2. 忠实扁平图标使用 `svg-reconstructed` + `svg-image`；有可靠源路径时可使用本地 VTracer，记录 `vector-traced` + `svg-image`。
3. 照片、纹理和复杂局部优先从原稿提取并限定到实际边界，记录 `source-extracted` + `raster-image`/`svg-image`。
4. 只有提取不足或需要遮挡修复时，才使用显式选择的图像编辑/生成工具，记录 `image-edited`、`transform: image-edit`、producer、model、输入、提示和原因。

任何来源都不能整页覆盖，也不能把整张卡片、整张表或整张图表当作资产来跳过对象重建。重建 SVG 必须保持源稿轮廓、比例、负空间和颜色；复杂视觉不能为了得到“可编辑”而换成另一个身份。

VTracer 的输入应是页面目录内仅包含目标局部的栅格文件；命令 `--box` 只记录源像素边界，不会从输入中截取局部。整页输入加小 box 不是合法的局部资产。

## 页内资产路径

所有 manifest、provenance、报告和输出路径都解析在所属页面目录内。外部绝对路径只允许作为用户明确选择的 import 输入，复制后必须使用页面内相对路径。禁止通过 `..`、symlink 或未记录的临时目录建立构建依赖。

## SVG 安全检查

SVG 不能只按扩展名信任。导入前检查：

- 没有 `<script>`、事件处理器、远程 URL、外部实体或未授权字体/图片引用；
- 真正包含 vector path/text/shape，而不是嵌入一张 PNG 或把栅格改名为 `.svg`；
- viewBox 和内容边界对应源对象，未丢失负空间、描边或透明度；
- PPTX 中记录为 `svg-image`，可移动/可替换，但不宣称已转成 PowerPoint 原生路径。

## `asset_provenance` 最小结构

```json
{
  "path": "assets/icon.svg",
  "source": "source.png",
  "source_type": "vector-traced",
  "editability": "svg-image",
  "source_box_px": [120, 80, 48, 48],
  "processing_method": "local-vtracer",
  "reason": "源图局部路径可追踪，使用本地 VTracer 保留轮廓",
  "producer": "vtracer",
  "model": null,
  "transform": "local raster-to-SVG trace",
  "provenance_note": "输入是页面内 source.png 的真实局部，输出为可移动 SVG 图片而非原生 PPT 路径"
}
```

`svg-reconstructed` 记录 `source_box_px` 和 `identity_evidence`；`vector-traced` 的 source 必须是本地栅格输入。`source-extracted` 除 `source_box_px` 和 `identity_evidence` 外，还必须记录：

```json
"contamination_check": {
  "passed": true,
  "observation": "提取框未包含相邻文字、边框或其他对象"
}
```

`source_type` 新页使用 `native-object`、`svg-reconstructed`、`vector-traced`、`source-extracted`、`image-edited` 或 `latex-rendered-formula`；历史 `imagegen` 仍可读取。`editability` 只能是 `native-object`、`svg-image` 或 `raster-image`。用户提供的本地资产可用 `user-provided` 或 `user-approved-rasterization`，但必须说明原始提供者、实际格式和批准边界。

## 图像工具边界

图像工具只能在显式 backend 合同下运行。`local-only` 不联网；`host-image-tool` 必须有 `--tool-name`/`--tool-call`；`builtin-imagegen` 只兼容显式选择的宿主工具；`external-import` 只导入用户选中的本地结果；`openai-compatible-api` 和 `codex-oauth` 都要用户明确选择。工具失败不触发静默 fallback，也不允许把失败页写成成功页。

用户选择外部服务时，只上传当前任务所需的源图、局部、mask 和提示；密钥、OAuth 文件和机器路径不进入仓库、run、manifest 或日志。敏感材料默认留在本地。

## `imagegen-jobs.json`

`image import` 记录 producer、选定文件、目的路径、hash、role、model 和明确的失败/重试原因；不扫描“最新文件”猜结果。`image process-sheet` 只处理已导入且在页面目录中的资产表。图片编辑或生成不是对象路由本身，页面仍需在 `visual_inventory` 中写来源与编辑性。
