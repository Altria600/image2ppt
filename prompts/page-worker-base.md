# Page Reconstructor Prompt

占位符 `{{NAME}}` 由 `scripts/build_page_worker_prompt.py` 填充。

```text
Rebuild one existing source page for Image2PPT.

Run dir: {{RUN_DIR}}
Page id: {{PAGE_ID}}
Page dir: {{PAGE_DIR}}
Source image: {{SOURCE_IMAGE}}

You own only this Page dir. Do not edit deck_manifest.json, page_jobs.json,
notes_manifest.json, final outputs, the original input, or another page.

MANDATORY FIRST ACTION: before inspecting source.png or making any object
decision, read these files in full:
- {{SKILL_ROOT}}/references/page-decision-tree.md
- {{SKILL_ROOT}}/references/manifest-schema.md
- {{SKILL_ROOT}}/references/cli-helper.md

Read only the additional contracts required by this page:
- structured page: region-decomposition.md and object-routing.md
- arrows: manifest-arrow-extension.md
- assets/PDF/style: assets-provenance-contract.md and source-fidelity-style-contract.md
- repeated text: typography-alignment-contract.md
- acceptance: qa-contract.md

Goal: reconstruct the existing page as a measured, mixed PowerPoint page. The
page is not a new deck. Keep the visible source identity and record what is
actually editable; do not claim that an SVG image is a native PowerPoint path.

SOURCE ROUTING (record before writing objects):
1. Native text, cards, tables, ordinary borders, ordinary lines, and ordinary
   arrows stay native. A simple arrow is one connector or one AutoShape, not a
   shaft plus a separate head.
2. A flat icon or simple mark may become a faithful SVG image. Record
   source_type=svg-reconstructed, editability=svg-image, source_box_px, and
   identity_evidence.
3. If source paths are traceable, local VTracer is allowed when installed.
   Prepare a page-local raster file containing only the target local visual;
   `--box` records source geometry and does not crop a full-page input. Record
   source_type=vector-traced, editability=svg-image, and source_box_px; use the
   original raster source for provenance and inspect the SVG for scripts,
   remote references, and raster payloads.
4. For photos, textures, complex illustrations, or hard-to-measure chart
   fragments, prefer a bounded asset extracted from the original source.
   Record source_type=source-extracted, editability=raster-image or svg-image,
   source_box_px, identity_evidence, and a passed contamination_check with a
   concrete observation. Preserve the source identity and exact local boundary.
5. Use an explicitly selected image-edit/generation backend only when local
   extraction or background repair cannot preserve the visible source. Record
   source_type=image-edited, transform=image-edit, producer, model, inputs, prompt,
   and reason. Never silently switch
   backend, invent credentials, or replace a failed path with a lookalike.
6. Never use one full-page, full-card, full-table, or full-chart bitmap to skip
   object reconstruction. Do not redraw a complex asset into a different visual
   identity merely to make it editable.

BACKEND:
- Read page_request.json.image_backend exactly. The default is local-only.
- host-image-tool requires the explicit tool_name and tool_call in the contract.
- builtin-imagegen is compatibility-only and is used only when selected.
- external-import accepts only a user-selected local file.
- openai-compatible-api and codex-oauth are explicit choices only. Codex OAuth
  credentials are never auto-read and there is no silent fallback.
- If the selected tool is unavailable, the input is unreadable, or no valid
  local output is returned, write a concrete blocked/failed result. Preserve
  completed artifacts; do not make an approximate page to pass validation.

OCR:
- Use local text geometry by default. Do not upload or read a Paddle token.
- Remote OCR is allowed only for a current prepare/run hints invocation when
  the user explicitly supplied --allow-remote-ocr; this is not persisted in
  page_request.json or another page-state field.
- Text hints are advisory. Read characters from the source and make all
  readable editable text real visible native text boxes.

WORK ORDER:
1. Inventory page size, text roles, background, visual objects, structural
   primitives, formulas, regions, and corner geometry.
2. Divide a structured page into 3-8 semantic regions (1-2 only when genuinely
   simple). Measure source-pixel coordinates and record each route.
3. Set typography_policy=governed. Reuse text_style_id and
   alignment_group/role for repeated levels and rails. Repair wrapping and box
   geometry before changing a whole level's size; never silently shrink one box.
4. Write schema-v2 manifest.json. Every positioned text/image/shape has box_px,
   points_px, or bezier_px. Add visual_inventory, asset_provenance,
   quality_checks, quality_evidence, and image2ppt_region_decomposition when
   relevant. Keep all paths inside this page directory.
5. Build and validate with the local CLI. The host supplies executable,
   page-local commands; keep PAGE_DIR as the owned working directory:
   {{PAGE_BUILD_COMMAND}}
   {{PAGE_VALIDATE_COMMAND}}
6. Run the page QA:
   {{PAGE_QA_COMMAND}}
   If a renderer exists, inspect source.png against the actual render and
   complete hash-bound visual-review evidence. Without a renderer, leave QA
   pending/unevaluated and report that limitation; never mark it reviewed from
   structural validation alone.
7. Create the standard page_result.json only after every required gate passes.

Required page artifacts:
- manifest.json
- imagegen-jobs.json
- page.pptx
- preview.png
- split_assets_contact.png
- validation.json (top-level boolean passed)
- page_result.json

On failure, write validation.json with passed=false and the concrete failed
condition, then write page_result.json with only paths for artifacts that exist.
Do not fabricate missing render, asset, or validation evidence.

Return only:
page_manifest=<absolute path>
page_pptx=<absolute path>
preview=<absolute path>
contact_sheet=<absolute path>
validation=<absolute path>
page_result=<absolute path>
```
