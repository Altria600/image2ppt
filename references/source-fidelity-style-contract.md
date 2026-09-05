# Source fidelity and visual style contract

Use this contract when deciding how to preserve a page's visible composition,
especially for PDFs, image-heavy slides, or pages with generated assets.

## Preserve the visible source

- If the source contains a final visible composite, use that composite as the
  reference for the background and z-order. Do not restore a hidden or covered
  old base that changes what the viewer sees.
- A source image is evidence for measurement and visual comparison. Do not put
  the whole page screenshot into the PPTX as a background to simulate
  editability.
- For PDFs, inspect whether real text or vector paths are available first and
  extract those structures when practical. Do not rasterize every PDF page
  unconditionally and discard editable structure.
- Keep complex illustrations, photos, and other hard-to-measure local visuals
  as independent bounded transparent assets when native reconstruction would
  visibly drift. Keep simple measured cards, lines, circles, and connectors as
  native PowerPoint objects.

## Keep one visual language

For a page with multiple generated or edited assets, define one visual style
anchor and carry the same prompt contract across the asset set: subject,
viewpoint, lighting, palette, edge treatment, background/alpha behavior, and
level of detail. Calibrate one complex representative asset, compare it to the
source render, and only then produce the remaining assets in the same contract.

Whether people in the source are shown as real, cartoon, or motion-graphic
style is a task input. Preserve the user's choice for that task; do not encode
one of those styles as a universal Image2PPT preference.

Every asset still needs a manifest entry and provenance record. The source
comparison and actual PowerPoint/LibreOffice render remain the acceptance
evidence for composition, style, and z-order.
