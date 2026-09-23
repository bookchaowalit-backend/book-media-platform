from __future__ import annotations

import unicodedata
from collections.abc import Mapping

from .errors import GraphicsError
from .inputs import variant_dimensions
from .models import (
    BrandTokens,
    Canvas,
    GraphicIR,
    GraphicJob,
    ImageNode,
    ShapeNode,
    TextNode,
)


def _char_width_factor(char: str) -> float:
    category = unicodedata.category(char)
    if category.startswith("M") or char == "\u200d":
        return 0
    if char.isspace():
        return 0.34
    if unicodedata.east_asian_width(char) in {"W", "F"}:
        return 1.0
    if "\u0e00" <= char <= "\u0e7f":
        return 0.78
    if char.isascii() and char.isupper():
        return 0.67
    if char.isascii() and char in "il.,:;!'|()[]{}":
        return 0.31
    if char.isascii() and char in "MW@%&":
        return 0.88
    if char.isascii():
        return 0.54
    return 0.82


def _clusters(value: str) -> list[str]:
    groups: list[str] = []
    for char in value:
        category = unicodedata.category(char)
        if groups and (category.startswith("M") or char in {"\u200d", "\ufe0f"}):
            groups[-1] += char
        else:
            groups.append(char)
    return groups


def _estimated_width(value: str, font_size: int) -> float:
    return sum(_char_width_factor(char) for char in value) * font_size


def _wrap_paragraph(paragraph: str, width: float, font_size: int) -> list[str]:
    if not paragraph:
        return [""]
    lines: list[str] = []
    current = ""
    for cluster in _clusters(paragraph):
        if cluster.isspace():
            current += cluster
            continue
        candidate = current + cluster
        if current and _estimated_width(candidate, font_size) > width:
            lines.append(current)
            current = cluster
        elif not current and _estimated_width(cluster, font_size) > width:
            raise GraphicsError("a single grapheme is wider than the text box")
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [""]


def fit_text(
    source_text: str,
    *,
    node_id: str,
    x: float,
    y: float,
    width: float,
    height: float,
    color: str,
    anchor: str = "start",
    weight: int = 400,
    max_font_size: int,
    min_font_size: int,
    max_lines: int,
) -> TextNode:
    paragraphs = source_text.split("\n")
    for size in range(max_font_size, min_font_size - 1, -1):
        lines: list[str] = []
        for paragraph in paragraphs:
            lines.extend(_wrap_paragraph(paragraph, width, size))
        line_height = size * 1.23
        if len(lines) <= max_lines and len(lines) * line_height <= height:
            return TextNode(
                node_id=node_id,
                source_text=source_text,
                lines=tuple(lines),
                box_x=x,
                box_y=y,
                box_width=width,
                box_height=height,
                font_size=size,
                line_height=line_height,
                color=color,
                anchor=anchor,
                weight=weight,
            )
    raise GraphicsError(f"text in {node_id} does not fit the template; shorten the copy")


def _shape(node_id: str, x: float, y: float, width: float, height: float, fill: str, radius: float = 0) -> ShapeNode:
    return ShapeNode(node_id, "rect", x, y, width, height, fill, radius)


def _text(
    record: Mapping[str, str], field: str, *, node_id: str, x: float, y: float,
    width: float, height: float, color: str, anchor: str = "start", weight: int = 400,
    max_font_size: int, min_font_size: int, max_lines: int,
) -> TextNode | None:
    source_text = record.get(field, "")
    if not source_text:
        return None
    return fit_text(
        source_text,
        node_id=node_id,
        x=x,
        y=y,
        width=width,
        height=height,
        color=color,
        anchor=anchor,
        weight=weight,
        max_font_size=max_font_size,
        min_font_size=min_font_size,
        max_lines=max_lines,
    )


def compile_graphic(job: GraphicJob, record: Mapping[str, str], variant: str) -> GraphicIR:
    width, height = variant_dimensions(variant)
    canvas = Canvas(variant, width, height)
    colors = job.brand.colors
    nodes: list[ShapeNode | TextNode | ImageNode] = [
        _shape("canvas-background", 0, 0, width, height, colors["background"])
    ]

    if job.template == "quote-card":
        margin = width * 0.075
        nodes.extend(
            (
                _shape("quote-panel", margin, height * 0.075, width - 2 * margin, height * 0.85, colors["surface"], width * 0.035),
                _shape("quote-accent", margin, height * 0.075, width * 0.018, height * 0.85, colors["accent"], width * 0.009),
                _shape("quote-marker", width * 0.45, height * 0.20, width * 0.10, height * 0.009, colors["primary"], width * 0.005),
            )
        )
        quote = _text(
            record, "quote", node_id="quote-text", x=width * 0.15, y=height * 0.29,
            width=width * 0.70, height=height * 0.38, color=colors["foreground"], anchor="middle",
            weight=600, max_font_size=72, min_font_size=32, max_lines=7,
        )
        if quote:
            nodes.append(quote)
        author = _text(
            record, "author", node_id="quote-author", x=width * 0.18, y=height * 0.73,
            width=width * 0.64, height=height * 0.08, color=colors["primary"], anchor="middle",
            weight=600, max_font_size=32, min_font_size=20, max_lines=2,
        )
        if author:
            nodes.append(author)

    elif job.template == "product-card":
        margin = width * 0.055
        photo_y = height * 0.055
        photo_height = height * 0.55
        image_box = (margin, photo_y, width - 2 * margin, photo_height)
        nodes.extend(
            (
                _shape("product-panel", margin, photo_y, width - 2 * margin, height * 0.89, colors["surface"], width * 0.028),
                _shape("product-image-backdrop", *image_box, colors["primary"], width * 0.022),
                ImageNode("product-image", record["image_asset"], *image_box),
                _shape("product-accent", margin + width * 0.04, height * 0.66, width * 0.12, height * 0.012, colors["accent"], width * 0.006),
            )
        )
        title = _text(
            record, "title", node_id="product-title", x=margin + width * 0.04, y=height * 0.70,
            width=width * 0.80, height=height * 0.10, color=colors["foreground"], weight=700,
            max_font_size=54, min_font_size=28, max_lines=2,
        )
        if title:
            nodes.append(title)
        description = _text(
            record, "description", node_id="product-description", x=margin + width * 0.04, y=height * 0.81,
            width=width * 0.70, height=height * 0.075, color=colors["foreground"],
            max_font_size=28, min_font_size=18, max_lines=2,
        )
        if description:
            nodes.append(description)
        price = _text(
            record, "price", node_id="product-price", x=width * 0.78, y=height * 0.81,
            width=width * 0.16, height=height * 0.075, color=colors["primary"], anchor="end", weight=700,
            max_font_size=30, min_font_size=18, max_lines=2,
        )
        if price:
            nodes.append(price)

    elif job.template == "announcement":
        nodes.extend(
            (
                _shape("announcement-banner", 0, 0, width, height * 0.27, colors["primary"]),
                _shape("announcement-accent", width * 0.08, height * 0.20, width * 0.20, height * 0.012, colors["accent"], width * 0.006),
                _shape("announcement-panel", width * 0.07, height * 0.32, width * 0.86, height * 0.58, colors["surface"], width * 0.028),
            )
        )
        headline = _text(
            record, "headline", node_id="announcement-headline", x=width * 0.10, y=height * 0.075,
            width=width * 0.80, height=height * 0.12, color=colors["surface"], weight=700,
            max_font_size=58, min_font_size=30, max_lines=2,
        )
        if headline:
            nodes.append(headline)
        body = _text(
            record, "body", node_id="announcement-body", x=width * 0.13, y=height * 0.43,
            width=width * 0.74, height=height * 0.30, color=colors["foreground"], anchor="middle",
            max_font_size=42, min_font_size=22, max_lines=8,
        )
        if body:
            nodes.append(body)
        cta = _text(
            record, "cta", node_id="announcement-cta", x=width * 0.16, y=height * 0.79,
            width=width * 0.68, height=height * 0.075, color=colors["primary"], anchor="middle", weight=700,
            max_font_size=32, min_font_size=20, max_lines=2,
        )
        if cta:
            nodes.append(cta)
    else:
        raise GraphicsError(f"unsupported template: {job.template}")

    return GraphicIR(canvas=canvas, template=job.template, brand=job.brand, nodes=tuple(nodes))
