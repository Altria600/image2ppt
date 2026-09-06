# Object Routing

本文件补充 [page-decision-tree.md](page-decision-tree.md) 的区域、混合重建和箭头规则。页面生命周期仍只有 `page_jobs.json`，构建源仍只有 `manifest.json`。

## 区域决策顺序

1. 先把结构化页面分成 3–8 个语义区域；真正简单的页面可用 1–2 个。
2. 在每个区域内盘点文字、结构对象、图像对象、箭头和公式。
3. 以源像素测量对象，按来源和编辑性路由，而不是按模型或国家名称路由。
4. 选择 `native-object-decomposition`、`mixed-reconstruction`、`bounded-local-asset` 或 `native-text-layout`，并将对象写入标准 manifest 数组。
5. 在 `image2ppt_region_decomposition` 中记录区域、manifest id、边界、风险和受保护视觉锚点。

## 来源与编辑性

新 manifest 将“如何获得”和“在 PPT 中怎样编辑”分开记录：

| `source_type` | 适用对象 | `editability` |
| --- | --- | --- |
| `native-object` | 文字、卡片、表格、普通线条/箭头、可测量基础形状 | `native-object` |
| `svg-reconstructed` | 依源稿轮廓重建的扁平图标或简单标记；需 `source_box_px`、`identity_evidence` | `svg-image` |
| `vector-traced` | 本地 VTracer 根据页面内栅格源生成的 SVG；需 `source_box_px` | `svg-image` |
| `source-extracted` | 从原稿提取的照片、纹理、复杂插画或复杂局部；需 `source_box_px`、`identity_evidence` 和通过的 `contamination_check` | `raster-image` 或 `svg-image` |
| `image-edited` | 用户选择的图像编辑/生成工具处理的局部或干净背景 | `raster-image`；必须有 producer/model/输入/原因 |
| `latex-rendered-formula` | 本地 LaTeX 渲染的公式资产 | `svg-image` 或 `raster-image` |

`representation` 是旧 manifest 的兼容字段，新页不应以它代替上述两项。每个局部资产都应有独立边界和来源说明；复杂资产优先 `source-extracted`，只在原稿局部无法保真分离或需要背景修复时采用显式图像工具，并将 `source_type: image-edited`、`transform: image-edit` 和 producer/model 写全。历史 `imagegen` 仍可读取。扁平图标 SVG 必须忠于源稿，不得用通用符号替代；VTracer 未安装时不得静默改走远程服务。processing method 应使用 `faithful-svg-reconstruction`、`local-vtracer`、`bounded-source-extraction` 或其他 manifest-schema 中的受控值。

VTracer 的输入必须先在页面目录内准备成只含目标局部的栅格文件；命令的 `--box` 仅记录原始源像素边界，不会替输入做局部截取。不能把整页输入矢量化后再用一个小 box 声称得到了局部资产。

## 普通箭头

普通结构箭头必须是一个 manifest shape 和一个 PowerPoint 对象：

| 源箭头 | manifest 表达 | PPT 对象 |
| --- | --- | --- |
| 直线细箭头 | `type: line`、`connector: straight`、原生端点箭头 | 1 个 `p:cxnSp` |
| 折线细箭头 | `type: line`、`connector: elbow`、原生端点箭头 | 1 个 `p:cxnSp` |
| 简单曲线箭头 | `type: line`、`connector: curve`、原生端点箭头 | 1 个 `p:cxnSp` |
| 填充方向箭头 | 一个 `rightArrow` 等 AutoShape preset | 1 个 `p:sp` |
| Chevron/process 箭头 | 一个 `chevron` preset | 1 个 `p:sp` |
| 填充箭头内文字 | 同一 shape 的 `text` | 仍为 1 个对象 |

手绘、纹理、渐变或插画化箭头不属于普通结构箭头：先判断它是否是页面风格资产，再按 `source-extracted` 或明确的 `image-edited`（`transform: image-edit`）记录。不要为了满足“一对象”而把真正的风格资产误转成普通线条。

以下做法对普通箭头不合格：线段加独立箭头三角形、多个线段拼接简单折线、Unicode 箭头字形、用整张图替代可测量箭头。箭头旁的文字是普通文本框；填充箭头内的文字只能属于同一 AutoShape。

## 复合图与区域混合

知识图谱、流程图、矩阵和节点关系图要记录每个节点中心/尺寸、真实圆形或椭圆、每条边的端点/方向/线型、标签锚点、z-order 和对应 manifest id。可测量的圆、卡片、线和连接器保持原生；只有复杂图标或风格化局部使用有边界的 SVG/栅格资产。不能把整个复合图压成一张图片。

每个节点和边都放入 `protected_visual_anchors`，并在渲染 review 中核对节点数量、中心、尺寸、边端点、箭头方向、虚线节奏、标签和层级。区域报告是证据，不是第二套构建计划。
