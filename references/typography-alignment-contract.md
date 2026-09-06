# Typography and alignment contract

Use this contract whenever a page has repeated cards, columns, numbered steps,
or dense Chinese/Latin copy. It turns visual consistency into data that can be
checked before the page is recorded.

Set `typography_policy: governed` in a new manifest before authoring its text.
That policy keeps authored sizes intact during build so QA can report overflow.
If the field is absent, the runtime retains its legacy fitting behavior for
older manifests being migrated.

## Inventory before drawing

Before writing `manifest.json`, list the text roles visible on the source:
number, title, subtitle, body, caption, label, and any other level that repeats.
For each role, record the intended font family, point size, weight, line height,
color, and source-pixel anchor. Treat a source measurement as evidence to
calibrate, then use one value for every member of that same level.

Give repeated text a shared `text_style_id`. Members of one style id must use
the same font and font size; if line height is authored, keep it the same too.
Rich text may still use runs for deliberate emphasis, but a shared style id
must not hide an accidental font or size change.

Use `alignment_group` with a `role` to name one shared alignment rail. The same
group and role must keep the same source-pixel x anchor, font, and size. Use
separate groups for genuinely different columns or rails. Number frames that
share a group and role must also have identical shape geometry and dimensions.
Give a number frame and its editable number label distinct roles such as
`number-frame` and `number-label`, so their shape and text rules stay separate.
These fields are optional for old manifests; once present, the validator checks
them deterministically. New pages should use the governed policy above so a
single box cannot be silently reduced.

## Fit dense text deliberately

With `typography_policy: governed`, the builder preserves the authored font
size. It never silently shrinks one box to cover overflow. When copy is too
long, work in this order:

1. Preserve the wording and introduce semantic line breaks at natural phrase
   boundaries.
2. Adjust the text box or the surrounding layout while retaining the measured
   anchor and hierarchy.
3. If a size change is truly necessary, apply it to the complete same-level
   style/alignment group and record the calibrated value for every member.

Run `image2ppt page validate` after each build. An estimated overflow is a page
contract failure, so repair the manifest and render again instead of accepting
a one-off per-box reduction.

## Render checks

Compare the source and the actual PowerPoint/LibreOffice render at useful
detail. Check number frames, title/body rails, baseline and line spacing,
wrapping, and every repeated group. Suggestions from another agent are input
only; the source render and the current manifest decide whether a change is
correct.
