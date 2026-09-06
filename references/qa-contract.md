# Supplemental QA Contract

QA 分为结构门禁和实际 render 对照。结构检查通过不等于视觉通过；没有 renderer 时可以构建和做静态检查，但必须把视觉 review 标为 pending/unsupported。

## 页面产物和门禁

标准页产物：

- `manifest.json`
- `imagegen-jobs.json`
- `page.pptx`
- `preview.png`
- `split_assets_contact.png`
- `validation.json`
- `page_result.json`

补充证据可包括 `arrow_postprocess_report.json`、`arrow_inspection_report.json`、`region_decomposition_report.json`、`render/rendered.png`、`render_report.json`、`image2ppt_qa.json` 和 hash-bound `visual-review-evidence.json`。

`page validate` 必须在 `run record` 前通过；`run record` 还检查路径边界、必需文件、hash、manifest 和 `validation.json` 顶层 `passed: true`。没有 renderer 的页面不能仅靠 `page validate` 标记 `visual_review_status: reviewed`，也不能用旧 evidence 复用。

## 来源、编辑性和资产 QA

对每个 `visual_inventory`/`images[]` 复核：

- `source_type` 与 `editability` 都存在且相互匹配；
- 新 SVG、VTracer 和源稿提取资产都有真实 `source_box_px`；SVG 重建/源稿提取有 `identity_evidence`；源稿提取有 `contamination_check.passed: true` 与 observation；
- 原生文本、卡片、表格、普通线和普通箭头确实是 native-object；
- 扁平图标 SVG 保留源稿轮廓和负空间，记录为 `svg-reconstructed`；可追踪源路径使用 `vector-traced`；
- 复杂照片/插画/纹理局部优先 `source-extracted`，边界真实且不是整页/整卡/整表/整图表；
- 显式 image-edit（`source_type: image-edited`、`transform: image-edit`）资产有 producer、model、输入、提示/意图、授权和原因，失败没有被藏成成功；
- SVG 无脚本、远程引用或栅格伪装；栅格资产可移动、可替换且 provenance 可追溯。

来源/编辑性不一致、对象身份漂移、缺失资产或整页图片绕过编辑性是硬失败，不是 warning。

## Arrow inspection

对每个普通箭头复核：

- `shapes[].id` 唯一并映射到对应 slide 上一个 PowerPoint 对象；
- 连接线是一个 `p:cxnSp`，端点箭头位于同一 line properties；
- 填充箭头是一个 `p:sp` AutoShape，`text` 位于同一对象的 `p:txBody`；
- 没有线段+独立三角、Unicode 箭头、重复 caption 或不必要的组。

手绘/纹理/渐变箭头若是风格资产，应按 `source-extracted` 或显式 `image-edited`（`transform: image-edit`）检查，而不是强行当作普通线。机器检查只证明结构，仍需 render 对照。

## Typography and alignment inspection

`typography_policy: governed` 下：

- 同一 `text_style_id` 的字体、字号、行高一致；
- 同一 `alignment_group` + `role` 的源像素 x anchor、字体和字号一致；
- 同组同角色 number frame 的原生几何/尺寸一致，number frame 与 number label 用不同 role；
- 估算溢出的文本先修语义换行、框或同级组，不单独缩小一个 box。

旧 manifest 缺少 governed 字段时保留迁移兼容，但新页不能以旧 fitter 隐藏溢出。

## Region and compound-diagram inspection

`inspect_region_decomposition.py` 应检查 `image2ppt_region_decomposition`：

- 结构化页有 3–8 个区域（真正简单页可用 1–2）；
- 区域 id 引用真实 manifest objects，所有对象都有归属；
- 高风险区域有 protected anchors；
- 复合图未被一张图片替代；
- 节点中心/尺寸、边端点/方向、圆形几何和线型与源测量一致；
- 每个节点/边的锚点存在且对象类型匹配。

机器报告是内部测量一致性检查，不能代替源图与 render 的视觉判断。

## Rendered review

有 renderer 时，比较同一宽高比的 `source.png` 与实际 PowerPoint/LibreOffice render，至少检查：

- 页面构图、区域边界、z-order 和背景遮挡；
- 文字层级、字符、行距、换行、字体回退、字号统一和溢出；
- 卡片/表格/圆角、节点数量/中心/尺寸、连接器端点/方向/虚线节奏；
- 普通箭头的弯折、头部、厚度、对象数和填充箭头内文字；
- SVG/raster 资产边界、透明边缘、源身份、缺失对象和重复源文字；
- 公式实际 render 和 provenance。

证据必须绑定当前 source/render SHA-256，并为每项写具体观察（至少 12 个字符）。不要用“looks good”或自由文本替代证据文件。WPS、Windows 和目标 Office 的人工复核仍是额外验收，不在本合同中默认为已验证。

没有 renderer 时，应记录无法取得 render 的准确原因，保持 `visual_review_status: pending` 或 `unsupported`，并列出未检查项。禁止用 preview、结构通过或旧截图冒充 Office render。

## Final gate

每次 `run finalize` 后运行 `run_final_image2ppt_qa.py`。有 renderer 时最终证据必须覆盖：页数、每页 source/render hash、notes hash、manifest/asset provenance、arrow atomicity、region anchors 和全部视觉检查；最终 `final/image2ppt_qa.json.passed` 才能为 true。无 renderer 时可保留 final build/structure 结果，但最终视觉状态必须明确未验收。

如果 final QA 失败，按 page manifest 的 lifecycle 修复、reset、record、finalize；不要只补丁最终 PPTX。
