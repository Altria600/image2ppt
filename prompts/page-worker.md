# Image2PPT profile addendum

This addendum extends the local base page prompt. It does not replace the
manifest lifecycle, ownership boundary, or the object-source contract.

Image2PPT root: {{SKILL_ROOT}}
Run directory: {{RUN_DIR}}
Page id: {{PAGE_ID}}
Page directory: {{PAGE_DIR}}
Source image: {{SOURCE_IMAGE}}

Before authoring the page, read these profile files in full when applicable:

- `{{SKILL_ROOT}}/references/region-decomposition.md`
- `{{SKILL_ROOT}}/references/object-routing.md`
- `{{SKILL_ROOT}}/references/manifest-arrow-extension.md`
- `{{SKILL_ROOT}}/references/qa-contract.md`
- `{{SKILL_ROOT}}/references/typography-alignment-contract.md`
- `{{SKILL_ROOT}}/references/source-fidelity-style-contract.md`

Profile rules:

1. `manifest.json` is the only page build source. Use schema version 2 and
   explicit `source_type` plus `editability` for every non-native visual asset.
   Keep legacy `representation` fields only when migrating an older manifest.
2. Divide structured pages into 3-8 semantic regions (1-2 only for a genuinely
   simple page), and write the evidence directly to
   `image2ppt_region_decomposition`. Do not create another controller or plan.
3. Native text, measured cards/tables/circles, ordinary connectors, and ordinary
   arrows remain native. Faithful flat icons may be `svg-reconstructed`; local
   VTracer output may be `vector-traced`; complex source material is preferably
   `source-extracted`. Image editing is a selected exception for repair, not a
   universal foreground requirement; record it as `image-edited` with
   `transform: image-edit` and complete provenance.
4. Every local asset is bounded to its source object. A full page, card, table,
   or chart image is not a valid editability shortcut. Do not introduce identity
   drift by redrawing a complex source into a generic substitute.
5. A simple arrow is one manifest shape and one PowerPoint object. Use native
   line arrowhead fields or one filled-arrow preset with embedded text. Never
   build it from a line and a separate triangle, glyph, or bitmap.
6. Record exact source coordinates, object ids, provenance, producer/model and
   any user approval. New SVG/traced/extracted assets require source_box_px;
   SVG reconstruction and source extraction require identity_evidence, while
   source extraction also requires a passed contamination_check. SVG pictures
   must be checked as vector content: no script, remote reference, or raster
   masquerading as vector.
7. Before authoring repeated text, inventory font, size, line height, color and
   x rails. Set `typography_policy: governed`; assign shared `text_style_id`
   and `alignment_group`/`role`. A number frame and its editable label have
   distinct roles. Repair semantic wrapping or the box before changing an
   entire same-level group.
8. Formula render failure is a hard page failure unless the user explicitly
   approved that exact formula omission and the manifest records the approval.
9. All page artifacts, inputs copied into the page, manifest paths and output
   overrides stay inside `{{PAGE_DIR}}`. A path escape is a hard failure.
10. Remote OCR and image services are opt-in. A selected backend cannot silently
    fall back to another provider or to invented credentials. With no image tool,
    continue local routes and report any complex visual that is blocked.

## Extended page gate

After writing the standard manifest and image ledger:

1. Run the host-supplied page build command:
   `{{PAGE_BUILD_COMMAND}}` (the owned working directory remains `{{PAGE_DIR}}`).
2. Run the host-supplied page QA command:
   `{{PAGE_QA_COMMAND}}`.
3. When a renderer is available, inspect `source.png` and the actual render at
   useful zoom across every semantic region. Check source identity, text rails,
   object count, SVG/raster boundaries, arrow atomicity and z-order. Complete
   the hash-bound visual-review evidence and rerun QA with
   `--visual-review-status reviewed` and the evidence file.
4. When no renderer is available, keep visual review pending and say so in the
   result. Structural validation is not a rendering pass.
5. Run the host-supplied contact-sheet command:
   `{{PAGE_CONTACT_COMMAND}}`, confirm top-level
   `validation.json.passed=true`, and write the standard `page_result.json`.

Supplemental reports may include:

- `arrow_postprocess_report.json`
- `arrow_inspection_report.json`
- `region_decomposition_report.json`
- `render/rendered.png` and `render_report.json` when a renderer exists
- `image2ppt_qa.json`
- `visual-review-evidence.json` only after actual visual inspection

Return exactly the standard paths requested by the base prompt. Do not return a
page as complete while a required gate is blocked or visual review is pending.
