# Region Decomposition and Mixed Reconstruction

区域证据帮助页面在“原生对象、SVG 图片和局部栅格资产”之间做可复核的混合重建。它不创建第二个 plan，`page_jobs.json` 仍是状态源，`manifest.json` 仍是构建源。

## 两级路由

1. 结构化页先分 3–8 个语义区域；真正简单的页可用 1–2 个。
2. 每区盘点文字、基础结构、普通箭头、视觉资产、公式和 z-order。
3. 测量源像素，再为每个对象记录 `source_type`、`editability` 和来源证据：
   - 原生文字、卡片、表格、普通边框、圆、线和普通箭头：`native-object` / `native-object`；
   - 忠实扁平图标：`svg-reconstructed` / `svg-image`，含 `source_box_px` 与 `identity_evidence`；
   - 可追踪源路径：`vector-traced` / `svg-image`，含 `source_box_px`，source 为页面内栅格输入；
   - 复杂照片、纹理或插画局部：优先 `source-extracted` / `raster-image` 或 `svg-image`，含 `source_box_px`、`identity_evidence` 与通过的 `contamination_check`；
   - 只有提取/本地修复不足时才是 `image-edited` + `transform: image-edit` / `raster-image`。
4. 选择 `native-object-decomposition`、`mixed-reconstruction`、`bounded-local-asset` 或 `native-text-layout`，然后把对象写入标准数组。

复杂区域也不能整体用图片覆盖所有可编辑对象；`bounded-local-asset` 只能描述它真实包含的局部。图标 SVG 必须保持源稿身份，不能用相似符号代替。

## 复合图

知识图谱、节点关系图、流程图和矩阵应记录：

- 每个节点中心、宽高、真实几何（circle/ellipse/document/complex asset）；
- 每条关系的端点、方向、线型、箭头归属；
- 标签锚点、z-order 和对应 manifest id；
- 哪些节点/边为原生、哪些局部为 SVG/栅格资产及其 provenance。

重复布局只能作测量交叉检查，不能套用模板。简单可测量节点和连接器保持原生；复杂图标只占用实际局部资产。不要把整张知识图谱或流程图变成一张图片。

## Protected visual anchors

每个节点和边都写入区域的 `protected_visual_anchors`：

- 圆、环、节点边界和 document-node 边界；
- 线端点、路线、箭头头部、弯折和汇合点；
- 虚线节奏、卡片边缘、分隔线、图标和标签锚点。

文本清理或背景修复不得擦除、复制、偏移或裁断这些锚点。render review 需检查节点数量、中心、大小、边端点/方向/虚线、标签和层级。

## Manifest extension

证据直接放在标准 manifest：

```json
{
  "image2ppt_region_decomposition": {
    "schema_version": "image2ppt-region-decomposition-v1",
    "page_complexity": "structured",
    "source_size_px": [1672, 941],
    "regions": [
      {
        "id": "knowledge-graph",
        "label": "Measured knowledge graph",
        "source_bbox_px": [904, 373, 391, 370],
        "risk_level": "high",
        "strategy": "mixed-reconstruction",
        "reason": "measured native nodes plus bounded source-faithful local assets",
        "manifest_ids": {
          "shapes": ["node_concept", "edge_concept_threshold"],
          "text_boxes": ["label_concept"],
          "images": ["pictogram_core"]
        },
        "protected_visual_anchors": [
          {
            "id": "anchor-node-concept",
            "kind": "circle-node",
            "manifest_id": "node_concept",
            "source_bbox_px": [1051, 467, 25, 25]
          }
        ],
        "compound_diagram": {
          "kind": "knowledge-graph",
          "object_inventory_complete": true,
          "measurement_reviewed": true,
          "native_object_policy": "measured-simple-objects-native",
          "nodes": [
            {
              "id": "concept",
              "manifest_id": "node_concept",
              "geometry": "circle",
              "source_center_px": [1063.5, 479.5],
              "source_size_px": [25, 25],
              "position_tolerance_px": 2,
              "size_tolerance_px": 2
            }
          ],
          "edges": [
            {
              "id": "concept-to-threshold",
              "manifest_id": "edge_concept_threshold",
              "source_points_px": [1063, 492, 1063, 535],
              "line_style": "solid",
              "direction": "end"
            }
          ]
        }
      }
    ]
  }
}
```

`source_bbox_px` 使用 `[x,y,width,height]`，`source_points_px` 使用源像素端点。区域引用的 id 必须在标准 manifest 存在且每个对象只归属一个区域。复合图不可用 `bounded-local-asset` 表示整个区域。

## Review gate

运行 `inspect_region_decomposition.py`，再逐区对照源图与实际 render。报告是证据，不是 controller；任何测量错误、缺失 anchor、重复对象或身份漂移都应修复 manifest 后重新 build。
