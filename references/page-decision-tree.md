# Page Decision Tree

本文件是单页对象来源的唯一决策入口；字段见 [manifest-schema.md](manifest-schema.md)，命令见 [cli-helper.md](cli-helper.md)。每页按以下顺序工作：

1. 页面清单和语义区域。
2. 背景与遮挡关系。
3. 前景对象与来源/编辑性。
4. 原生文本、结构对象、公式和 QA 证据。

先决定“这个对象是什么、来源是什么、实际能编辑到什么程度”，再写 manifest。不要先铺一张整页底图，再把对象盖在上面。

## 预决策清单

在 manifest 中盘点：

- 页面尺寸、源图尺寸、背景类型和被遮挡位置；
- 所有可读文字、文字等级、字高、行距、密度和对齐轨道；
- 卡片、表格、圆形、边框、线、普通箭头、图表骨架等结构对象；
- 扁平图标、照片、纹理、插画、截图、徽章和其他风格资产；
- 公式候选及其文本/图片编辑边界；
- 每个对象的 `source_type`、`editability`、源文件、局部边界和 z-order；
- 矩形圆角：直角、小半径、大半径或 pill。

结构化页先分 3–8 个语义区域；真正简单的页可用 1–2 个。每个区域都必须落到标准 `text_boxes[]`、`shapes[]` 或 `images[]`，区域证据写回同一 manifest。

## 1. 背景

可直接用本地构建的背景包括纯色、简单渐变、规则纹理、普通阴影、空白区域和卡片/表格的填充。复杂照片、空间场景或插画背景只有在文字/图标遮挡且本地结构无法复原时，才需要选定的图像编辑工具做局部背景修复。

重用原稿局部前确认：它没有将被重建的文字或前景对象，不会造成重复，也不是整页、整卡片、整表或整图表的截图。背景策略应记录 `mode`、保留的构图/透视/颜色/光照/关键细节、移除的遮挡对象和与源图对比后的 `comparison_note`。

如果需要图像编辑，编辑目标是“同一背景去除待重建对象”，不是同主题新图。必须记录选定 backend、输入、提示、producer/model 和原因；工具失败时报告 blocked，不切换到未知服务。

## 2. 前景对象

按以下规则选择来源：

1. 文字默认为原生文本框；品牌字标、地图底图文字、截图内不要求编辑的小字等例外必须说明。
2. 卡片、表格、普通连接线、圆形、简单图表骨架和普通箭头按测量结果使用原生对象。
3. 扁平图标/简单标记可以忠于源稿地重建为 SVG，记录 `source_type: svg-reconstructed`、`editability: svg-image`、`source_box_px` 和 `identity_evidence`。
4. 源文件有可追踪路径时可使用本地 VTracer，记录 `source_type: vector-traced`、`editability: svg-image` 和 `source_box_px`；source 必须是页面内栅格输入。安装是可选的，不是隐式远程依赖。
5. 照片、纹理、复杂插画和无法可靠测量的数据视觉优先从原稿提取有边界的局部，记录 `source_type: source-extracted`、`source_box_px`、`identity_evidence` 和通过的 `contamination_check`；保留实际 `raster-image` 或 `svg-image` 编辑性。
6. 只有局部提取不够、需要遮挡修复或用户明确要求时才使用显式图像工具，记录 `source_type: image-edited`、`transform: image-edit` 和完整 provenance。不要把编辑后的相似图误报为原稿提取，也不要因图像工具缺失而用占位符。

所有来源都必须保持源稿身份，不能用整页/整卡片/整图表绕过编辑性，不能因为“看起来能画”就把复杂身份重绘为另一个图标。资产应绑定真实局部边界，并在 `asset_provenance` 中记录来源、变换和限制。

## 3. 原生重建

### 文字

所有主要文字必须是真实、可见、可选择的文本框。使用 `text_hints.json` 的源像素框和字高作为测量提示，但由 agent 对照源图确认字符。新页设置 `typography_policy: governed`，同级文字使用共享 `text_style_id` 和 `alignment_group`/`role`。遇到溢出时先改语义换行、框或布局，再统一调整整个同级组；不能单独缩小一个框隐藏问题。

`text_hints.json` 的 `box_px`、glyph height、CJK/Latin 字号候选和 `size_group` 都是 advisory：提示可能漏字、合并行或误识别。用 `page hints <page-dir>` 只重建一页，用 `run hints <run-dir>` 重建整次运行；远程 OCR 仍需当前命令显式带 `--allow-remote-ocr`，否则只用本地几何。主要文字不能用隐藏、透明、1 pt 或画外文本伪装。

### 公式

把公式转写为 LaTeX，并用本地 `formula render-latex` 输出 SVG/PNG 与 manifest fragment。编译器或转换器缺失、编译失败或输出缺失时，页保持失败；只有用户明确批准该公式缺失，且 `formula_inventory` 记录具体批准，才可交付。

公式不是普通文字。不要用 Unicode 上下标、源图局部或多个文本框代替。`latex-rendered-formula` 图片仍是 `svg-image`/`raster-image`，不能宣称为可编辑方程对象。

### 结构与箭头

简单可测量的卡片、圆、边框、线、表格和连接器保持 native-object。普通箭头必须一个对象并将箭头头部放在同一连接线/AutoShape；箭头标签按旁置文本或 AutoShape 内文字归属，不能创建重复文字。

圆角按源图分类：直角用 `rect`；小半径、大半径和 pill 用 `roundRect` 并写 `source_corner_radius_px`。不按个人审美默认圆角。建议 z-index 为背景 0、结构 10–20、局部资产 30、可编辑文字 40+；同一对象不能同时出现在图片层和 native 层。

PDF 有真实文字或 vector path 时先检查并提取，不能无条件整页栅格化。表格、卡片、dashboard、图表骨架仍按对象重建；复杂局部仅限真实边界。对复杂资产定义一个 source-consistent style anchor，先校准代表性资产再扩展同类处理。

## 最终自检

在记录页面前检查：

- `manifest.json` 能独立构建，所有路径位于页面目录；
- `text_inventory`、`visual_inventory` 和 positioned objects 无遗漏，来源/编辑性/provenance 对得上；
- 没有整页、整卡片、整表或整图表图片覆盖可编辑对象；
- SVG 无脚本、远程引用或栅格伪装，栅格资产边界真实；
- 字体、字号、行距、对齐轨道、圆角和 z-order 与源图一致；
- 普通箭头对象数为一，复合图节点/边锚点完整；
- 有渲染器时完成源图对 render 的逐项视觉核对；无渲染器时明确记录 QA 未验收；
- `validation.json` 顶层 `passed` 只有在全部必需门禁完成后才为 true。

结构错误、缺失对象、身份漂移、公式失败和无渲染证据不能写成普通 warning。可接受的 warning 只能是已经通过来源合同后的轻微抗锯齿、字体回退或非关键装饰差异，并需在 QA 中具体说明。

页面返回前还要确认：`manifest.json` 能独立构建；`page.pptx`、`preview.png`、`split_assets_contact.png` 和 provenance 都存在；普通箭头对象数为一；复合图节点/边锚点完整；有 renderer 时完成源图对照，无 renderer 时明确列出未验收项。`validation.json.passed` 只有在必需结构和实际可用的 QA 门禁都完成后才为 true。
