from __future__ import annotations

import json
import struct
import tempfile
import unittest
from pathlib import Path
import zlib

from book_media_platform.graphics.errors import GraphicsError
from book_media_platform.graphics.qa import inspect_png
from book_media_platform.graphics.renderer import EdgeRenderer, find_edge
from book_media_platform.graphics.service import render_batch


class EdgeRendererIntegrationTests(unittest.TestCase):
    def test_headless_edge_waits_for_a_complete_local_preview(self) -> None:
        try:
            renderer = EdgeRenderer(find_edge())
        except GraphicsError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory(prefix="graphics renderer test ") as temp_dir:
            root = Path(temp_dir)
            svg = root / "design.svg"
            png = root / "preview.png"
            svg.write_text(
                '<svg xmlns="http://www.w3.org/2000/svg" width="1080" height="1080" viewBox="0 0 1080 1080">'
                '<rect width="1080" height="1080" fill="#ffffff"/>'
                '<text x="80" y="540" font-family="Arial" font-size="72">Local preview</text></svg>',
                encoding="utf-8",
            )

            renderer.render(svg, png, 1080, 1080)

            self.assertEqual(inspect_png(png, 1080, 1080)[:2], (1080, 1080))

    def test_real_render_and_atomic_commit_work_under_deep_output_root(self) -> None:
        try:
            find_edge()
        except GraphicsError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory(prefix="graphics deep output ") as temp_dir:
            root = Path(temp_dir)
            job = {
                "schema_version": "graphics.job.v1",
                "job_id": "graphics-acceptance-product-card",
                "template": "quote-card",
                "brand": {
                    "colors": {
                        "primary": "#17324D",
                        "accent": "#F2A65A",
                        "background": "#F8F5EF",
                        "foreground": "#14212B",
                        "surface": "#FFFFFF",
                    },
                    "font_family": "Arial",
                },
                "variants": ["story"],
                "records": [{"id": "product-01", "quote": "Long local path acceptance"}],
            }
            spec = root / "job.json"
            spec.write_text(json.dumps(job), encoding="utf-8")
            padding = max(1, 182 - len(str(root.resolve())) - 1)
            output = root / ("o" * padding)

            result = render_batch(spec, output)

            self.assertEqual(result.output_count, 1)
            self.assertTrue(result.manifest_path.is_file())

    def test_real_product_template_embeds_and_renders_local_png_asset(self) -> None:
        try:
            find_edge()
        except GraphicsError as exc:
            self.skipTest(str(exc))
        with tempfile.TemporaryDirectory(prefix="graphics product asset ") as temp_dir:
            root = Path(temp_dir)
            assets = root / "assets"
            assets.mkdir()
            image = assets / "photo.png"

            def chunk(kind: bytes, payload: bytes) -> bytes:
                body = kind + payload
                return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

            image.write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(b"\x00\x40\x90\xe0\xff"))
                + chunk(b"IEND", b"")
            )
            job = {
                "schema_version": "graphics.job.v1",
                "job_id": "product-asset-render",
                "template": "product-card",
                "brand": {
                    "colors": {
                        "primary": "#17324D",
                        "accent": "#F2A65A",
                        "background": "#F8F5EF",
                        "foreground": "#14212B",
                        "surface": "#FFFFFF",
                    },
                    "font_family": "Arial",
                },
                "variants": ["square"],
                "assets_root": "assets",
                "assets": {"photo": "photo.png"},
                "records": [
                    {
                        "id": "product-01",
                        "title": "สินค้าทดลอง",
                        "description": "ภาพนี้มาจากไฟล์ในเครื่อง",
                        "price": "฿1,290",
                        "image_asset": "photo",
                    }
                ],
            }
            spec = root / "product-job.json"
            spec.write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")

            result = render_batch(spec, root / "output")

            preview = result.manifest_path.parent / "product-01" / "square" / "preview.png"
            self.assertEqual(result.output_count, 1)
            self.assertEqual(inspect_png(preview, 1080, 1080)[:2], (1080, 1080))


if __name__ == "__main__":
    unittest.main()
