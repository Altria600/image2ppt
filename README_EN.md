<div align="center">
  <p>
    <img src="assets/readme/banner.png" alt="Image2PPT: from slide images to object-level editable PowerPoint" width="100%">
  </p>
  <p>
    <a href="LICENSE"><img alt="License" src="https://img.shields.io/badge/license-MIT-2ea44f"></a>
    <a href="#installation-and-configuration"><img alt="Install" src="https://img.shields.io/badge/install-Claude%20Code%20%7C%20Codex-8b5cf6"></a>
    <a href="README.md"><img alt="Language" src="https://img.shields.io/badge/language-中文%20%7C%20English-1f6feb"></a>
  </p>
</div>

# Image2PPT

🧩 Image2PPT specializes in reconstructing **complex business slides and scientific flowcharts** as high-fidelity, object-level editable PowerPoint while preserving clarity and fine relationships in dense layouts and compound diagrams.

## Capabilities and Examples

Simple image-to-PPT pages are no longer the hard part. The real challenge is a complex page with many elements, dense relationships, small local icons, and little tolerance for errors in nodes, arrows, or spacing. Image2PPT is designed for that harder reconstruction problem:

- 🏢 **Complex business slides**: Reconstruct dense timelines, layered processes, cards, icons, and compound arrows while keeping the layout and objects editable.
- 🔬 **Complex scientific flowcharts**: Rebuild knowledge graphs and scientific frameworks node by node and relation by relation, preserving circles, connectors, arrows, and local structures.
- ✏️ **Object-level editability**: Keep text, shapes, nodes, connectors, and arrows independently selectable instead of using a full-slide screenshot as a pseudo-editable background.
- ✅ **Two quality advantages**: In the like-for-like examples shown below, Image2PPT delivers the best clarity and the highest detail fidelity.

The first row below shows a complex business slide and the second a complex scientific figure; together, the two source/result pairs form a 2×2 comparison. Selection handles in converted screenshots demonstrate editable objects and do not appear in slide-show mode.

<table>
  <tr>
    <td align="center" width="50%"><strong>Business PPT · Source</strong><br><img src="assets/readme/business-source.png" alt="Business PPT source" width="100%"></td>
    <td align="center" width="50%"><strong>Business PPT · Converted</strong><br><img src="assets/readme/business-converted.png" alt="Editable business PPT result" width="100%"></td>
  </tr>
  <tr>
    <td align="center" width="50%"><strong>Academic figure · Source</strong><br><img src="assets/readme/scientific-source.png" alt="Academic figure source" width="100%"></td>
    <td align="center" width="50%"><strong>Academic figure · Converted</strong><br><img src="assets/readme/scientific-converted.png" alt="Editable academic figure result" width="100%"></td>
  </tr>
</table>

### 🔎 Case 1: Clarity

The figure below enlarges the same complex local region across four outputs. **Image2PPT is in the bottom-left**, while the other positions show other Image-to-PPT approaches. In this example, Image2PPT preserves icon contours, text edges, and thin lines most clearly, delivering the best overall clarity.

<p align="center"><img src="assets/readme/clarity-comparison.png" alt="Business PPT clarity comparison" width="100%"></p>

### 🧬 Case 2: Detail Fidelity

The figure below compares complete reconstructions of a complex scientific flowchart. **Image2PPT is in the bottom-left**, while the other positions show other Image-to-PPT approaches. In this example, Image2PPT most completely preserves knowledge-graph nodes, relation connectors, arrow directions, chart structures, and local layout, delivering the highest detail fidelity.

<p align="center"><img src="assets/readme/detail-comparison.png" alt="Academic figure detail and arrow comparison" width="100%"></p>

## Typical Requests

> Use $image2ppt to restore these slide images in order as an editable PPTX. Keep the text, timeline, and arrows editable.

> Use $image2ppt to reconstruct this scientific framework. Keep knowledge-graph nodes, relations, and ordinary arrows as independent native PowerPoint objects, and deliver only after rendered QA passes.

## What You Need to Provide

- One or more ordered PNG/JPG files, or a scanned PDF or image-only PPT/PPTX.
- Which objects must remain editable, which speaker notes must be preserved, and whether online OCR is allowed.

## Outputs

- An object-level editable `.pptx` that preserves measurable text, shapes, nodes, connectors, and arrows.
- Page and final QA reports; complex local visuals that cannot be rebuilt reliably as native objects remain replaceable assets.

## Installation and Configuration

### 1. Install the Skill

Give the matching instruction below directly to your Agent. Install the complete Skill containing `SKILL.md`, `cli/`, `prompts/`, `references/`, and its runtime resources; copying only `SKILL.md` is not sufficient.

#### Codex

> Fetch the complete Image2PPT Skill from `https://github.com/Paul-Jeo/Image2PPT` and install it at `~/.codex/skills/image2ppt`. With Python 3.10 or later, install the dependencies from its `requirements.txt`, then install any system requirements reported by `doctor`, such as LibreOffice and CJK fonts. Finally, verify the installation with `python ~/.codex/skills/image2ppt/cli/image2ppt/cli.py doctor --json`.

#### Claude Code

> Fetch the complete Image2PPT Skill from `https://github.com/Paul-Jeo/Image2PPT` and install it at `~/.claude/skills/image2ppt`. With Python 3.10 or later, install the dependencies from its `requirements.txt`, then install any system requirements reported by `doctor`, such as LibreOffice and CJK fonts. Finally, verify the installation with `python ~/.claude/skills/image2ppt/cli/image2ppt/cli.py doctor --json`.

### 2. Get and Configure a Baidu PaddleOCR Token

Image2PPT uses one **Baidu AI Studio Access Token** (`PADDLE_OCR_TOKEN`), not a traditional API Key and Secret Key (AK/SK) pair.

1. Sign in to or register with [Baidu AI Studio](https://aistudio.baidu.com/).
2. Open the [Access Token page](https://aistudio.baidu.com/account/accessToken), then create and copy a token as instructed.
3. Save it in the user-level configuration and rerun `doctor`:

   ```bash
   python /absolute/path/to/image2ppt/cli/image2ppt/cli.py config \
     --paddle-ocr-token "<BAIDU_AI_STUDIO_ACCESS_TOKEN>"
   python /absolute/path/to/image2ppt/cli/image2ppt/cli.py doctor --json
   ```

The token is stored in `~/.image2ppt/config.yaml` by default and can alternatively be supplied through `PADDLE_OCR_TOKEN`. Never commit a real token or place it in an issue, log, or chat. If no token is configured or network OCR fails, Image2PPT falls back to local `builtin-ink` geometry detection, which measures text regions but does not recognize their characters.

## Boundaries

- Reconstructs existing visual pages; it does not author a new presentation from notes, papers, or outlines.
- Complex illustrations, photos, and local effects that cannot be measured reliably may remain independent image assets; not every element is guaranteed to become a native shape.
- Low-resolution sources and missing fonts limit fidelity. Online OCR uploads current task pages to Baidu services, so sensitive material should use offline mode.

## License

Released under the [MIT License](LICENSE).
