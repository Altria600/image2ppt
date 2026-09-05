#!/usr/bin/env python3
import argparse
import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from build_pptx_from_manifest import (
    TEXT_ALIGNMENTS,
    TEXT_VERTICAL_ALIGNMENTS,
    fitted_font_size,
    normalize_manifest,
)


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

ALLOWED_SOURCE_TYPES = {
    "asset-sheet-separated",
    "imagegen",
    "latex-rendered-formula",
    "user-provided",
    "user-approved-rasterization",
}
REQUIRED_QUALITY_CHECKS = {
    "font_size_calibrated",
    "visual_inventory_matched",
    "background_strategy_checked",
    "shape_corner_geometry_checked",
}
FOREGROUND_TERMS = {
    "badge",
    "decorative",
    "foreground",
    "hand-drawn",
    "icon",
    "illustration",
    "image block",
    "logo",
    "mark",
    "photo",
    "pictogram",
    "screenshot",
    "semantic",
    "sticker",
    "symbol",
    "trend",
    "visual object",
    "前景",
    "图标",
    "照片",
    "截图",
    "徽章",
    "贴纸",
    "语义",
    "视觉对象",
}
NON_FOREGROUND_TERMS = {
    "background",
    "clean base",
    "formula",
    "latex",
    "native structural",
    "structural shape",
    "背景",
    "公式",
    "结构",
}
ASSET_SHEET_TERMS = {
    "asset-sheet",
    "asset sheet",
    "asset_sheet",
    "image edit",
    "imagegen",
    "separated",
    "source-faithful",
    "source faithful",
    "split",
    "分离",
}
FORBIDDEN_FOREGROUND_FALLBACK_TERMS = {
    "approximate",
    "approximation",
    "approximated",
    "crop",
    "cropped",
    "direct crop",
    "direct source",
    "emoji",
    "fallback",
    "native approximation",
    "source crop",
    "source snippet",
    "text symbol",
    "warning only",
    "warning_only",
    "近似",
    "裁切",
    "裁剪",
    "降级",
}


def read_manifest(path):
    if not path:
        return {}
    return json.loads(Path(path).read_text(encoding="utf-8"))


def compact_text(value):
    if value is None:
        return ""
    if isinstance(value, str):
        return value.lower()
    if isinstance(value, (int, float, bool)):
        return str(value).lower()
    if isinstance(value, dict):
        return " ".join(compact_text(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return " ".join(compact_text(item) for item in value)
    return str(value).lower()


def contains_any(text, terms):
    return any(term in text for term in terms)


def visual_item_path(item):
    for key in ("path", "asset", "asset_path", "image", "image_path", "corresponding_asset"):
        value = item.get(key) if isinstance(item, dict) else None
        if isinstance(value, str) and value.strip():
            return Path(value).as_posix()
    return None


def is_foreground_visual_item(item):
    text = compact_text(item)
    if contains_any(text, NON_FOREGROUND_TERMS):
        return False
    return contains_any(text, FOREGROUND_TERMS)


def foreground_asset_contract_violations(manifest):
    violations = []
    provenance_by_path = {
        Path(entry.get("path", "")).as_posix(): entry
        for entry in manifest.get("asset_provenance", [])
        if entry.get("path")
    }

    for index, item in enumerate(manifest.get("visual_inventory", [])):
        if not isinstance(item, dict):
            continue
        text = compact_text(item)
        field = f"visual_inventory[{index}]"
        if contains_any(text, FORBIDDEN_FOREGROUND_FALLBACK_TERMS):
            violations.append(
                {
                    "field": field,
                    "reason": "foreground visual decisions must not use direct crops, native approximations, emoji/text symbols, warning-only fallbacks, or similar shortcuts",
                }
            )
        if not is_foreground_visual_item(item):
            continue
        if not contains_any(text, ASSET_SHEET_TERMS):
            violations.append(
                {
                    "field": field,
                    "reason": "foreground visual objects must explicitly use source-faithful asset-sheet separation",
                }
            )
        path = visual_item_path(item)
        if path:
            provenance = provenance_by_path.get(path, {})
            source_type = provenance.get("source_type")
            if source_type in {"user-provided", "user-approved-rasterization"}:
                violations.append(
                    {
                        "field": field,
                        "path": path,
                        "reason": "foreground visual objects cannot use user-provided/direct raster provenance; use asset-sheet separation",
                    }
                )

    for index, entry in enumerate(manifest.get("asset_provenance", [])):
        if not isinstance(entry, dict):
            continue
        text = compact_text(entry)
        source_type = entry.get("source_type")
        path = Path(entry.get("path", "")).as_posix()
        field = f"asset_provenance[{index}]"
        if source_type in {"user-provided", "user-approved-rasterization"} and contains_any(
            text, FOREGROUND_TERMS | FORBIDDEN_FOREGROUND_FALLBACK_TERMS
        ):
            violations.append(
                {
                    "field": field,
                    "path": path,
                    "reason": "foreground-like raster provenance cannot be direct user-provided/cropped source material",
                }
            )
        if contains_any(text, FORBIDDEN_FOREGROUND_FALLBACK_TERMS):
            violations.append(
                {
                    "field": field,
                    "path": path,
                    "reason": "asset provenance records a forbidden foreground fallback such as crop, approximation, or warning-only delivery",
                }
            )

    return violations


def is_full_slide_image(item, slide):
    width = float(slide.get("width", 13.333))
    height = float(slide.get("height", 7.5))
    left = float(item.get("left", 0))
    top = float(item.get("top", 0))
    image_width = float(item.get("width", 0))
    image_height = float(item.get("height", 0))
    return (
        abs(left) <= 0.02
        and abs(top) <= 0.02
        and image_width >= width * 0.98
        and image_height >= height * 0.98
    )


def page_contract_violations(manifest):
    violations = []
    slide = manifest.get("slide", {})
    images = manifest.get("images", [])
    text_boxes = manifest.get("text_boxes", [])
    provenance_by_path = {
        Path(entry.get("path", "")).as_posix(): entry
        for entry in manifest.get("asset_provenance", [])
        if entry.get("path")
    }
    for image in images:
        path = Path(image.get("path", "")).as_posix()
        provenance = provenance_by_path.get(path, {})
        source_type = provenance.get("source_type")
        if is_full_slide_image(image, slide) and Path(path).name == "source.png" and text_boxes:
            violations.append(
                {
                    "field": "images",
                    "path": path,
                    "reason": "full-slide source.png background with editable text overlays causes baked-text overlap",
                }
            )
        if (
            is_full_slide_image(image, slide)
            and source_type in {"user-provided", "user-approved-rasterization"}
            and text_boxes
        ):
            violations.append(
                {
                    "field": "asset_provenance",
                    "path": path,
                    "reason": "full-slide raster background cannot be assembled with editable text",
                }
            )

    return violations


def _iter_text_items(manifest, include_shapes=True):
    """Yield text-bearing manifest items with stable report locations."""
    for section in ("text_boxes", "shapes") if include_shapes else ("text_boxes",):
        for index, item in enumerate(manifest.get(section, [])):
            if not isinstance(item, dict):
                continue
            has_text = (
                item.get("text") not in (None, "")
                or item.get("runs")
                or item.get("paragraphs")
            )
            if section == "shapes" and not has_text:
                continue
            if (
                has_text
                or "text_style_id" in item
                or "alignment_group" in item
            ):
                yield f"{section}[{index}]", item


def _number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _item_x(item):
    box = item.get("box_px")
    if isinstance(box, (list, tuple)) and len(box) == 4:
        return _number(box[0])
    return _number(item.get("left"))


def _item_font_values(item, manifest=None):
    default_font = item.get("font", "PingFang SC")
    fonts = [str(default_font).strip().casefold()]
    default_size = item.get("font_size", 18)
    sizes = [_number(default_size)]
    manifest_line_height = (manifest or {}).get("text_line_height", 1.22)
    line_heights = [_number(item.get("line_height", manifest_line_height))]
    runs = item.get("runs") or []
    for paragraph in item.get("paragraphs") or []:
        if isinstance(paragraph, dict):
            runs = [*runs, *(paragraph.get("runs") or [])]
    for run in runs:
        if not isinstance(run, dict):
            continue
        fonts.append(str(run.get("font", default_font)).strip().casefold())
        sizes.append(_number(run.get("font_size", default_size)))
        line_heights.append(_number(run.get("line_height", item.get("line_height", manifest_line_height))))
    return (
        tuple(sorted(set(fonts))),
        tuple(sorted(set(sizes), key=lambda value: (value is None, value))),
        tuple(sorted(set(line_heights), key=lambda value: (value is None, value))),
    )


def _shape_geometry_signature(item):
    box = item.get("box_px")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    width = _number(box[2])
    height = _number(box[3])
    if width is None or height is None:
        return None
    corner_value = item.get("source_corner_radius_px")
    if corner_value is None:
        corner_value = item.get("radius")
    corner = _number(corner_value)
    rotation = _number(item.get("rotation", 0))
    return (
        str(item.get("type", "rect")),
        str(item.get("preset", "")),
        round(width, 4),
        round(height, 4),
        None if corner is None else round(corner, 4),
        0 if rotation is None else round(rotation, 4),
    )


def style_alignment_contract_violations(manifest, normalized_manifest=None):
    """Audit optional typography styles and alignment rails in a manifest.

    The fields are optional so manifests produced before this contract remain
    valid. Once a page opts into a style or alignment group, the checks are
    deterministic and report the offending manifest item instead of changing
    it during build.
    """
    violations = []
    text_items = list(_iter_text_items(manifest))
    policy_value = manifest.get("typography_policy")
    policy = str(policy_value).strip().lower() if policy_value is not None else ""
    governance_used = any(
        item.get("text_style_id") is not None or item.get("alignment_group") is not None
        for _, item in text_items
    ) or any(
        isinstance(shape, dict) and shape.get("alignment_group") is not None
        for shape in manifest.get("shapes", [])
    )
    if policy_value is not None and policy != "governed":
        violations.append(
            {
                "field": "typography_policy",
                "reason": "typography_policy must be 'governed' when present; omit it only for legacy manifests",
            }
        )
    elif governance_used and policy != "governed":
        violations.append(
            {
                "field": "typography_policy",
                "reason": "text_style_id and alignment_group require typography_policy: governed",
            }
        )

    style_seen = {}
    alignment_groups = {}
    for location, item in text_items:
        style_id = item.get("text_style_id")
        if style_id is not None:
            field = f"{location}.text_style_id"
            if not isinstance(style_id, str) or not style_id.strip():
                violations.append({"field": field, "reason": "text_style_id must be a non-empty string"})
            else:
                signature = _item_font_values(item, manifest)
                previous = style_seen.get(style_id)
                if previous and previous["signature"] != signature:
                    violations.append(
                        {
                            "field": field,
                            "reason": (
                                f"text_style_id {style_id!r} changes font, font size, or line height; "
                                f"expected {previous['signature']}, got {signature}"
                            ),
                        }
                    )
                else:
                    style_seen.setdefault(style_id, {"location": location, "signature": signature})

        group = item.get("alignment_group")
        if group is not None:
            field = f"{location}.alignment_group"
            if not isinstance(group, str) or not group.strip():
                violations.append({"field": field, "reason": "alignment_group must be a non-empty string"})
            else:
                role = item.get("role", "default") or "default"
                alignment_groups.setdefault((group, str(role)), []).append((location, item))

    for (group, role), members in alignment_groups.items():
        if len(members) < 2:
            continue
        first_item = members[0][1]
        first_x = _item_x(first_item)
        first_signature = _item_font_values(first_item, manifest)
        for location, item in members[1:]:
            current_x = _item_x(item)
            if first_x is None or current_x is None:
                violations.append(
                    {
                        "field": f"{location}.box_px",
                        "reason": f"alignment_group {group!r} role {role!r} needs a measurable x anchor",
                    }
                )
            elif abs(current_x - first_x) > 1e-6:
                violations.append(
                    {
                        "field": f"{location}.box_px[0]",
                        "reason": (
                            f"alignment_group {group!r} role {role!r} x anchor drifts "
                            f"from {first_x:g} to {current_x:g} source pixels"
                        ),
                    }
                )
            current_signature = _item_font_values(item, manifest)
            if current_signature != first_signature:
                violations.append(
                    {
                        "field": f"{location}.font_size",
                        "reason": (
                            f"alignment_group {group!r} role {role!r} changes font, font size, or line height "
                            f"from {first_signature} to {current_signature}"
                        ),
                    }
                )

    shape_groups = {}
    for index, shape in enumerate(manifest.get("shapes", [])):
        if not isinstance(shape, dict) or shape.get("alignment_group") is None:
            continue
        group = shape.get("alignment_group")
        if not isinstance(group, str) or not group.strip():
            continue
        role = shape.get("role", "default") or "default"
        signature = _shape_geometry_signature(shape)
        if signature is not None:
            shape_groups.setdefault((group, str(role)), []).append((index, _item_x(shape), signature))
    for (group, role), members in shape_groups.items():
        _, expected_x, expected = members[0]
        for index, current_x, signature in members[1:]:
            if expected_x is None or current_x is None:
                violations.append(
                    {
                        "field": f"shapes[{index}].box_px",
                        "reason": f"alignment_group {group!r} role {role!r} needs a measurable x anchor",
                    }
                )
            elif abs(current_x - expected_x) > 1e-6:
                violations.append(
                    {
                        "field": f"shapes[{index}].box_px[0]",
                        "reason": (
                            f"alignment_group {group!r} role {role!r} x anchor drifts "
                            f"from {expected_x:g} to {current_x:g} source pixels"
                        ),
                    }
                )
            if signature != expected:
                violations.append(
                    {
                        "field": f"shapes[{index}].alignment_group",
                        "reason": (
                            f"alignment_group {group!r} role {role!r} requires identical shape geometry; "
                            f"expected {expected}, got {signature}"
                        ),
                    }
                )

    if normalized_manifest is None:
        try:
            normalized_manifest = normalize_manifest(manifest)
        except Exception:
            normalized_manifest = None
    governed_typography = (
        normalized_manifest is not None
        and str(normalized_manifest.get("typography_policy", "")).strip().lower() == "governed"
    )
    if governed_typography:
        for location, item in _iter_text_items(normalized_manifest):
            requested = _number(item.get("font_size", 18))
            if requested is None or "width" not in item or "height" not in item:
                continue
            probe = dict(item)
            probe["fit_text"] = True
            # The validator reports the geometric limit itself; an authored
            # minimum is useful for legacy fitting but must not waive a
            # governed overflow.
            probe["min_font_size"] = 0
            fit_limit = fitted_font_size(probe, normalized_manifest)
            if fit_limit is not None and requested > fit_limit + 1e-6:
                violations.append(
                    {
                        "field": f"{location}.font_size",
                        "reason": (
                            f"authored font size {requested:g}pt exceeds the estimated {fit_limit:g}pt "
                            "box limit; wrap text or adjust the box and size as a group"
                        ),
                    }
                )

    return violations


def quality_contract_violations(manifest, normalized_manifest=None):
    violations = []

    if "visual_inventory" not in manifest:
        violations.append(
            {
                "field": "visual_inventory",
                "reason": "page manifest must record the non-text visual inventory, even when it is empty",
            }
        )
    elif not isinstance(manifest.get("visual_inventory"), list):
        violations.append({"field": "visual_inventory", "reason": "visual_inventory must be a list"})

    background_strategy = manifest.get("background_strategy")
    if not background_strategy:
        violations.append(
            {
                "field": "background_strategy",
                "reason": "page manifest must record how the background was rebuilt or preserved",
            }
        )

    quality_checks = manifest.get("quality_checks")
    if not isinstance(quality_checks, dict):
        violations.append({"field": "quality_checks", "reason": "quality_checks must be an object"})
    else:
        for key in sorted(REQUIRED_QUALITY_CHECKS):
            if quality_checks.get(key) is not True:
                violations.append(
                    {
                        "field": f"quality_checks.{key}",
                        "reason": "required page QA check must be explicitly true",
                    }
                )

    for index, shape in enumerate(manifest.get("shapes", [])):
        is_round_rect = shape.get("type") == "roundRect" or shape.get("preset") == "roundRect"
        if is_round_rect and not shape.get("source_corner_radius_px"):
            violations.append(
                {
                    "field": f"shapes[{index}]",
                    "reason": "roundRect requires source_corner_radius_px; use rect for source straight-corner containers",
                }
            )
        if is_round_rect and shape.get("source_corner_radius_px") and shape.get("box_px"):
            box = shape.get("box_px")
            radius = float(shape.get("source_corner_radius_px") or 0)
            min_dim = max(1.0, min(float(box[2]), float(box[3])))
            if radius > min_dim / 2:
                violations.append(
                    {
                        "field": f"shapes[{index}].source_corner_radius_px",
                        "reason": "roundRect source radius cannot exceed half of the smaller shape dimension",
                    }
                )

    for index, text_box in enumerate(manifest.get("text_boxes", [])):
        align = str(text_box.get("align", "left") or "left").strip().lower()
        if align not in TEXT_ALIGNMENTS:
            violations.append(
                {
                    "field": f"text_boxes[{index}].align",
                    "reason": "text align must be left, center, right, or the equivalent DrawingML token l, ctr, r",
                }
            )
        valign = str(text_box.get("valign", "top") or "top").strip().lower()
        if valign not in TEXT_VERTICAL_ALIGNMENTS:
            violations.append(
                {
                    "field": f"text_boxes[{index}].valign",
                    "reason": "text valign must be top, middle, bottom, or the equivalent DrawingML token t, ctr, b",
                }
            )

    violations.extend(foreground_asset_contract_violations(manifest))
    violations.extend(style_alignment_contract_violations(manifest, normalized_manifest))
    return violations


def pixel_authoring_violations(manifest):
    violations = []
    source = manifest.get("source", {})
    if not source.get("width_px") or not source.get("height_px"):
        violations.append(
            {
                "field": "source.width_px/source.height_px",
                "reason": "page manifest must record the source image pixel size",
            }
        )

    for section in ("text_boxes", "images"):
        for index, item in enumerate(manifest.get(section, [])):
            if "box_px" not in item:
                violations.append(
                    {
                        "field": f"{section}[{index}].box_px",
                        "reason": "positioned text and image objects must use source-image pixel coordinates",
                    }
                )

    for index, item in enumerate(manifest.get("shapes", [])):
        if item.get("type") == "line":
            if "points_px" not in item:
                violations.append(
                    {
                        "field": f"shapes[{index}].points_px",
                        "reason": "line shapes must use source-image pixel endpoints",
                    }
                )
        elif item.get("type") == "bezier":
            if "box_px" not in item:
                violations.append(
                    {
                        "field": f"shapes[{index}].box_px",
                        "reason": "Bezier shapes must use a source-image pixel bounding box",
                    }
                )
            segments = item.get("bezier_px")
            if not isinstance(segments, list) or not segments or any(not isinstance(segment, list) or len(segment) != 8 for segment in segments):
                violations.append(
                    {
                        "field": f"shapes[{index}].bezier_px",
                        "reason": "Bezier shapes require cubic segments [x1,y1,c1x,c1y,c2x,c2y,x2,y2]",
                    }
                )
        elif "box_px" not in item:
            violations.append(
                {
                    "field": f"shapes[{index}].box_px",
                    "reason": "positioned shapes must use source-image pixel coordinates",
                }
            )

    return violations


def normalize_for_validation(manifest):
    violations = pixel_authoring_violations(manifest)
    try:
        return normalize_manifest(manifest), violations
    except Exception as exc:
        violations.append({"field": "manifest", "reason": str(exc)})
        return manifest, violations


def sha256_text(value):
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def flatten_required_text(value):
    """Return exact text strings that should be verified in the PPTX."""
    items = []
    if value is None:
        return items
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, dict):
        if "required_text" in value:
            return flatten_required_text(value.get("required_text"))
        if "items" in value:
            return flatten_required_text(value.get("items"))
        if "texts" in value:
            return flatten_required_text(value.get("texts"))
        if "text" in value:
            return flatten_required_text(value.get("text"))
        return items
    if isinstance(value, (list, tuple, set)):
        for item in value:
            items.extend(flatten_required_text(item))
    return items


def required_texts_from_manifest(manifest):
    required = []
    required.extend(flatten_required_text(manifest.get("required_text", [])))
    required.extend(flatten_required_text(manifest.get("text_inventory", [])))
    return required


def collect_text(xml_bytes):
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//a:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//a:t", NS)).strip()
        if text:
            paragraphs.append(text)
    # Keep readable word boundaries across explicit line/paragraph breaks. This
    # lets required-text checks validate visual multi-line labels such as
    # "Format\nReward" without forcing them into an overflowing single line.
    return " ".join(paragraphs)


def collect_paragraph_text(xml_bytes):
    root = ET.fromstring(xml_bytes)
    paragraphs = []
    for paragraph in root.findall(".//a:p", NS):
        text = "".join(node.text or "" for node in paragraph.findall(".//a:t", NS))
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def collect_notes_texts(z, names):
    notes = {}
    for name in sorted(n for n in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", n)):
        match = re.search(r"notesSlide(\d+)\.xml$", name)
        if not match:
            continue
        notes[int(match.group(1))] = collect_paragraph_text(z.read(name))
    return notes


def validate_deck(args):
    deck_path = Path(args.deck_manifest).resolve()
    deck = read_manifest(deck_path)
    root = Path(deck.get("job_dir", deck_path.parent)).resolve()
    expected_pages = int(deck.get("page_count", len(deck.get("pages", []))))
    notes_manifest = {}
    notes_path = deck.get("notes_manifest")
    if notes_path:
        notes_file = Path(notes_path)
        if not notes_file.is_absolute():
            notes_file = root / notes_file
        if notes_file.exists():
            notes_manifest = read_manifest(notes_file)

    report = {
        "pptx": str(Path(args.pptx).resolve()),
        "deck_manifest": str(deck_path),
        "expected_pages": expected_pages,
        "slides": 0,
        "page_manifests_missing": [],
        "page_validation_missing": [],
        "failed_page_validations": [],
        "page_contract_violations": [],
        "notes_expected": len(notes_manifest.get("notes", [])),
        "notes_found": 0,
        "notes_hash_mismatches": [],
        "missing_parts": [],
        "warnings": [],
        "passed": False,
    }

    for page in deck.get("pages", []):
        manifest_path = Path(page.get("manifest", ""))
        validation_path = Path(page.get("validation", ""))
        if not manifest_path.is_absolute():
            manifest_path = root / manifest_path
        if not validation_path.is_absolute():
            validation_path = root / validation_path
        if not manifest_path.exists():
            report["page_manifests_missing"].append(str(manifest_path))
        else:
            try:
                raw_manifest = read_manifest(manifest_path)
                normalized_manifest, authoring_violations = normalize_for_validation(raw_manifest)
                violations = (
                    authoring_violations
                    + page_contract_violations(normalized_manifest)
                    + quality_contract_violations(raw_manifest, normalized_manifest)
                )
                if violations:
                    report["page_contract_violations"].append(
                        {
                            "page_id": page.get("page_id"),
                            "manifest": str(manifest_path),
                            "violations": violations,
                        }
                    )
            except Exception as exc:
                report["page_contract_violations"].append(
                    {
                        "page_id": page.get("page_id"),
                        "manifest": str(manifest_path),
                        "violations": [{"field": "manifest", "reason": str(exc)}],
                    }
                )
        if not validation_path.exists():
            report["page_validation_missing"].append(str(validation_path))
        else:
            try:
                page_report = read_manifest(validation_path)
                if page_report.get("passed") is False:
                    report["failed_page_validations"].append(str(validation_path))
            except Exception as exc:
                report["failed_page_validations"].append(f"{validation_path}: {exc}")

    try:
        with zipfile.ZipFile(args.pptx) as z:
            names = z.namelist()
            report["slides"] = len([n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n)])
            for part in ("[Content_Types].xml", "_rels/.rels", "ppt/presentation.xml", "ppt/_rels/presentation.xml.rels"):
                if part not in names:
                    report["missing_parts"].append(part)
            notes_texts = collect_notes_texts(z, names)
            report["notes_found"] = len(notes_texts)
            for entry in notes_manifest.get("notes", []):
                page_index = int(entry.get("page_index", 0))
                expected_hash = entry.get("text_sha256", sha256_text(entry.get("text", "")))
                actual = notes_texts.get(page_index)
                if actual is None:
                    report["notes_hash_mismatches"].append({"page_index": page_index, "reason": "missing notes slide"})
                elif sha256_text(actual) != expected_hash:
                    report["notes_hash_mismatches"].append({"page_index": page_index, "reason": "text hash mismatch"})
    except Exception as exc:
        report["warnings"].append(f"Unable to read pptx: {exc}")

    report["passed"] = (
        report["slides"] == expected_pages
        and not report["page_manifests_missing"]
        and not report["page_validation_missing"]
        and not report["failed_page_validations"]
        and not report["page_contract_violations"]
        and not report["missing_parts"]
        and not report["notes_hash_mismatches"]
    )
    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if report["passed"] else 1)


def rel_source_part(rels_name):
    if not rels_name.endswith(".rels"):
        return posixpath.dirname(rels_name)
    directory = posixpath.dirname(rels_name)
    if directory.endswith("/_rels"):
        directory = posixpath.dirname(directory)
    source = posixpath.basename(rels_name)[:-5]
    return posixpath.normpath(posixpath.join(directory, source))


def resolve_target(rels_name, target):
    if not target or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    source = rel_source_part(rels_name)
    return posixpath.normpath(posixpath.join(posixpath.dirname(source), target))


def relationship_targets(z, rels_name, names):
    if rels_name not in names:
        return []
    root = ET.fromstring(z.read(rels_name))
    targets = []
    for rel in root.findall("rel:Relationship", NS):
        mode = rel.attrib.get("TargetMode")
        target = rel.attrib.get("Target")
        resolved = resolve_target(rels_name, target)
        targets.append(
            {
                "id": rel.attrib.get("Id"),
                "type": rel.attrib.get("Type", ""),
                "target": target,
                "resolved": resolved,
                "external": mode == "External",
            }
        )
    return targets


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pptx")
    parser.add_argument("--manifest")
    parser.add_argument("--deck-manifest")
    parser.add_argument("--required-text", action="append", default=[])
    parser.add_argument("--report")
    args = parser.parse_args()

    if args.deck_manifest:
        validate_deck(args)

    raw_manifest = read_manifest(args.manifest)
    manifest, authoring_violations = normalize_for_validation(raw_manifest)
    manifest_base = Path(args.manifest).resolve().parent if args.manifest else Path.cwd()
    required = list(args.required_text)
    required.extend(required_texts_from_manifest(manifest))

    report = {
        "pptx": str(Path(args.pptx).resolve()),
        "zip_ok": False,
        "slides": 0,
        "images": 0,
        "editable_text_shapes": 0,
        "shape_count": 0,
        "all_text": "",
        "required_text": required,
        "missing_required_text": [],
        "missing_parts": [],
        "missing_relationship_targets": [],
        "missing_asset_provenance": [],
        "missing_manifest_images": [],
        "missing_provenance_sources": [],
        "invalid_asset_provenance": [],
        "media_hash_mismatches": [],
        "asset_provenance_checked": 0,
        "manifest_image_count": len(manifest.get("images", [])),
        "media_manifest_mismatch": False,
        "relationship_targets_checked": 0,
        "warnings": [],
        "page_contract_violations": [],
    }

    try:
        with zipfile.ZipFile(args.pptx) as z:
            bad = z.testzip()
            report["zip_ok"] = bad is None
            if bad:
                report["warnings"].append(f"Bad zip member: {bad}")
            names = z.namelist()
            required_parts = [
                "[Content_Types].xml",
                "_rels/.rels",
                "ppt/presentation.xml",
                "ppt/_rels/presentation.xml.rels",
            ]
            for part in required_parts:
                if part not in names:
                    report["missing_parts"].append(part)
            slide_names = sorted(n for n in names if re.match(r"ppt/slides/slide\d+\.xml$", n))
            report["slides"] = len(slide_names)
            report["images"] = len([n for n in names if n.startswith("ppt/media/")])
            report["media_manifest_mismatch"] = report["images"] != report["manifest_image_count"]
            for index, image in enumerate(manifest.get("images", []), start=1):
                image_path = image.get("path")
                if not image_path:
                    continue
                ext = Path(image_path).suffix.lower()
                if ext == ".jpeg":
                    ext = ".jpg"
                media_name = f"ppt/media/image{index}{ext}"
                source_path = Path(image_path)
                if not source_path.is_absolute():
                    source_path = manifest_base / source_path
                if media_name not in names:
                    report["media_hash_mismatches"].append(
                        {"path": image_path, "media": media_name, "reason": "missing media part"}
                    )
                    continue
                if source_path.exists():
                    manifest_hash = file_sha256(source_path)
                    media_hash = hashlib.sha256(z.read(media_name)).hexdigest()
                    if manifest_hash != media_hash:
                        report["media_hash_mismatches"].append(
                            {"path": image_path, "media": media_name, "reason": "hash mismatch"}
                        )
                else:
                    report["missing_manifest_images"].append(str(image_path))
            for slide_name in slide_names:
                rels_name = f"{posixpath.dirname(slide_name)}/_rels/{posixpath.basename(slide_name)}.rels"
                if rels_name not in names:
                    report["missing_parts"].append(rels_name)
            rel_files = [name for name in names if name.endswith(".rels")]
            for rels_name in rel_files:
                for target in relationship_targets(z, rels_name, names):
                    if target["external"] or not target["resolved"]:
                        continue
                    report["relationship_targets_checked"] += 1
                    if target["resolved"] not in names:
                        report["missing_relationship_targets"].append(
                            {
                                "rels": rels_name,
                                "id": target["id"],
                                "target": target["target"],
                                "resolved": target["resolved"],
                            }
                        )
            texts = []
            for slide_name in slide_names:
                xml = z.read(slide_name)
                root = ET.fromstring(xml)
                shapes = root.findall(".//p:sp", NS)
                report["shape_count"] += len(shapes)
                report["editable_text_shapes"] += sum(1 for shape in shapes if shape.findall(".//a:t", NS))
                texts.append(collect_text(xml))
            report["all_text"] = "\n".join(texts)
    except Exception as exc:
        report["warnings"].append(f"Unable to read pptx: {exc}")

    # Required-text validation is about semantic content, not visual line
    # wrapping. PowerPoint stores explicit line breaks as paragraph boundaries,
    # and vertical CJK labels may place one character per paragraph. Compare a
    # whitespace-free form as well so editable multi-line layout does not create
    # false missing-text failures.
    all_text_compact = re.sub(r"\s+", "", report["all_text"])
    for text in required:
        text_compact = re.sub(r"\s+", "", str(text))
        if text and text not in report["all_text"] and text_compact not in all_text_compact:
            report["missing_required_text"].append(text)

    provenance = {}
    for entry in manifest.get("asset_provenance", []):
        path = entry.get("path")
        if path:
            provenance[Path(path).as_posix()] = entry

    for image in manifest.get("images", []):
        image_path = image.get("path")
        if not image_path:
            continue
        key = Path(image_path).as_posix()
        entry = provenance.get(key)
        if not entry:
            report["missing_asset_provenance"].append(key)
            continue
        report["asset_provenance_checked"] += 1
        source_type = entry.get("source_type")
        provenance_note = entry.get("provenance_note")
        if source_type not in ALLOWED_SOURCE_TYPES:
            report["invalid_asset_provenance"].append(
                {"path": key, "field": "source_type", "value": source_type}
            )
        if not provenance_note:
            report["invalid_asset_provenance"].append(
                {"path": key, "field": "provenance_note", "value": provenance_note}
            )
        if source_type == "user-approved-rasterization" and not entry.get("approval_note"):
            report["invalid_asset_provenance"].append(
                {"path": key, "field": "approval_note", "value": entry.get("approval_note")}
            )
        source = entry.get("source")
        if not source:
            report["missing_provenance_sources"].append({"path": key, "source": source})
            continue
        source_path = Path(source)
        if not source_path.is_absolute():
            source_path = manifest_base / source_path
        if not source_path.exists():
            report["missing_provenance_sources"].append({"path": key, "source": str(source)})
    report["page_contract_violations"] = (
        authoring_violations
        + page_contract_violations(manifest)
        + quality_contract_violations(raw_manifest, manifest)
    )

    report["passed"] = (
        report["zip_ok"]
        and report["slides"] >= 1
        and not report["media_manifest_mismatch"]
        and not report["missing_parts"]
        and not report["missing_relationship_targets"]
        and not report["media_hash_mismatches"]
        and not report["missing_required_text"]
        and not report["missing_asset_provenance"]
        and not report["missing_manifest_images"]
        and not report["missing_provenance_sources"]
        and not report["invalid_asset_provenance"]
        and not report["page_contract_violations"]
        and (report["editable_text_shapes"] > 0 or not required)
    )

    output = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(output + "\n", encoding="utf-8")
    print(output)
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
