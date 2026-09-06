# Standard Manifest Arrow Extension

For `rightArrow`, `leftArrow`, `upArrow`, and `downArrow`, measure the source
head length and shaft thickness when the default silhouette differs. Record
`source_head_length_px` and `source_shaft_thickness_px` together with `box_px`.
The builder writes native AutoShape adjustment handles; these fields do not
split the arrow into multiple objects. For a 380 by 100 px right arrow with a
100 px head and 50 px shaft, use values `100` and `50`. Compare the actual PPTX
render, since the lightweight preview does not reproduce every preset handle.

These fields extend the local standard `pages/page_NNN/manifest.json`. All manifest fields, source-pixel coordinate rules, inventories, quality checks, and provenance rules remain mandatory.

## Thin connector arrow

```json
{
  "id": "flow-arrow-01",
  "type": "line",
  "points_px": [420, 318, 690, 318],
  "stroke": "#2563EB",
  "stroke_width": 2.2,
  "connector": "straight",
  "start_arrow": "none",
  "end_arrow": "triangle",
  "arrow_width": "med",
  "arrow_length": "med",
  "z_index": 140
}
```

Rules:

- `id` is required and unique within the slide.
- `type` must be `line`; `points_px` follows the source-pixel contract.
- `connector` accepts `straight`, `elbow`, or `curve`.
- `start_arrow` and `end_arrow` accept `none`, `arrow`, `triangle`, `stealth`, `diamond`, or `oval`; at least one must be non-`none`.
- `arrow_width` and `arrow_length` accept `sm`, `med`, or `lg`.
- The postprocessor converts the locally built line into one named `p:cxnSp`; it does not add a second object.
- A caption outside the connector is an ordinary standard `text_boxes[]` item. Do not use it as the arrowhead.

## Filled arrow with embedded text

```json
{
  "id": "phase-arrow-01",
  "type": "shape",
  "preset": "rightArrow",
  "box_px": [410, 292, 260, 76],
  "fill": "#2563EB",
  "stroke": "none",
  "text": "下一阶段",
  "font": "Microsoft YaHei",
  "font_size": 16,
  "text_color": "#FFFFFF",
  "bold": false,
  "align": "center",
  "valign": "middle",
  "text_margin_pt": 3,
  "z_index": 140
}
```

Supported presets are `rightArrow`, `leftArrow`, `upArrow`, `downArrow`, `leftRightArrow`, `upDownArrow`, `quadArrow`, `leftRightUpArrow`, `bentArrow`, `uturnArrow`, `stripedRightArrow`, `notchedRightArrow`, `chevron`, and `homePlate`.

The local builder creates one AutoShape from `preset`; the postprocessor names it and writes `text` into that same object's `p:txBody`. Include embedded label text in `text_inventory` so exact-text validation covers it. Do not also create a duplicate centered text box.

## Identification

The profile treats a line as an arrow only when at least one start/end arrow field is non-empty, and treats a non-line shape as an arrow only when its `preset` is one of the supported arrow presets. Ordinary lines and ordinary shapes are untouched.

The postprocessor mirrors the local builder's stable `(z_index, original order)` object-id assignment. Therefore the manifest remains independently reproducible at page and final-deck level; no page-local build script or separate plan is allowed.

Hand-drawn, textured, gradient, or illustrated arrows are not ordinary structural arrows. If their identity cannot be represented by the native presets, route the bounded visual as `source-extracted` or an explicitly selected `image-edited` asset with `transform: image-edit`, `editability: raster-image`/`svg-image`, and full provenance. This exception does not permit flattening an ordinary arrow or an entire diagram.
