#!/usr/bin/env python3
"""Small, deterministic object routing contract for page manifests.

Routing is based on explicit object properties.  It does not inspect a model
name, provider, or free-form description to decide a source.  ``source_type``
describes where an asset came from; ``editability`` describes what the PPTX
consumer can edit.  The validator calls :func:`manifest_routing_violations`,
so this module does not create a second page lifecycle.
"""

from __future__ import annotations

import hashlib
import math
import re
from pathlib import Path
from typing import Any, Mapping


SOURCE_TYPES = frozenset(
    {
        "native-object",
        "svg-reconstructed",
        "vector-traced",
        "source-extracted",
        "image-edited",
        "latex-rendered-formula",
        "asset-sheet-separated",
        # Historical values remain readable for old manifests.
        "imagegen",
        "user-provided",
        "user-approved-rasterization",
    }
)
NEW_SOURCE_TYPES = frozenset(
    {
        "native-object",
        "svg-reconstructed",
        "vector-traced",
        "source-extracted",
        "image-edited",
    }
)
EDITABILITIES = frozenset({"native-object", "svg-image", "raster-image"})

LEGACY_REPRESENTATION_SOURCE_TYPES = {
    "native": "native-object",
    "asset-sheet-separated": "asset-sheet-separated",
    "imagegen": "imagegen",
    "source-preserving-local-cleanup": "image-edited",
    "latex-rendered-formula": "latex-rendered-formula",
}

# These are explicit values accepted by route_object when source_type is not
# recorded yet.  Free-form descriptions are never consulted for a route.
OBJECT_KIND_ROUTES = {
    "native": "native-object",
    "native-structure": "native-object",
    "text": "native-object",
    "card": "native-object",
    "table": "native-object",
    "shape": "native-object",
    "line": "native-object",
    "ordinary-arrow": "native-object",
    "arrow": "native-object",
    "flat-icon": "svg-reconstructed",
    "vector-traced": "vector-traced",
    "complex-visual": "source-extracted",
    "photo": "source-extracted",
    "texture": "source-extracted",
    "illustration": "source-extracted",
    "chart-fragment": "source-extracted",
    "asset-sheet-separated": "asset-sheet-separated",
}

PROCESSING_METHODS = {
    "native-object-decomposition": "native-object",
    "faithful-svg-reconstruction": "svg-reconstructed",
    "local-vtracer": "vector-traced",
    "bounded-source-extraction": "source-extracted",
    "asset-sheet-separated": "asset-sheet-separated",
    "explicit-local-image-edit": "image-edited",
    "local-latex-render": "latex-rendered-formula",
}

_NEW_EDITABILITY = {
    "native-object": {"native-object"},
    "svg-reconstructed": {"svg-image"},
    "vector-traced": {"svg-image"},
    "source-extracted": {"raster-image", "svg-image"},
    "image-edited": {"raster-image"},
    "latex-rendered-formula": {"raster-image", "svg-image"},
}
_WHOLE_FLAGS = {
    "full_page",
    "full_slide",
    "whole_page",
    "whole_slide",
    "full_card",
    "whole_card",
    "full_table",
    "whole_table",
    "full_chart",
    "whole_chart",
}


class ObjectRoutingError(ValueError):
    """Raised when an explicit object route violates the contract."""


def _box(value: Any) -> list[float] | None:
    if isinstance(value, str):
        values: list[Any] = [part.strip() for part in value.split(",")]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        return None
    if len(values) != 4:
        return None
    try:
        result = [float(item) for item in values]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in result) or result[2] <= 0 or result[3] <= 0:
        return None
    return result


def _size(value: Any) -> tuple[float, float] | None:
    if isinstance(value, Mapping):
        value = [value.get("width_px"), value.get("height_px")]
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        width, height = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) and item > 0 for item in (width, height)):
        return None
    return width, height


def _field(record: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        value = record.get(name)
        if value is not None and value != "":
            return value
    return None


def _asset_path(record: Mapping[str, Any]) -> str | None:
    value = _field(record, "path", "asset_path", "asset", "image", "image_path")
    return str(value).strip() if isinstance(value, str) and value.strip() else None


def _source_box(record: Mapping[str, Any]) -> list[float] | None:
    return _box(_field(record, "source_box_px", "source_bbox_px"))


def _source_size(record: Mapping[str, Any], supplied: Any = None) -> tuple[float, float] | None:
    result = _size(supplied)
    if result:
        return result
    result = _size(record.get("source_size_px"))
    if result:
        return result
    return _size(record.get("source", {}))


def _kind(record: Mapping[str, Any]) -> str | None:
    value = _field(record, "object_kind", "object_type", "kind")
    if not isinstance(value, str):
        return None
    return value.strip().casefold().replace("_", "-")


def _explicit_source_type(record: Mapping[str, Any]) -> str | None:
    value = record.get("source_type")
    if isinstance(value, str) and value.strip():
        return value.strip().casefold()
    representation = record.get("representation")
    if isinstance(representation, str):
        return LEGACY_REPRESENTATION_SOURCE_TYPES.get(representation.strip().casefold())
    return None


def _full_box(box: list[float] | None, size: tuple[float, float] | None) -> bool:
    if box is None or size is None:
        return False
    x, y, width, height = box
    source_width, source_height = size
    return x <= 1 and y <= 1 and width >= source_width * 0.98 and height >= source_height * 0.98


def _whole_visual(record: Mapping[str, Any], source_size: tuple[float, float] | None) -> bool:
    if any(bool(record.get(flag)) for flag in _WHOLE_FLAGS):
        return True
    source_box = _source_box(record)
    if _full_box(source_box, source_size):
        return True
    # A local visual may not silently cover a declared page/card/chart region.
    for key in ("page_box_px", "slide_box_px", "card_box_px", "table_box_px", "chart_box_px", "region_box_px"):
        container = _box(record.get(key))
        if source_box and container and all(abs(a - b) <= 1 for a, b in zip(source_box, container)):
            return True
    return False


def _identity_evidence(record: Mapping[str, Any]) -> bool:
    value = record.get("identity_evidence")
    return isinstance(value, str) and bool(value.strip())


def _contamination_passed(record: Mapping[str, Any]) -> bool:
    check = record.get("contamination_check")
    return (
        isinstance(check, Mapping)
        and check.get("passed") is True
        and isinstance(check.get("observation"), str)
        and bool(check["observation"].strip())
    )


def _default_editability(source_type: str, path: str | None) -> str | None:
    if source_type == "native-object":
        return "native-object"
    if source_type in {"svg-reconstructed", "vector-traced"}:
        return "svg-image"
    if source_type == "source-extracted":
        return "svg-image" if path and path.casefold().endswith(".svg") else "raster-image"
    if source_type in {"asset-sheet-separated", "image-edited", "imagegen", "user-provided", "user-approved-rasterization", "latex-rendered-formula"}:
        return "svg-image" if path and path.casefold().endswith(".svg") else "raster-image"
    return None


def _validate_svg(record: Mapping[str, Any], manifest_base: str | Path | None) -> None:
    path_value = _asset_path(record)
    if path_value and re.match(r"^[a-z][a-z0-9+.-]*://", path_value, re.IGNORECASE):
        raise ObjectRoutingError("asset paths must be local")
    if not path_value or not path_value.casefold().endswith(".svg"):
        if record.get("editability") == "svg-image":
            raise ObjectRoutingError("svg-image requires an SVG asset path")
        return
    if manifest_base is None:
        path = Path(path_value).expanduser()
    else:
        try:
            from deck_run_state import resolve_inside

            path = resolve_inside(manifest_base, path_value)
        except ValueError as exc:
            raise ObjectRoutingError(f"asset path is outside the page directory: {exc}") from exc
    if not path.exists():
        raise ObjectRoutingError(f"asset path does not exist: {path_value}")
    if record.get("editability") == "raster-image":
        raise ObjectRoutingError("raster-image cannot point to an SVG asset")
    try:
        from vector_assets import validate_svg

        validate_svg(path)
    except Exception as exc:  # validate_svg intentionally exposes ValueError subclasses.
        raise ObjectRoutingError(f"SVG validation failed: {exc}") from exc


def _reject_page_source_clone(
    record: Mapping[str, Any],
    *,
    page_source_path: str | Path | None,
    manifest_base: str | Path | None,
) -> None:
    """Reject a renamed/full-page source screenshot used as a local asset."""

    asset_value = _asset_path(record)
    if not asset_value:
        return
    if page_source_path is None:
        if manifest_base is None:
            raise ObjectRoutingError("source-extracted requires a locatable page source for clone checking")
        page_source_path = "source.png"
    try:
        from deck_run_state import resolve_inside

        if manifest_base is None:
            asset_path = Path(asset_value).expanduser().resolve()
            source_path = Path(page_source_path).expanduser().resolve()
        else:
            asset_path = resolve_inside(manifest_base, asset_value)
            source_path = resolve_inside(manifest_base, page_source_path)
    except (OSError, ValueError):
        return
    if not source_path.is_file():
        raise ObjectRoutingError("source-extracted requires the page source for local clone checking")
    if not asset_path.is_file():
        return
    try:
        if hashlib.sha256(asset_path.read_bytes()).digest() == hashlib.sha256(source_path.read_bytes()).digest():
            raise ObjectRoutingError("source-extracted asset is an unchanged copy of page source.png")
        from PIL import Image, ImageChops

        with Image.open(asset_path) as asset_image, Image.open(source_path) as source_image:
            if asset_image.size != source_image.size:
                return
            asset_rgb = asset_image.convert("RGB")
            source_rgb = source_image.convert("RGB")
            try:
                identical_pixels = ImageChops.difference(asset_rgb, source_rgb).getbbox() is None
            finally:
                asset_rgb.close()
                source_rgb.close()
        if identical_pixels:
            raise ObjectRoutingError("source-extracted asset has identical RGB pixels and dimensions to page source.png")
    except ObjectRoutingError:
        raise
    except (OSError, ValueError):
        return


def route_object(
    record: Mapping[str, Any],
    *,
    source_size_px: Any = None,
    manifest_base: str | Path | None = None,
    page_source_path: str | Path | None = None,
) -> dict[str, Any]:
    """Route one explicit object and return ``source_type`` plus editability.

    New manifests should pass ``object_kind`` when source_type is not yet
    recorded.  Once source_type is present it is treated as a fact and is
    checked, not re-inferred from prose.
    """

    if not isinstance(record, Mapping):
        raise ObjectRoutingError("object route must be an object")
    source_type = _explicit_source_type(record)
    object_kind = _kind(record)
    if source_type is None:
        if object_kind is None:
            raise ObjectRoutingError("object_kind or source_type is required")
        source_type = OBJECT_KIND_ROUTES.get(object_kind)
        if source_type is None:
            raise ObjectRoutingError(f"unsupported object_kind: {object_kind}")
    if source_type not in SOURCE_TYPES:
        raise ObjectRoutingError(f"unsupported source_type: {source_type}")

    protected = object_kind in {
        "native",
        "native-structure",
        "text",
        "card",
        "table",
        "shape",
        "line",
        "ordinary-arrow",
        "arrow",
    }
    if record.get("protected") is True:
        protected = True
    if protected and source_type != "native-object":
        raise ObjectRoutingError("protected text, cards, tables, and ordinary arrows must remain native-object")
    if source_type == "native-object" and _asset_path(record):
        raise ObjectRoutingError("native-object must not be represented by an image asset")

    path = _asset_path(record)
    editability = record.get("editability")
    if editability is None:
        editability = _default_editability(source_type, path)
    if editability not in EDITABILITIES:
        raise ObjectRoutingError(f"editability must be one of {sorted(EDITABILITIES)}")
    expected = _NEW_EDITABILITY.get(source_type)
    if expected and editability not in expected:
        raise ObjectRoutingError(f"source_type {source_type!r} requires editability in {sorted(expected)}")
    if record.get("source_type") in NEW_SOURCE_TYPES and record.get("editability") is None:
        raise ObjectRoutingError("new source types must record actual editability separately")

    source_size = _source_size(record, source_size_px)
    source_box = _source_box(record)
    if source_type in {"svg-reconstructed", "vector-traced", "source-extracted", "image-edited", "asset-sheet-separated"} and not path:
        raise ObjectRoutingError(f"{source_type} requires an asset path")
    if source_type in {"svg-reconstructed", "vector-traced", "source-extracted"} and source_box is None:
        raise ObjectRoutingError(f"{source_type} requires source_box_px or source_bbox_px")
    if source_box is not None and source_size is not None:
        x, y, width, height = source_box
        source_width, source_height = source_size
        if x < 0 or y < 0 or x + width > source_width or y + height > source_height:
            raise ObjectRoutingError("source_box_px must stay inside the page source dimensions")
    if source_type == "svg-reconstructed" and not _identity_evidence(record):
        raise ObjectRoutingError("svg-reconstructed requires explicit identity_evidence")
    if source_type in {"svg-reconstructed", "vector-traced", "source-extracted"} and _whole_visual(record, source_size):
        raise ObjectRoutingError(f"{source_type} must not cover a full page, card, table, or chart")
    if source_type == "source-extracted":
        if not _identity_evidence(record):
            raise ObjectRoutingError("source-extracted requires explicit identity_evidence")
        if not _contamination_passed(record):
            raise ObjectRoutingError("source-extracted requires a passed local contamination_check")
    if source_type == "vector-traced":
        source = record.get("source")
        if not isinstance(source, str) or not source.strip():
            raise ObjectRoutingError("vector-traced requires the local raster source path")
        if source.casefold().endswith(".svg"):
            raise ObjectRoutingError("vector-traced source must be a local raster input, not generated SVG")
    if source_type in {"svg-reconstructed", "vector-traced", "source-extracted"}:
        _validate_svg(record, manifest_base)
    if source_type == "source-extracted":
        _reject_page_source_clone(
            record,
            page_source_path=page_source_path,
            manifest_base=manifest_base,
        )

    processing = record.get("processing_method")
    reason = record.get("reason")
    if processing is not None or reason is not None:
        if not isinstance(processing, str) or processing not in PROCESSING_METHODS:
            raise ObjectRoutingError(f"processing_method must be one of {sorted(PROCESSING_METHODS)}")
        if PROCESSING_METHODS[processing] != source_type:
            raise ObjectRoutingError(f"processing_method {processing!r} does not match source_type {source_type!r}")
        if not isinstance(reason, str) or not reason.strip():
            raise ObjectRoutingError("reason is required when processing_method is present")

    return {
        "source_type": source_type,
        "editability": editability,
        **({"processing_method": processing} if processing is not None else {}),
        **({"reason": reason} if reason is not None else {}),
        **({"path": path} if path else {}),
        **({"source_box_px": source_box} if source_box else {}),
    }


def _merge(*records: Mapping[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for record in records:
        if isinstance(record, Mapping):
            merged.update(record)
    return merged


def validate_object_record(
    record: Mapping[str, Any],
    *,
    source_size_px: Any = None,
    manifest_base: str | Path | None = None,
    require_asset_path: bool = False,
    page_source_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Return validator-shaped violations for one merged manifest record."""

    if not isinstance(record, Mapping):
        return [{"reason": "object route must be an object"}]
    has_route = any(record.get(key) is not None for key in ("source_type", "editability", "processing_method", "reason"))
    if not has_route:
        return []
    label = str(record.get("id") or record.get("path") or "object")
    try:
        route_object(
            record,
            source_size_px=source_size_px,
            manifest_base=manifest_base,
            page_source_path=page_source_path,
        )
    except ObjectRoutingError as exc:
        return [{"field": label, "reason": str(exc)}]
    if require_asset_path and _explicit_source_type(record) != "native-object" and not _asset_path(record):
        return [{"field": label, "reason": "routed image requires an asset path"}]
    return []


def manifest_routing_violations(
    manifest: Mapping[str, Any],
    *,
    manifest_base: str | Path | None = None,
) -> list[dict[str, Any]]:
    """Validate inventory/images/provenance while preserving legacy records."""

    if not isinstance(manifest, Mapping):
        return [{"field": "manifest", "reason": "manifest must be an object"}]
    source = manifest.get("source")
    source_size = _size(source)
    page_source_path = (
        source.get("path") if isinstance(source, Mapping) else None
    ) or "source.png"
    provenance = [item for item in manifest.get("asset_provenance", []) if isinstance(item, Mapping)]
    by_path = {
        Path(str(item.get("path"))).as_posix(): item
        for item in provenance
        if item.get("path")
    }
    inventory = [item for item in manifest.get("visual_inventory", []) if isinstance(item, Mapping)]
    inventory_by_path = {
        Path(str(_asset_path(item))).as_posix(): item
        for item in inventory
        if _asset_path(item)
    }
    violations: list[dict[str, Any]] = []

    for index, item in enumerate(manifest.get("visual_inventory", [])):
        if not isinstance(item, Mapping):
            continue
        path_key = Path(_asset_path(item)).as_posix() if _asset_path(item) else None
        merged = _merge(item, by_path.get(path_key))
        for violation in validate_object_record(
            merged,
            source_size_px=source_size,
            manifest_base=manifest_base,
            page_source_path=page_source_path,
            require_asset_path=item.get("kind") == "foreground-asset" or item.get("source_type") is not None,
        ):
            violations.append({"field": f"visual_inventory[{index}]", **violation})
        if path_key and path_key in by_path:
            other = by_path[path_key]
            if item.get("source_type") and other.get("source_type") and item.get("source_type") != other.get("source_type"):
                violations.append({"field": f"visual_inventory[{index}].source_type", "reason": "source_type does not match asset provenance"})
            if item.get("editability") and other.get("editability") and item.get("editability") != other.get("editability"):
                violations.append({"field": f"visual_inventory[{index}].editability", "reason": "editability does not match asset provenance"})

    for index, image in enumerate(manifest.get("images", [])):
        if not isinstance(image, Mapping):
            continue
        path = _asset_path(image)
        path_key = Path(path).as_posix() if path else None
        merged = _merge(image, by_path.get(path_key), inventory_by_path.get(path_key))
        if not any(merged.get(key) is not None for key in ("source_type", "editability", "processing_method", "reason")):
            continue
        if not by_path.get(path_key):
            violations.append({"field": f"images[{index}]", "reason": "routed image requires matching asset_provenance"})
        for violation in validate_object_record(
            merged,
            source_size_px=source_size,
            manifest_base=manifest_base,
            page_source_path=page_source_path,
            require_asset_path=True,
        ):
            violations.append({"field": f"images[{index}]", **violation})

    for index, entry in enumerate(provenance):
        path = _asset_path(entry)
        path_key = Path(path).as_posix() if path else None
        # Provenance is the authority for source identity and extraction
        # evidence.  Do not let a visual-inventory description fill missing
        # provenance fields and thereby weaken the local guard.
        merged = _merge(entry)
        if not any(merged.get(key) is not None for key in ("source_type", "editability", "processing_method", "reason")):
            continue
        source_type = _explicit_source_type(entry)
        if source_type == "native-object":
            violations.append({
                "field": f"asset_provenance[{index}].source_type",
                "reason": "native-object belongs in native manifest objects, not asset_provenance",
            })
        if source_type in {"svg-reconstructed", "vector-traced", "source-extracted", "image-edited"}:
            source = entry.get("source")
            if not isinstance(source, str) or not source.strip():
                violations.append({
                    "field": f"asset_provenance[{index}].source",
                    "reason": f"{source_type} provenance requires the local source path",
                })
        for violation in validate_object_record(
            merged,
            source_size_px=source_size,
            manifest_base=manifest_base,
            page_source_path=page_source_path,
            require_asset_path=True,
        ):
            violations.append({"field": f"asset_provenance[{index}]", **violation})

    return violations


__all__ = [
    "EDITABILITIES",
    "NEW_SOURCE_TYPES",
    "ObjectRoutingError",
    "PROCESSING_METHODS",
    "SOURCE_TYPES",
    "manifest_routing_violations",
    "route_object",
    "validate_object_record",
]
