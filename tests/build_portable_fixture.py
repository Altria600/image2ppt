"""Build four offline engineering fixtures for actual PPTX rendering checks.

These are controlled test inputs, not evidence of automatic reconstruction of
real customer slides. Run from the repository with --out inside output/.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from support import base_manifest, build_deck, build_page, write_json


def build(out: Path) -> None:
    if out.exists():
        raise SystemExit(f"Refusing to overwrite an existing fixture run: {out}")
    out.mkdir(parents=True)
    entries = []
    font_path = "/Library/Fonts/NotoSansCJKsc-Regular.otf"
    font = ImageFont.truetype(font_path, 24) if Path(font_path).exists() else ImageFont.load_default()
    titles = ("原生流程结构", "扁平 SVG 图标", "独立光影图片", "密集中文排版")
    for index, title in enumerate(titles, 1):
        page = out / "pages" / f"page_{index:03d}"
        manifest_path = base_manifest(page, {
            "id": "card", "type": "rect", "box_px": [100, 180, 1080, 440],
            "fill": "#F1F5F9", "stroke": "#CBD5E1", "stroke_width": 1, "z_index": 10,
        })
        manifest = json.loads(manifest_path.read_text())
        manifest["text_inventory"] = [title]
        manifest["text_boxes"] = [{
            "id": "title", "text": title, "box_px": [100, 70, 1080, 55],
            "font": "Noto Sans CJK SC", "font_size": 18, "color": "#172B4D", "z_index": 40,
        }]
        region = manifest["image2ppt_region_decomposition"]["regions"][0]
        region["manifest_ids"]["text_boxes"] = ["title"]
        source = Image.new("RGB", (1280, 720), "white")
        draw = ImageDraw.Draw(source)
        draw.rectangle((100, 180, 1180, 620), fill="#F1F5F9", outline="#CBD5E1")
        draw.text((100, 75), title, font=font, fill="#172B4D")
        assets = page / "assets"
        assets.mkdir()
        if index == 1:
            manifest["shapes"].append({
                "id": "arrow", "type": "shape", "preset": "rightArrow", "box_px": [420, 340, 380, 100],
                "source_head_length_px": 100, "source_shaft_thickness_px": 50,
                "fill": "#2563EB", "stroke": "none", "z_index": 20,
            })
            region["manifest_ids"]["shapes"].append("arrow")
            draw.polygon([(420, 365), (700, 365), (700, 340), (800, 390),
                          (700, 440), (700, 415), (420, 415)], fill="#2563EB")
        elif index == 2:
            svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><path d="M30 45V30C30 4 70 4 70 30V45" fill="none" stroke="#2563EB" stroke-width="8"/><rect x="20" y="42" width="60" height="48" rx="4" fill="#2563EB"/><circle cx="50" cy="63" r="5" fill="#ffffff"/></svg>'
            (assets / "lock.svg").write_text(svg, encoding="utf-8")
            # Independent raster reference for the same deliberately simple icon.
            draw.arc((600, 250, 680, 350), 180, 360, fill="#2563EB", width=16)
            draw.line((600, 300, 600, 340), fill="#2563EB", width=16)
            draw.line((680, 300, 680, 340), fill="#2563EB", width=16)
            draw.rounded_rectangle((580, 334, 700, 430), radius=8, fill="#2563EB")
            draw.ellipse((630, 366, 650, 386), fill="white")
            add_asset(manifest, "lock", "assets/lock.svg", [540, 250, 200, 200], "svg-reconstructed", "svg-image")
        elif index == 3:
            sphere = Image.new("RGBA", (180, 180))
            pixels = sphere.load()
            for y in range(180):
                for x in range(180):
                    nx, ny = (x - 90) / 85, (y - 90) / 85
                    radius = nx * nx + ny * ny
                    if radius <= 1:
                        light = max(0.12, min(1, 0.35 - nx * 0.3 - ny * 0.4 + math.sqrt(1 - radius) * 0.55))
                        pixels[x, y] = (int(65 * light), int(145 * light), int(240 * light), 255)
            sphere.save(assets / "sphere.png")
            source.paste(sphere, (550, 280), sphere)
            add_asset(manifest, "sphere", "assets/sphere.png", [550, 280, 180, 180], "source-extracted", "raster-image")
        else:
            for line in range(8):
                text = f"第 {line + 1} 项：文字保持独立可编辑，字体、间距和对齐需要实际渲染复核。"
                item_id = f"body-{line}"
                manifest["text_inventory"].append(text)
                manifest["text_boxes"].append({
                    "id": item_id, "text": text, "box_px": [135, 205 + line * 47, 1010, 38],
                    "font": "Noto Sans CJK SC", "font_size": 18, "color": "#172B4D", "z_index": 40,
                })
                region["manifest_ids"]["text_boxes"].append(item_id)
                draw.text((135, 208 + line * 47), text, font=font, fill="#172B4D")
        source.save(page / "source.png")
        write_json(manifest_path, manifest)
        build_page(page)
        entries.append({"page_id": page.name, "manifest": f"pages/{page.name}/manifest.json"})
    write_json(out / "deck_manifest.json", {"schema_version": 1, "pages": entries, "output": "final/portable-fixture.pptx"})
    build_deck(out / "deck_manifest.json", out / "final/portable-fixture.pptx")
    print(out / "final/portable-fixture.pptx")


def add_asset(manifest, name, path, box, source_type, editability):
    manifest["images"].append({"id": name, "path": path, "box_px": box, "z_index": 30, "editability": editability})
    manifest["visual_inventory"].append({
        "id": name, "kind": "foreground-asset", "representation": source_type,
        "path": path, "description": "Controlled local fixture asset, not a whole layout region.",
        "editability": editability,
    })
    manifest["asset_provenance"].append({
        "path": path, "source_type": source_type, "source": "source.png", "source_box_px": box,
        "editability": editability, "provenance_note": "Independent bounded engineering fixture asset; source identity preserved.",
        "identity_evidence": "The fixture contains this exact local asset at the declared source box; its silhouette, colors and proportions are unchanged.",
        "contamination_check": {"passed": True, "observation": "This controlled icon/sphere asset contains no text, card border, arrows or other foreground objects."},
    })
    manifest["image2ppt_region_decomposition"]["regions"][0]["manifest_ids"]["images"].append(name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    build(parser.parse_args().out.resolve())
