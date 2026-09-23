from __future__ import annotations

import base64
import binascii
import struct
import xml.etree.ElementTree as ET
import zlib
from pathlib import Path

from .errors import GraphicsError
from .models import GraphicIR, GraphicJob


SVG_NS = "http://www.w3.org/2000/svg"
_FORBIDDEN_TAGS = {"script", "foreignObject", "iframe", "object", "embed", "animate", "set"}


def validate_svg(svg_path: Path, ir: GraphicIR, job: GraphicJob, record: dict[str, str]) -> None:
    data = svg_path.read_bytes()
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise GraphicsError("generated SVG contains a forbidden document declaration")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise GraphicsError("generated SVG is not well-formed XML") from exc
    if root.tag != f"{{{SVG_NS}}}svg":
        raise GraphicsError("generated SVG has an unexpected root element")
    if root.get("width") != str(ir.canvas.width) or root.get("height") != str(ir.canvas.height):
        raise GraphicsError("generated SVG dimensions do not match the selected variant")
    if root.get("viewBox") != f"0 0 {ir.canvas.width} {ir.canvas.height}":
        raise GraphicsError("generated SVG viewBox does not match its dimensions")
    if root.get("data-overflow-policy") != "auto-fit-or-reject":
        raise GraphicsError("generated SVG is missing its overflow policy")

    found_text: list[str] = []
    for element in root.iter():
        local_name = element.tag.rsplit("}", 1)[-1]
        if local_name in _FORBIDDEN_TAGS:
            raise GraphicsError(f"generated SVG contains a forbidden {local_name} element")
        for name, value in element.attrib.items():
            local_attr = name.rsplit("}", 1)[-1].casefold()
            if local_attr in {"href", "src"} and not value.startswith(("data:image/png;base64,", "data:image/jpeg;base64,")):
                raise GraphicsError("generated SVG contains an external asset reference")
            if local_attr == "href":
                verify_embedded_image(value)
            if local_attr == "font-family" and value != job.brand.font_family:
                raise GraphicsError("generated SVG references an unvalidated font")
        if local_name == "text":
            source_text = element.get("data-source-text")
            if source_text is None:
                raise GraphicsError("generated SVG text has no source-text provenance")
            if "".join(element.itertext()) != source_text.replace("\n", ""):
                raise GraphicsError("generated SVG visible text differs from its source text")
            found_text.append(source_text)
            try:
                x = float(element.get("data-box-x", "nan"))
                y = float(element.get("data-box-y", "nan"))
                width = float(element.get("data-box-width", "nan"))
                height = float(element.get("data-box-height", "nan"))
            except ValueError as exc:
                raise GraphicsError("generated SVG text box is invalid") from exc
            if min(x, y, width, height) < 0 or x + width > ir.canvas.width + 0.01 or y + height > ir.canvas.height + 0.01:
                raise GraphicsError("generated SVG text box exceeds the canvas")
    expected = [record.get(field, "") for field in ("quote", "author", "title", "description", "price", "headline", "body", "cta") if record.get(field)]
    if sorted(found_text) != sorted(expected):
        raise GraphicsError("generated SVG is missing or duplicating source text")


def inspect_png(path: Path, expected_width: int, expected_height: int) -> tuple[int, int, int]:
    data = path.read_bytes()
    if len(data) < 57 or len(data) > 80 * 1024 * 1024 or not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise GraphicsError("preview is missing a valid PNG container")
    index = 8
    width = height = 0
    saw_idat = saw_iend = False
    while index + 12 <= len(data):
        length = struct.unpack(">I", data[index : index + 4])[0]
        kind = data[index + 4 : index + 8]
        end = index + 12 + length
        if end > len(data):
            raise GraphicsError("preview PNG has a truncated chunk")
        body = data[index + 4 : end - 4]
        expected_crc = struct.unpack(">I", data[end - 4 : end])[0]
        if (zlib.crc32(body) & 0xFFFFFFFF) != expected_crc:
            raise GraphicsError("preview PNG has a corrupt chunk checksum")
        if kind == b"IHDR":
            if length != 13:
                raise GraphicsError("preview PNG has an invalid IHDR chunk")
            width, height = struct.unpack(">II", data[index + 8 : index + 16])
        elif kind == b"IDAT":
            saw_idat = True
        elif kind == b"IEND":
            saw_iend = True
            if length != 0 or end != len(data):
                raise GraphicsError("preview PNG has trailing data")
            break
        index = end
    if not saw_idat or not saw_iend:
        raise GraphicsError("preview PNG is incomplete")
    if (width, height) != (expected_width, expected_height):
        raise GraphicsError("preview PNG dimensions do not match its selected variant")
    return width, height, len(data)


def verify_embedded_image(uri: str) -> None:
    try:
        header, encoded = uri.split(",", 1)
        if header not in {"data:image/png;base64", "data:image/jpeg;base64"}:
            raise ValueError
        base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise GraphicsError("generated SVG has an invalid embedded raster asset") from exc
