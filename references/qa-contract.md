# Supplemental QA Contract

Local deterministic validation remains mandatory. Image2PPT adds region/compound-diagram evidence, arrow atomicity, and render-based visual review.

## Page gate

Required standard artifacts are exactly those in the local manifest schema:

- `manifest.json`
- `imagegen-jobs.json`
- `page.pptx`
- `preview.png`
- `split_assets_contact.png`
- `validation.json`
- `page_result.json`

Supplemental evidence is:

- `arrow_postprocess_report.json`
- `arrow_inspection_report.json`
- `region_decomposition_report.json`
- `render/rendered.png`
- `render_report.json`
- `image2ppt_qa.json`

`run_image2ppt_qa.py` must be the last validation command before writing standard `page_result.json`. It reruns local page validation after modifying the PPTX, then sets:

```json
{
  "passed": true,
  "image2ppt_profile": {
    "passed": true,
    "visual_review_status": "reviewed"
  }
}
```

at the relevant locations in standard `validation.json`. Do not replace `validation.json` with a profile-specific result file.

## Arrow inspection

For every profiled manifest arrow:

- `shapes[].id` resolves to exactly one PowerPoint object on the corresponding slide;
- a connector is one `p:cxnSp` with the expected straight/elbow/curve preset;
- start/end arrowheads are children of that connector's own line properties;
- a filled arrow is one `p:sp` with the expected Arrow AutoShape preset;
- `text`, when specified on a filled arrow, exists in that same object's text body;
- no duplicate object name creates an ambiguous mapping.

Machine inspection proves object structure, not visual fidelity.

## Typography and alignment inspection

`image2ppt page validate` audits the optional `text_style_id` and
`alignment_group`/`role` fields without changing the manifest. It rejects:

- one `text_style_id` used with different fonts, font sizes, or line heights;
- same-group, same-role text with a drifting source-pixel x anchor, font, or
  font size;
- same-group, same-role number frames with a drifting source-pixel x anchor or
  different native geometry/size; use separate roles for a number frame and
  its editable label;
- a governed (`typography_policy: governed`) text box whose authored size is
  estimated to overflow its measured box.

Older manifests without the policy or governance fields retain legacy fitting
and remain compatible. Governed overflow is repaired by semantic wrapping,
box/layout adjustment, or a complete same-level size change before record.

## Region and compound-diagram inspection

`inspect_region_decomposition.py` validates the in-manifest
`image2ppt_region_decomposition` block against standard object ids and source
coordinates. It rejects:

- a structured page without 3-8 semantic regions;
- region references to missing manifest objects;
- manifest objects that were never assigned to a semantic region;
- a high-risk region without protected visual anchors;
- a compound diagram flattened as one region asset;
- an incomplete or unreviewed compound-object inventory;
- node centers/sizes or edge endpoints that do not match the reviewed source measurements;
- a declared circle implemented as a distorted ellipse;
- a missing direction arrowhead or dashed relationship style;
- a compound node/edge without a protected anchor.

Machine inspection proves internal measurement consistency. Source-versus-render review still determines whether the measurements themselves are correct.

## Rendered review

Compare `source.png` with the actual PowerPoint/LibreOffice render at matching aspect ratio. Check:

- arrow direction, bend, curvature, thickness, head type/size, and z-order;
- semantic region boundaries and composition;
- compound diagram node count, centers, sizes, circle geometry, connector endpoints, direction, dash rhythm, labels, and z-order;
- filled-arrow silhouette and embedded-label centering;
- composition, text hierarchy, line breaks, font fallback, assets, formula rendering, missing objects, and duplicate source text;
- typography inventory, same-level font/size/line-height consistency, alignment
  group anchors, number-frame geometry, and governed text overflow;
- no full-slide source image or source reuse masquerades as a render.

Specific review notes are mandatory. A generic phrase such as "looks good" is not sufficient evidence.

## Final gate

After every local `image2ppt run finalize`, run `run_final_image2ppt_qa.py`. It must report:

- local deck validation still passes;
- page count and render count match;
- speaker-note hashes still match through the local validator;
- all profiled arrows pass one-object inspection in the rebuilt final deck;
- every manifest passes region/compound-diagram inspection;
- every rendered slide was compared with its source;
- `final/image2ppt_qa.json.passed` is true.

If final QA fails, fix the authoritative page manifest through the same local lifecycle and finalize again. Do not patch the final deck manually as the only fix.
