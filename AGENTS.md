# Coding rules

## Product contract

- Reconstruct existing images, scanned PDFs and image-only presentations into editable PPTX; export SVG assets alongside it. Preserve source identity and layout. Do not add slide authoring, Illustrator automation, or a web application. Repository publication requires explicit user authorization.
- Use the Image2PPT runtime as the base. Retain its MIT license and attribution. Cell-lct is a design reference only: do not copy unlicensed source.
- Route per object within semantic page regions. Native text, cards, tables and ordinary arrows stay editable. Simple flat icons may use faithful SVG. Complex visual assets retain source identity through extraction or image editing. A shadow alone does not require generation.
- SVG pictures are movable/replaceable assets, not automatically editable PowerPoint paths. Record and report the actual editing level. Never claim a whole-page bitmap is an editable reconstruction.

## Implementation discipline

- Inspect existing callers and conventions before changing code. Use the smallest necessary change; no unrelated cleanup, speculative framework or duplicate state machine.
- Keep one manifest and page lifecycle. Extend fields compatibly; accept valid legacy manifests. Keep routing decisions, prompts, schema and provenance validation consistent.
- Use Python pathlib and argument-list subprocess calls for portable execution. Support Windows and macOS, Chinese names and paths with spaces. Avoid POSIX-only assumptions in the shared runtime.
- Detect available capabilities rather than assigning behavior by model brand or country. A host image tool is explicitly supplied by the host, never inferred from another application's credential file.
- Default to local processing. Optional remote OCR and image providers require the user's existing authorization; never silently switch to a new external service, charge money or upload materials. No keys, login tokens or machine-specific paths in tracked files or logs.
- Check SVG assets as vector content, not just a filename: reject scripts, remote references and raster masquerading as vectors. Preserve content bounds and text ownership.
- Report blocked objects/pages explicitly. Preserve completed page results; never pass missing rendering or visual review as successful QA.

## Team ownership

- Astra owns architecture, interface decisions, integration review and acceptance. Luna max owns implementation tasks with explicit non-overlapping file scopes.
- Read the task assignment and current files before writing. Do not overwrite another worker's edits, switch branches, stash, reset or clean. Workers do not commit or push; the coordinator may publish only within explicit user authorization.
- Propose changes outside your file scope to the coordinator. Coordinate shared interfaces before changing callers owned by another worker.
- Return changed files, behavior, exact checks and remaining limits. The coordinator verifies integrated output; a worker's completion message is not final acceptance.

## Verification and handoff

- Run relevant existing tests before and after changes. Add behavior tests for routing, provenance, provider selection and platform-sensitive failures; avoid tests that merely match documentation wording.
- Use local fixtures; tests must not call paid services or upload user data. Validate SVG/PPTX structure and render actual generated PPTX when a renderer is available.
- Keep offline CI for Windows/macOS. Host integration and PowerPoint/WPS manual acceptance are distinct from unit tests; record untested combinations honestly.
- Chinese user-facing docs should state setup, supported inputs, output editability and failure recovery clearly. Keep SKILL.md provider-neutral and route detailed instructions to relevant references.
