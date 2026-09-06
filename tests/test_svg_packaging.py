from __future__ import annotations

import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "cli/image2ppt/runtime"))
from build_pptx_from_manifest import write_deck, write_pptx

NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "asvg": "http://schemas.microsoft.com/office/drawing/2016/SVG/main",
}


class SvgPackagingTests(unittest.TestCase):
    def check_picture(self, archive, index):
        slide = ET.fromstring(archive.read(f"ppt/slides/slide{index}.xml"))
        relationships = ET.fromstring(archive.read(f"ppt/slides/_rels/slide{index}.xml.rels"))
        targets = {item.attrib["Id"]: item.attrib["Target"] for item in relationships}
        self.assertEqual(len(relationships), len(targets), "relationship ids must remain unique with notes")
        self.assertEqual(2, len(slide.findall(".//p:pic", NS)), "SVG fallback must not create another visible picture")
        blip = slide.find(".//p:pic/p:blipFill/a:blip", NS)
        svg = blip.find(".//asvg:svgBlip", NS)
        png_target = targets[blip.attrib[f"{{{NS['r']}}}embed"]]
        svg_target = targets[svg.attrib[f"{{{NS['r']}}}embed"]]
        self.assertTrue(png_target.endswith(".png"))
        self.assertTrue(svg_target.endswith(".svg"))
        with Image.open(io.BytesIO(archive.read("ppt/" + png_target.removeprefix("../")))) as png:
            self.assertEqual((37, 99, 235), png.convert("RGB").getpixel((png.width // 2, png.height // 2)))
        self.assertIn(b"<rect", archive.read("ppt/" + svg_target.removeprefix("../")))

    def test_svg_keeps_vector_and_real_png_in_page_and_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            page = Path(tmp) / "中文 素材"
            page.mkdir()
            (page / "icon.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><rect width="100" height="100" fill="#2563eb"/></svg>', encoding="utf-8")
            Image.new("RGB", (10, 10), "white").save(page / "photo.png")
            manifest = {"slide": {"width": 10, "height": 6}, "images": [
                {"path": "icon.svg", "left": 1, "top": 1, "width": 1, "height": 1},
                {"path": "photo.png", "left": 3, "top": 1, "width": 1, "height": 1},
            ]}
            manifest_path = page / "manifest.json"
            single = page / "page.pptx"
            write_pptx(manifest, single, manifest_path)
            with zipfile.ZipFile(single) as archive:
                self.check_picture(archive, 1)
                self.assertIn(b'image/svg+xml', archive.read("[Content_Types].xml"))
                self.assertIn(b'image/png', archive.read("[Content_Types].xml"))
            deck = page / "deck.pptx"
            entry = {"manifest": manifest, "manifest_path": manifest_path}
            write_deck({}, [entry, entry], deck, [{"page_index": 1, "text": "Source note"}])
            with zipfile.ZipFile(deck) as archive:
                self.check_picture(archive, 1)
                self.check_picture(archive, 2)
                self.assertIn(b"Source note", archive.read("ppt/notesSlides/notesSlide1.xml"))
