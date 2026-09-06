#!/usr/bin/env python3
"""Trace local raster assets to SVG and validate the SVG subset we embed.

This module deliberately supports a small, inspectable SVG subset rather than
pretending to validate every feature in the SVG standard.  The accepted
document consists of an ``svg`` root with a finite positive ``viewBox`` and
the drawing elements ``g``, ``path``, ``rect``, ``circle``, ``ellipse``,
``line``, ``polyline``, and ``polygon``.  Geometry may use inline fills,
strokes, opacity, and the SVG affine transforms ``matrix``, ``translate``,
``scale``, ``rotate``, ``skewX``, and ``skewY``.

Text, images, ``use`` references, definitions/gradients/patterns, CSS
stylesheets, ``foreignObject``, scripts, event handlers, and all ``url`` or
external references are intentionally outside this subset.  Validated SVG is
still a movable/replacable SVG picture in PowerPoint (``svg-image``), not a
promise that PowerPoint will expose each path as a native shape.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from deck_run_state import resolve_inside


SVG_NAMESPACE = "http://www.w3.org/2000/svg"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"

SUPPORTED_SVG_ELEMENTS = (
    "svg",
    "g",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
)
GEOMETRY_ELEMENTS = set(SUPPORTED_SVG_ELEMENTS) - {"svg", "g"}
_NUMBER = r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?"
_NUMBER_RE = re.compile(rf"^{_NUMBER}$")
_VIEWBOX_RE = re.compile(rf"^(?:{_NUMBER})(?:[\s,]+{_NUMBER}){{3}}$")
_EXTERNAL_REFERENCE_RE = re.compile(
    r"(?:url\s*\(|https?\s*:|ftp\s*:|file\s*:|data\s*:|//)", re.IGNORECASE
)
_PATH_COMMANDS = set("MmZzLlHhVvCcSsQqTtAa")
_PATH_ALLOWED_RE = re.compile(r"^[MmZzLlHhVvCcSsQqTtAa0-9eE+\-.,\s]*$")


class VectorAssetError(RuntimeError):
    """Base error for local vector asset operations."""


class VectorTraceError(VectorAssetError):
    """Raised when local raster-to-SVG tracing cannot complete."""


class SvgValidationError(ValueError):
    """Raised when an SVG is outside the supported, trusted subset."""


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _namespace(tag: str) -> str:
    return tag[1:].split("}", 1)[0] if tag.startswith("{") else ""


def _attribute_name(attribute: str) -> tuple[str, str]:
    if attribute.startswith("{") and "}" in attribute:
        namespace, local = attribute[1:].split("}", 1)
        return namespace, local
    return "", attribute


def _error(path: Path, message: str) -> SvgValidationError:
    return SvgValidationError(f"Invalid SVG {path}: {message}")


def _parse_finite_number(value: str, *, label: str, path: Path) -> float:
    text = str(value).strip()
    if not _NUMBER_RE.fullmatch(text):
        raise _error(path, f"{label} must be a finite number")
    number = float(text)
    if not math.isfinite(number):
        raise _error(path, f"{label} must be finite")
    return number


def _parse_number_list(value: str, *, label: str, path: Path, minimum: int | None = None) -> list[float]:
    text = str(value).strip()
    if not text:
        raise _error(path, f"{label} is empty")
    tokens = [token for token in re.split(r"[\s,]+", text) if token]
    numbers = [_parse_finite_number(token, label=label, path=path) for token in tokens]
    if minimum is not None and len(numbers) < minimum:
        raise _error(path, f"{label} needs at least {minimum} numbers")
    return numbers


def _parse_view_box(value: str, *, path: Path) -> list[float]:
    text = " ".join(str(value).strip().replace(",", " ").split())
    if not _VIEWBOX_RE.fullmatch(text):
        raise _error(path, "viewBox must contain exactly four finite numbers")
    values = _parse_number_list(text, label="viewBox", path=path, minimum=4)
    if values[2] <= 0 or values[3] <= 0:
        raise _error(path, "viewBox width and height must be positive")
    return values


def _parse_length(value: str, *, label: str, path: Path) -> float:
    text = str(value).strip()
    match = re.fullmatch(rf"({_NUMBER})(?:px)?", text, re.IGNORECASE)
    if not match:
        raise _error(path, f"{label} must be a finite number or px length")
    number = float(match.group(1))
    if not math.isfinite(number) or number <= 0:
        raise _error(path, f"{label} must be positive")
    return number


def _check_external_reference(value: str, *, label: str, path: Path) -> None:
    if _EXTERNAL_REFERENCE_RE.search(str(value)):
        raise _error(path, f"{label} contains an external, URL, data, or url() reference")


def _validate_path_data(value: str, *, path: Path) -> None:
    text = str(value).strip()
    if not text:
        raise _error(path, "path d is empty")
    if not _PATH_ALLOWED_RE.fullmatch(text):
        raise _error(path, "path d contains unsupported characters")
    if not any(character in _PATH_COMMANDS for character in text):
        raise _error(path, "path d contains no drawing command")


def _validate_points(value: str, *, label: str, path: Path, minimum_pairs: int) -> None:
    values = _parse_number_list(value, label=label, path=path, minimum=minimum_pairs * 2)
    if len(values) % 2:
        raise _error(path, f"{label} must contain x,y pairs")


def _validate_common_attributes(element: ET.Element, *, path: Path) -> None:
    local = _local_name(element.tag)
    for attribute, value in element.attrib.items():
        namespace, name = _attribute_name(attribute)
        if namespace not in {"", XLINK_NAMESPACE}:
            raise _error(path, f"unsupported attribute namespace on {local}: {attribute}")
        if name.lower().startswith("on") and len(name) > 2:
            raise _error(path, f"event handler attribute is not allowed: {name}")
        if name.lower() in {"href", "src"}:
            raise _error(path, f"external/resource attribute is not allowed: {name}")
        _check_external_reference(value, label=f"attribute {name}", path=path)


def _validate_geometry(element: ET.Element, *, path: Path) -> bool:
    local = _local_name(element.tag)
    attributes = element.attrib
    if local == "path":
        _validate_path_data(attributes.get("d", ""), path=path)
        return True
    if local == "rect":
        width = _parse_finite_number(attributes.get("width", ""), label="rect width", path=path)
        height = _parse_finite_number(attributes.get("height", ""), label="rect height", path=path)
        if width <= 0 or height <= 0:
            raise _error(path, "rect width and height must be positive")
        for name in ("x", "y", "rx", "ry"):
            if name in attributes:
                value = _parse_finite_number(attributes[name], label=f"rect {name}", path=path)
                if name in {"rx", "ry"} and value < 0:
                    raise _error(path, f"rect {name} must not be negative")
        return True
    if local == "circle":
        radius = _parse_finite_number(attributes.get("r", ""), label="circle r", path=path)
        if radius <= 0:
            raise _error(path, "circle r must be positive")
        for name in ("cx", "cy"):
            if name in attributes:
                _parse_finite_number(attributes[name], label=f"circle {name}", path=path)
        return True
    if local == "ellipse":
        rx = _parse_finite_number(attributes.get("rx", ""), label="ellipse rx", path=path)
        ry = _parse_finite_number(attributes.get("ry", ""), label="ellipse ry", path=path)
        if rx <= 0 or ry <= 0:
            raise _error(path, "ellipse rx and ry must be positive")
        for name in ("cx", "cy"):
            if name in attributes:
                _parse_finite_number(attributes[name], label=f"ellipse {name}", path=path)
        return True
    if local == "line":
        values = [_parse_finite_number(attributes.get(name, ""), label=f"line {name}", path=path) for name in ("x1", "y1", "x2", "y2")]
        return values[0:2] != values[2:4]
    if local in {"polyline", "polygon"}:
        _validate_points(
            attributes.get("points", ""),
            label=f"{local} points",
            path=path,
            minimum_pairs=2 if local == "polyline" else 3,
        )
        return True
    return False


def _read_svg_root(path: Path) -> ET.Element:
    if not path.exists():
        raise _error(path, "file does not exist")
    if not path.is_file():
        raise _error(path, "path is not a file")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _error(path, f"cannot read file: {exc}") from exc
    lowered = raw.lower()
    if b"<!doctype" in lowered or b"<!entity" in lowered:
        raise _error(path, "DOCTYPE and ENTITY declarations are not allowed")
    if b"<?xml-stylesheet" in lowered:
        raise _error(path, "external XML stylesheets are not allowed")
    if b"\x00" in raw:
        raise _error(path, "NUL bytes are not allowed")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise _error(path, f"XML parse failed: {exc}") from exc
    return root


def validate_svg(path: Path) -> dict[str, Any]:
    """Validate one SVG against the trusted local subset.

    ``ValueError`` (specifically :class:`SvgValidationError`) is raised for
    malformed, raster, remote, script-bearing, text-bearing, or otherwise
    unsupported files.  A successful result includes ``valid``/``ok`` for
    callers that use either naming convention, the parsed viewBox, geometry
    count, and the supported element counts.
    """

    svg_path = Path(path).expanduser().resolve()
    root = _read_svg_root(svg_path)
    root_local = _local_name(root.tag)
    root_namespace = _namespace(root.tag)
    if root_local != "svg":
        raise _error(svg_path, "root element must be svg")
    if root_namespace not in {"", SVG_NAMESPACE}:
        raise _error(svg_path, f"unsupported root namespace: {root_namespace}")
    _validate_common_attributes(root, path=svg_path)
    view_box_value = root.attrib.get("viewBox")
    if view_box_value is None:
        raise _error(svg_path, "viewBox is required")
    view_box = _parse_view_box(view_box_value, path=svg_path)
    if "width" in root.attrib:
        _parse_length(root.attrib["width"], label="width", path=svg_path)
    if "height" in root.attrib:
        _parse_length(root.attrib["height"], label="height", path=svg_path)

    counts: Counter[str] = Counter()
    geometry_count = 0
    for element in root.iter():
        local = _local_name(element.tag)
        namespace = _namespace(element.tag)
        if namespace not in {"", SVG_NAMESPACE}:
            raise _error(svg_path, f"unsupported element namespace: {namespace}")
        if element is root:
            if element.text and element.text.strip():
                raise _error(svg_path, "text content is not allowed")
            continue
        if local not in GEOMETRY_ELEMENTS and local != "g":
            if local == "text":
                raise _error(svg_path, "text elements are not allowed; keep text as native PPT text")
            if local == "image":
                raise _error(svg_path, "raster image elements are not allowed in SVG assets")
            if local == "foreignObject":
                raise _error(svg_path, "foreignObject is not allowed")
            if local in {"script", "style"}:
                raise _error(svg_path, f"{local} elements are not allowed")
            raise _error(svg_path, f"unsupported SVG element: {local}")
        _validate_common_attributes(element, path=svg_path)
        if element.text and element.text.strip():
            raise _error(svg_path, "text content is not allowed")
        counts[local] += 1
        if local in GEOMETRY_ELEMENTS and _validate_geometry(element, path=svg_path):
            geometry_count += 1

    for element in root.iter():
        if element.tail and element.tail.strip():
            raise _error(svg_path, "text content is not allowed")
    if geometry_count == 0:
        raise _error(svg_path, "SVG contains no non-empty drawing geometry")
    return {
        "valid": True,
        "ok": True,
        "passed": True,
        "path": str(svg_path),
        "format": "svg",
        "vector": True,
        "viewBox": view_box,
        "geometry_count": geometry_count,
        "elements": dict(counts),
        "editability": "svg-image",
        "supported_elements": list(SUPPORTED_SVG_ELEMENTS),
    }


def parse_box_px(value: str | Iterable[Any]) -> list[float]:
    """Parse an ``x,y,width,height`` source-pixel box."""

    parts = [part.strip() for part in value.split(",")] if isinstance(value, str) else list(value)
    if len(parts) != 4:
        raise VectorTraceError("box must be x,y,width,height")
    try:
        numbers = [float(part) for part in parts]
    except (TypeError, ValueError) as exc:
        raise VectorTraceError("box must contain four finite numbers") from exc
    if not all(math.isfinite(number) for number in numbers):
        raise VectorTraceError("box must contain four finite numbers")
    if numbers[2] <= 0 or numbers[3] <= 0:
        raise VectorTraceError("box width and height must be positive")
    return numbers


def _resolve_page_path(
    value: str | Path,
    page_dir: str | Path | None,
    label: str,
    *,
    confine: bool = True,
) -> Path:
    try:
        if page_dir is None:
            return Path(value).expanduser().resolve()
        if confine:
            return resolve_inside(page_dir, value)
        candidate = Path(value).expanduser()
        if not candidate.is_absolute():
            candidate = Path(page_dir).expanduser() / candidate
        return candidate.resolve()
    except ValueError as exc:
        raise VectorTraceError(f"{label} must stay inside page_dir: {value}") from exc


def _manifest_path(path: Path, page_dir: str | Path | None) -> str:
    resolved = path.resolve()
    if page_dir is not None:
        root = Path(page_dir).expanduser().resolve()
        try:
            return resolved.relative_to(root).as_posix()
        except ValueError:
            # This is retained for an explicitly external source path, but
            # outputs and fragments are always checked by _resolve_page_path.
            return resolved.as_posix()
    return resolved.as_posix()


def _format_view_box_dimension(value: float) -> str:
    return format(value, ".12g")


def _ensure_view_box(svg_path: Path) -> None:
    """Add the VTracer width/height as a viewBox when it omitted one."""

    root = _read_svg_root(svg_path)
    if root.attrib.get("viewBox") is not None:
        return
    width = root.attrib.get("width")
    height = root.attrib.get("height")
    if width is None or height is None:
        raise VectorTraceError("VTracer produced SVG without a usable viewBox or width/height")
    width_value = _parse_length(width, label="traced SVG width", path=svg_path)
    height_value = _parse_length(height, label="traced SVG height", path=svg_path)
    root.attrib["viewBox"] = f"0 0 {_format_view_box_dimension(width_value)} {_format_view_box_dimension(height_value)}"
    namespace = _namespace(root.tag)
    if namespace == SVG_NAMESPACE:
        ET.register_namespace("", SVG_NAMESPACE)
    tree = ET.ElementTree(root)
    try:
        tree.write(svg_path, encoding="utf-8", xml_declaration=True, short_empty_elements=True)
    except OSError as exc:
        raise VectorTraceError(f"Could not normalize traced SVG: {exc}") from exc


def vector_image_fragment(
    *,
    image_id: str,
    image_path: str | Path,
    source_path: str | Path,
    box_px: str | Iterable[Any] | None = None,
    page_dir: str | Path | None = None,
    alt: str | None = None,
    z_index: int = 220,
    validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a page-manifest fragment for one traced SVG image."""

    parsed_validation = validation or validate_svg(Path(image_path))
    parsed_box = parse_box_px(box_px) if box_px is not None else [0.0, 0.0, parsed_validation["viewBox"][2], parsed_validation["viewBox"][3]]
    image_manifest_path = _manifest_path(Path(image_path), page_dir)
    source_manifest_path = _manifest_path(Path(source_path), page_dir)
    provenance: dict[str, Any] = {
        "path": image_manifest_path,
        "source": source_manifest_path,
        "source_type": "vector-traced",
        "editability": "svg-image",
        "provenance_note": (
            "Traced locally from the bounded raster source with VTracer. "
            "The result is a movable/replacable SVG image in PowerPoint, "
            "not native editable PowerPoint paths."
        ),
    }
    if box_px is not None:
        provenance["source_box_px"] = parsed_box
        provenance["source_bbox_px"] = parsed_box
    return {
        "schema_version": 1,
        "type": "vector-traced-image-fragment",
        "images": [
            {
                "id": image_id,
                "path": image_manifest_path,
                "box_px": parsed_box,
                "alt": alt or f"Locally vector-traced image {image_id}",
                "z_index": int(z_index),
                "editability": "svg-image",
            }
        ],
        "asset_provenance": [provenance],
    }


def _load_vtracer():
    try:
        import vtracer  # type: ignore
    except (ImportError, ModuleNotFoundError) as exc:
        raise VectorTraceError(
            "Local SVG tracing requires the optional Python package `vtracer`; "
            "install it in the active environment (for example, `python -m pip install vtracer`)."
        ) from exc
    converter = getattr(vtracer, "convert_image_to_svg_py", None)
    if not callable(converter):
        raise VectorTraceError("Installed `vtracer` package does not expose convert_image_to_svg_py")
    return converter


def _ensure_raster_input(path: Path) -> None:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise VectorTraceError(
            "Raster tracing requires Pillow to inspect the local input image."
        ) from exc
    if not path.exists() or not path.is_file():
        raise VectorTraceError(f"Raster input is not a file: {path}")
    try:
        with Image.open(path) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise VectorTraceError(f"Raster input is unreadable: {path}: {exc}") from exc


def trace_raster_to_svg(
    input_path: str | Path,
    output_path: str | Path,
    *,
    force: bool = False,
    page_dir: str | Path | None = None,
    source_path: str | Path | None = None,
    box_px: str | Iterable[Any] | None = None,
    fragment_path: str | Path | None = None,
    image_id: str | None = None,
    alt: str | None = None,
    z_index: int = 220,
) -> dict[str, Any]:
    """Trace a local raster with VTracer and optionally write its fragment.

    When ``page_dir`` is supplied, output and fragment paths are resolved
    through the same ``resolve_inside`` confinement used by the page runtime.
    The input/source may be an explicitly selected external file when no
    fragment is requested. A page fragment requires its source to be inside
    ``page_dir`` so it never records an unusable absolute dependency.
    """

    input_file = _resolve_page_path(input_path, page_dir, "vector input", confine=False)
    output_file = _resolve_page_path(output_path, page_dir, "vector output")
    if output_file.suffix.lower() != ".svg":
        raise VectorTraceError("vector output must have a .svg suffix")
    source_file = _resolve_page_path(source_path or input_path, page_dir, "vector source", confine=False)
    if not source_file.is_file():
        raise VectorTraceError(f"Vector source is not a file: {source_file}")
    fragment_file = None
    if fragment_path is not None:
        if page_dir is None:
            raise VectorTraceError(
                "Writing a page-manifest fragment requires --page-dir so every referenced path stays page-local"
            )
        fragment_file = _resolve_page_path(fragment_path, page_dir, "vector fragment")
        if fragment_file.suffix.lower() not in {".json", ".fragment"}:
            raise VectorTraceError("vector fragment must have a .json or .fragment suffix")
        page_root = Path(page_dir).expanduser().resolve()
        try:
            source_file.relative_to(page_root)
        except ValueError as exc:
            raise VectorTraceError(
                "Vector fragment source must stay inside page_dir; copy the original page/source into the page first"
            ) from exc
    if output_file.exists() and not force:
        raise VectorTraceError(f"Vector output already exists; pass --force to overwrite: {output_file}")
    if fragment_file is not None and fragment_file.exists() and not force:
        raise VectorTraceError(f"Vector fragment already exists; pass --force to overwrite: {fragment_file}")
    _ensure_raster_input(input_file)
    converter = _load_vtracer()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=f".{output_file.stem}.",
            suffix=".svg",
            dir=output_file.parent,
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
        try:
            converter(str(input_file), str(temporary_path))
        except Exception as exc:  # vtracer reports native errors as varying exception types.
            raise VectorTraceError(f"VTracer failed to trace {input_file}: {exc}") from exc
        _ensure_view_box(temporary_path)
        validate_svg(temporary_path)
        if output_file.exists() and not force:
            raise VectorTraceError(f"Vector output already exists; pass --force to overwrite: {output_file}")
        os.replace(temporary_path, output_file)
        validation = validate_svg(output_file)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink()
            except FileNotFoundError:
                pass
    result: dict[str, Any] = {
        "out": str(output_file),
        "output": str(output_file),
        "input": str(input_file),
        "source": str(source_file),
        "validation": dict(validation),
    }
    if fragment_file is not None:
        fragment = vector_image_fragment(
            image_id=image_id or output_file.stem,
            image_path=output_file,
            source_path=source_file,
            box_px=box_px,
            page_dir=page_dir,
            alt=alt,
            z_index=z_index,
            validation=validation,
        )
        fragment_file.parent.mkdir(parents=True, exist_ok=True)
        fragment_file.write_text(json.dumps(fragment, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result["fragment"] = str(fragment_file)
    return result


# Explicit aliases keep the API discoverable for callers that name the action
# after the input (``trace_raster``) or the resulting image (``trace_image``).
trace_raster = trace_raster_to_svg
trace_image_to_svg = trace_raster_to_svg
trace_to_svg = trace_raster_to_svg


__all__ = [
    "SUPPORTED_SVG_ELEMENTS",
    "SvgValidationError",
    "VectorAssetError",
    "VectorTraceError",
    "parse_box_px",
    "trace_image_to_svg",
    "trace_raster",
    "trace_raster_to_svg",
    "trace_to_svg",
    "validate_svg",
    "vector_image_fragment",
]
