---
name: image2ppt
description: Convert slide images, screenshots, scanned PDFs, and image-only PPT/PPTX files into high-fidelity object-level editable PowerPoint with measured structure, governed typography, source-faithful assets, and rendered QA. Use for 图片转可编辑PPT、截图还原PPT、扫描PDF恢复、图片型PPTX转换、流程图/知识图谱/复合图形/箭头重建; not for authoring a new deck from notes.
---

# Image2PPT

Use this directory as the complete runtime. Run deterministic actions only through:

```bash
python <image2ppt-root>/cli/image2ppt/cli.py <command> ...
```

For this project-local Windows deployment, substitute
`<image2ppt-root>/.venv/Scripts/python.exe` for every `python` command below when
that interpreter exists. It contains the pinned runtime dependencies and avoids
depending on the user's global Python environment.

Do not discover or invoke another Skill, CLI, Prompt, Schema, module, or state machine.

## Read the local contracts

Before a run, read:

- `references/workflow.md`
- `references/runtime-dependencies.md`
- `references/ocr-text-hints-contract.md`

Before reconstructing a page, also read:

- `references/page-decision-tree.md`
- `references/manifest-schema.md`
- `references/region-decomposition.md`
- `references/object-routing.md`
- `references/manifest-arrow-extension.md`
- `references/assets-provenance-contract.md`
- `references/typography-alignment-contract.md`
- `references/source-fidelity-style-contract.md`

Before accepting or delivering output, read `references/qa-contract.md`.

## Preserve the single source of truth

- Treat `page_jobs.json` as the only page-state source.
- Treat each `pages/page_NNN/manifest.json` as the only page-content source.
- Treat `deck_manifest.json` as the final-assembly source.
- Use only `prepare`, `run next/dispatch/record/reset/hints/finalize`, and the
  page commands in the local CLI for stateful lifecycle operations.
- Keep semantic-region evidence in `manifest.json.image2ppt_region_decomposition`.
- Never create a second job file, reconstruction plan, OCR normalizer, page
  controller, packager, or finalize path.
- Let supplemental QA report failures; never let it mutate lifecycle state.

## Preserve pre-migration behavior

- Treat self-containment as a path/import/entrypoint migration, not a redesign of
  reconstruction behavior.
- Generate each worker Prompt from the complete local base layer plus the preserved
  Image2PPT profile layer. Do not condense, reinterpret, or replace either layer.
- Prefer the previously validated visual strategy when several routes satisfy the
  contracts. Keep simple measured objects native and retain bounded complex assets
  wherever a native redraw would reduce fidelity.
- Never re-author an accepted baseline page merely to prove runtime independence.

## Run the workflow

### 1. Preflight and OCR choice

```bash
python <image2ppt-root>/cli/image2ppt/cli.py doctor --json
```

Use Baidu AI Studio `PADDLE_OCR_TOKEN` when configured. If it is absent, tell the
user once that the local `builtin-ink` fallback measures text geometry but does
not recognize characters; offer the configuration path in
`references/ocr-text-hints-contract.md`. Respect an offline-only choice.

### 2. Prepare one run

```bash
python <image2ppt-root>/cli/image2ppt/cli.py prepare <input...> \
  --out-root output/image2ppt --image-backend builtin-imagegen
```

Use `--no-text-hints` only when OCR processing is intentionally disabled. Regenerate
hints without creating a new run when needed:

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run hints <run-dir>
```

### 3. Advance and claim pages

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run next <run-dir> --json
python <image2ppt-root>/scripts/build_page_worker_prompt.py \
  <run-dir> --page <page-id> --out <absolute-page-dir>/worker-prompt.md
python <image2ppt-root>/cli/image2ppt/cli.py run dispatch \
  <run-dir> --page <page-id> --agent-id <id> --prompt-file <absolute-prompt>
```

For exactly one page, claim it with `--local` and reconstruct it in the current
agent. For multiple pages, dispatch independent page workers up to the capacity in
`page_jobs.json`. Do not reset a live worker merely because it is slow.

### 4. Reconstruct and gate each page

Before drawing, inventory text roles, shared styles, alignment rails, and one
visual style anchor for the page. Set `typography_policy: governed` in new
manifests, then record repeated text with `text_style_id` and
`alignment_group`/`role` when those rails are present. The governed builder
never changes authored typography to hide overflow; manifests without the new
policy retain legacy fitting for migration compatibility. Follow
`references/typography-alignment-contract.md` for fitting and render checks,
and `references/source-fidelity-style-contract.md` for PDF structure,
visible-source composition, and asset/style decisions.

Plan a structured page as 3–8 semantic regions and route each region independently.
Use measured compound diagrams: measure every node, relation, and protected anchor. Keep measurable
circles, cards, straight/dashed relations, and simple connectors native. Use bounded
transparent assets only for complex local subparts.

Represent a thin arrow as one connector with its arrowhead on the same object.
Represent a filled arrow as one Arrow AutoShape, with centered label text inside the
same object. Never construct an ordinary arrow from a line plus triangle and never
flatten a whole knowledge graph into one image.

The worker Prompt performs the deterministic sequence. Its final gates are:

```bash
python <image2ppt-root>/cli/image2ppt/cli.py page build <page-dir>
python <image2ppt-root>/scripts/run_image2ppt_qa.py <page-dir>
# inspect source.png against render/rendered.png, repair, then:
python <image2ppt-root>/scripts/run_image2ppt_qa.py <page-dir> \
  --visual-review-status reviewed \
  --visual-review-notes "<specific observations checked>"
python <image2ppt-root>/cli/image2ppt/cli.py page contact-sheet <page-dir>
```

Record only after standard validation and the Image2PPT region, arrow, and rendered
gates pass:

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run record \
  <run-dir> --page <page-id> --agent-id <id>
```

Use the same `run reset` → dispatch → record lifecycle to repair rejected pages.

### 5. Finalize and revalidate the rebuilt deck

When `run next` reports `finalize`, run:

```bash
python <image2ppt-root>/cli/image2ppt/cli.py run finalize <run-dir>
python <image2ppt-root>/scripts/run_final_image2ppt_qa.py <run-dir>
# inspect every rendered slide against its source, repair manifests if needed, then:
python <image2ppt-root>/scripts/run_final_image2ppt_qa.py <run-dir> \
  --visual-review-status reviewed \
  --visual-review-notes "<specific checks covering every slide>"
```

Finalize rebuilds from page manifests, preserves source speaker notes, validates the
package, and writes the output recorded by `deck_manifest.json`. Final QA reapplies
manifest arrows, verifies arrow atomicity and compound structure, renders every
slide, checks speaker-note integrity, and writes `final/image2ppt_qa.json`.

## Deliver

Return the final PPTX path, standard final validation, and
`final/image2ppt_qa.json`. Report which complex visuals remain replaceable bitmap
assets. Do not call the deck complete while any page/final gate is pending or failed.
