from __future__ import annotations

import sys
import unittest
from pathlib import Path
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "cli/image2ppt/runtime"))
from build_pptx_from_manifest import preset_geometry_xml


class ArrowMeasurementTests(unittest.TestCase):
    def test_source_head_length_does_not_use_default_half_height(self):
        item = {"box_px": [420, 340, 380, 100], "source_head_length_px": 100, "source_shaft_thickness_px": 50}
        xml = '<root xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">' + preset_geometry_xml("rightArrow", item) + '</root>'
        root = ET.fromstring(xml)
        adjustments = {node.get("name"): node.get("fmla") for node in root.iter() if node.tag.endswith("}gd")}
        self.assertEqual("val 100000", adjustments.get("adj2"))
        self.assertEqual("val 50000", adjustments.get("adj1"))

    def test_measurement_cannot_exceed_source_arrow_bounds(self):
        with self.assertRaises(ValueError):
            preset_geometry_xml("rightArrow", {"box_px": [0, 0, 80, 40], "source_head_length_px": 100})
