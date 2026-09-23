from __future__ import annotations

import csv
import hashlib
import json
import re
import struct
from pathlib import Path
from typing import Any

from .errors import GraphicsError
from .fonts import require_font
from .models import BrandTokens, GraphicJob, RasterAsset
from .qa import inspect_png


SCHEMA_VERSION = "graphics.job.v1"
TEMPLATES = {"quote-card", "product-card", "announcement"}
VARIANTS = {"square": (1080, 1080), "portrait": (1080, 1350), "story": (1080, 1920)}
MAX_SPEC_BYTES = 2 * 1024 * 1024
MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_ASSET_BYTES = 10 * 1024 * 1024
MAX_ASSETS = 100
MAX_TOTAL_ASSET_BYTES = 50 * 1024 * 1024
MAX_RECORDS = 100
MAX_OUTPUTS = 180
MAX_TEXT_CHARS = 4000
MAX_CANVAS_DIMENSION = 4096
_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_TEXT_FIELDS = {
    "quote-card": {"quote", "author"},
    "product-card": {"title", "description", "price", "image_asset"},
    "announcement": {"headline", "body", "cta"},
}
_REQUIRED_FIELDS = {
    "quote-card": {"quote"},
    "product-card": {"title", "image_asset"},
    "announcement": {"headline"},
}
_COLOR_KEYS = {"primary", "accent", "background", "foreground", "surface"}


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _resolve_local(base: Path, raw_path: Any, label: str, *, must_exist: bool = True) -> Path:
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise GraphicsError(f"{label} path must be a non-empty string")
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise GraphicsError(f"{label} path must be relative to the job file")
    try:
        resolved = (base / candidate).resolve(strict=must_exist)
    except OSError as exc:
        raise GraphicsError(f"{label} path does not exist or cannot be accessed") from exc
    if not _inside(resolved, base.resolve()):
        raise GraphicsError(f"{label} path escapes the job directory")
    return resolved


def _validate_png(data: bytes, label: str) -> tuple[str, int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "", 0, 0
    if len(data) < 33 or data[12:16] != b"IHDR":
        raise GraphicsError(f"{label} is not a valid PNG")
    width, height = struct.unpack(">II", data[16:24])
    return "image/png", width, height


def _validate_jpeg(data: bytes) -> tuple[str, int, int]:
    if not data.startswith(b"\xff\xd8"):
        return "", 0, 0
    index = 2
    while index + 4 <= len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        while index < len(data) and data[index] == 0xFF:
            index += 1
        if index >= len(data):
            break
        marker = data[index]
        index += 1
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(data):
            break
        size = int.from_bytes(data[index : index + 2], "big")
        if size < 2 or index + size > len(data):
            break
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            if size < 7:
                break
            height, width = struct.unpack(">HH", data[index + 3 : index + 7])
            return "image/jpeg", width, height
        index += size
    raise GraphicsError("local JPEG asset has invalid dimensions or truncated headers")


def _load_asset(asset_id: str, relative_path: Any, asset_root: Path) -> RasterAsset:
    if not _SLUG.fullmatch(asset_id):
        raise GraphicsError(f"invalid asset id: {asset_id}")
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise GraphicsError(f"asset path must be a non-empty string: {asset_id}")
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise GraphicsError(f"asset path must be relative: {asset_id}")
    try:
        path = (asset_root / candidate).resolve(strict=True)
    except OSError as exc:
        raise GraphicsError(f"local asset is missing: {asset_id}") from exc
    if not _inside(path, asset_root.resolve()):
        raise GraphicsError(f"asset path escapes assets_root: {asset_id}")
    if not path.is_file():
        raise GraphicsError(f"local asset is not a file: {asset_id}")
    if path.suffix.casefold() == ".svg":
        raise GraphicsError("SVG assets are rejected in V1A; use a local PNG or JPEG")
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise GraphicsError(f"local asset cannot be read: {asset_id}") from exc
    if size <= 0 or size > MAX_ASSET_BYTES:
        raise GraphicsError(f"asset size is outside the 1..{MAX_ASSET_BYTES} byte limit: {asset_id}")
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise GraphicsError(f"local asset cannot be read: {asset_id}") from exc
    mime_type, width, height = _validate_png(data, asset_id)
    if mime_type:
        inspect_png(path, width, height)
    if not mime_type:
        mime_type, width, height = _validate_jpeg(data)
    if not mime_type or width <= 0 or height <= 0:
        raise GraphicsError(f"asset is not a supported PNG or JPEG: {asset_id}")
    if width > MAX_CANVAS_DIMENSION * 2 or height > MAX_CANVAS_DIMENSION * 2:
        raise GraphicsError(f"asset dimensions exceed the local processing limit: {asset_id}")
    return RasterAsset(
        asset_id=asset_id,
        path=path,
        mime_type=mime_type,
        sha256=hashlib.sha256(data).hexdigest(),
        data=data,
        width=width,
        height=height,
    )


def _clean_record(raw: Any, template: str, index: int) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise GraphicsError(f"record {index} must be an object")
    if any(not isinstance(key, str) for key in raw):
        raise GraphicsError(f"record {index} has an invalid column name")
    allowed = {"id", *_TEXT_FIELDS[template]}
    unexpected = sorted(set(raw) - allowed)
    if unexpected:
        raise GraphicsError(f"record {index} has unsupported fields: {', '.join(unexpected)}")
    record_id = raw.get("id")
    if not isinstance(record_id, str) or not _SLUG.fullmatch(record_id):
        raise GraphicsError(f"record {index} id must be a lowercase slug")
    record: dict[str, str] = {"id": record_id}
    for field in _TEXT_FIELDS[template]:
        value = raw.get(field, "")
        if not isinstance(value, str):
            raise GraphicsError(f"record {record_id} field {field} must be text")
        value = value.replace("\r\n", "\n").replace("\r", "\n")
        if len(value) > MAX_TEXT_CHARS:
            raise GraphicsError(f"record {record_id} field {field} exceeds the text limit")
        if any(ord(char) < 32 and char not in "\n\t" for char in value):
            raise GraphicsError(f"record {record_id} field {field} contains a control character")
        record[field] = value
    missing = [field for field in _REQUIRED_FIELDS[template] if not record.get(field)]
    if missing:
        raise GraphicsError(f"record {record_id} is missing required field(s): {', '.join(sorted(missing))}")
    return record


def _read_records(raw: Any, base: Path, template: str) -> list[dict[str, Any]]:
    if isinstance(raw, list):
        return raw
    if not isinstance(raw, dict) or set(raw) != {"format", "path"}:
        raise GraphicsError("records_source must contain only format and path")
    fmt = raw.get("format")
    if not isinstance(fmt, str) or fmt not in {"csv", "json"}:
        raise GraphicsError("records_source.format must be csv or json")
    path = _resolve_local(base, raw.get("path"), "records_source")
    try:
        source_size = path.stat().st_size if path.is_file() else 0
    except OSError as exc:
        raise GraphicsError("records_source cannot be accessed") from exc
    if not path.is_file() or source_size > MAX_SOURCE_BYTES:
        raise GraphicsError("records_source must be a file no larger than 10 MiB")
    try:
        if fmt == "csv":
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.DictReader(stream)
                headers = reader.fieldnames
                if not headers or any(not name for name in headers) or len(headers) != len(set(headers)):
                    raise GraphicsError("CSV records_source requires unique, non-empty column names")
                return list(reader)
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError, csv.Error) as exc:
        raise GraphicsError("records_source could not be decoded") from exc
    if isinstance(payload, dict) and set(payload) == {"records"}:
        payload = payload["records"]
    if not isinstance(payload, list):
        raise GraphicsError("JSON records_source must be a list or an object with a records list")
    return payload


def load_job(spec: str | Path | GraphicJob) -> GraphicJob:
    if isinstance(spec, GraphicJob):
        return spec
    try:
        spec_path = Path(spec).expanduser().resolve(strict=True)
    except OSError as exc:
        raise GraphicsError("job specification file does not exist or cannot be accessed") from exc
    try:
        spec_size = spec_path.stat().st_size if spec_path.is_file() else 0
    except OSError as exc:
        raise GraphicsError("job specification file cannot be accessed") from exc
    if not spec_path.is_file() or spec_size > MAX_SPEC_BYTES:
        raise GraphicsError("job specification must be a JSON file no larger than 2 MiB")
    try:
        payload = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GraphicsError("job specification could not be decoded as JSON") from exc
    if not isinstance(payload, dict):
        raise GraphicsError("job specification must be a JSON object")
    allowed = {"schema_version", "job_id", "template", "brand", "variants", "records", "records_source", "assets_root", "assets"}
    unexpected = sorted(set(payload) - allowed)
    if unexpected:
        raise GraphicsError(f"job specification has unsupported fields: {', '.join(unexpected)}")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise GraphicsError(f"schema_version must be {SCHEMA_VERSION}")
    job_id = payload.get("job_id")
    if not isinstance(job_id, str) or not _SLUG.fullmatch(job_id):
        raise GraphicsError("job_id must be a lowercase slug")
    template = payload.get("template")
    if not isinstance(template, str) or template not in TEMPLATES:
        raise GraphicsError(f"template must be one of: {', '.join(sorted(TEMPLATES))}")

    brand = payload.get("brand")
    if not isinstance(brand, dict) or set(brand) - {"colors", "font_family"}:
        raise GraphicsError("brand must contain colors and font_family")
    colors = brand.get("colors")
    if not isinstance(colors, dict) or set(colors) - _COLOR_KEYS or not {"primary", "accent", "background", "foreground"}.issubset(colors):
        raise GraphicsError("brand.colors requires primary, accent, background, and foreground tokens")
    normalized_colors = dict(colors)
    normalized_colors.setdefault("surface", "#FFFFFF")
    for key, value in normalized_colors.items():
        if not isinstance(value, str) or not _COLOR.fullmatch(value):
            raise GraphicsError(f"brand color {key} must be a six-digit hex color")
    font_family = brand.get("font_family")
    if not isinstance(font_family, str) or not font_family.strip():
        raise GraphicsError("brand.font_family must be a non-empty string")
    font_family = font_family.strip()
    require_font(font_family)
    brand_tokens = BrandTokens(colors=normalized_colors, font_family=font_family)

    variants_raw = payload.get("variants")
    if not isinstance(variants_raw, list) or not variants_raw or len(variants_raw) > 3:
        raise GraphicsError("variants must contain one to three supported sizes")
    if any(not isinstance(variant, str) or variant not in VARIANTS for variant in variants_raw):
        raise GraphicsError(f"variants must be selected from: {', '.join(VARIANTS)}")
    if len(set(variants_raw)) != len(variants_raw):
        raise GraphicsError("variants must not contain duplicates")
    variants = tuple(variants_raw)

    if ("records" in payload) == ("records_source" in payload):
        raise GraphicsError("provide exactly one of records or records_source")
    raw_records = _read_records(payload.get("records", payload.get("records_source")), spec_path.parent, template)
    if not raw_records or len(raw_records) > MAX_RECORDS:
        raise GraphicsError(f"records must contain 1..{MAX_RECORDS} rows")
    if len(raw_records) * len(variants) > MAX_OUTPUTS:
        raise GraphicsError(f"job may create at most {MAX_OUTPUTS} outputs")
    records = tuple(_clean_record(row, template, index + 1) for index, row in enumerate(raw_records))
    ids = [row["id"] for row in records]
    if len(ids) != len(set(ids)):
        raise GraphicsError("record ids must be unique within the job")

    raw_assets = payload.get("assets", {})
    if not isinstance(raw_assets, dict):
        raise GraphicsError("assets must map asset ids to local paths")
    if len(raw_assets) > MAX_ASSETS:
        raise GraphicsError(f"job may reference at most {MAX_ASSETS} raster assets")
    if raw_assets:
        asset_root = _resolve_local(spec_path.parent, payload.get("assets_root", "assets"), "assets_root")
        if not asset_root.is_dir():
            raise GraphicsError("assets_root must be an existing local directory")
    else:
        asset_root = spec_path.parent
    assets = {}
    total_asset_bytes = 0
    for asset_id, path in raw_assets.items():
        asset = _load_asset(asset_id, path, asset_root)
        total_asset_bytes += len(asset.data)
        if total_asset_bytes > MAX_TOTAL_ASSET_BYTES:
            raise GraphicsError(f"total local raster assets exceed the {MAX_TOTAL_ASSET_BYTES} byte limit")
        assets[asset_id] = asset
    if template == "product-card":
        for record in records:
            asset_id = record["image_asset"]
            if asset_id not in assets:
                raise GraphicsError(f"record {record['id']} references a missing local image asset")

    return GraphicJob(
        job_id=job_id,
        template=template,
        brand=brand_tokens,
        variants=variants,
        records=records,
        assets=assets,
        spec_path=spec_path,
    )


def variant_dimensions(name: str) -> tuple[int, int]:
    try:
        width, height = VARIANTS[name]
    except KeyError as exc:
        raise GraphicsError(f"unknown canvas variant: {name}") from exc
    if not (1 <= width <= MAX_CANVAS_DIMENSION and 1 <= height <= MAX_CANVAS_DIMENSION):
        raise GraphicsError("canvas dimensions exceed the safe local rendering limit")
    return width, height
