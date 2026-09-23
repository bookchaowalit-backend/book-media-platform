from __future__ import annotations

import json
import struct
import time
import zlib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from .inputs import VARIANTS
from .renderer import EdgeRenderer
from .service import render_batch


def _write_fixture_png(path: Path) -> None:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    raw = zlib.compress(b"\x00\x38\x88\xd8\xff")
    data = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", raw)
        + chunk(b"IEND", b"")
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def _fixture_rows(template: str, count: int, image_key: str | None = None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(count):
        record: dict[str, str] = {"id": f"{template.split('-')[0]}-{index + 1:02d}"}
        if template == "quote-card":
            record.update(
                quote=f"หลักคิดเรื่องที่ {index + 1}: ใช้ระบบที่ตรวจซ้ำได้ แทนงานซ้ำที่เดาผลไม่ได้",
                author=f"ชุดทดสอบ {index + 1}",
            )
        elif template == "product-card":
            record.update(
                title=f"สินค้าทดสอบ รุ่น {index + 1}",
                description="วัสดุคุณภาพ พร้อมข้อมูลสินค้าแบบมีโครงสร้าง",
                price=f"฿{index + 1},290",
                image_asset=image_key or "product-photo",
            )
        else:
            record.update(
                headline=f"ประกาศทดลองลำดับ {index + 1}",
                body="แจ้งข้อมูลสำคัญให้ลูกค้าอ่านง่าย พร้อมขนาดภาพที่เหมาะกับแต่ละช่องทาง",
                cta="ดูรายละเอียดเพิ่มเติม",
            )
        rows.append(record)
    return rows


def run_acceptance_benchmark(output_root: str | Path) -> dict[str, Any]:
    root = Path(output_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    renderer = EdgeRenderer()
    fresh_count = replay_count = rejected = renderer_invocations = 0
    fresh_wall = replay_wall = 0.0
    cpu_start = time.process_time()
    batch_wall_start = time.perf_counter()
    total_bytes = 0
    with TemporaryDirectory(prefix="book-media-graphics-fixtures-") as temp_dir:
        fixture_root = Path(temp_dir)
        image = fixture_root / "assets" / "photo.png"
        _write_fixture_png(image)
        specifications: list[Path] = []
        distribution = (("quote-card", 4), ("product-card", 3), ("announcement", 3))
        for template, count in distribution:
            spec: dict[str, Any] = {
                "schema_version": "graphics.job.v1",
                "job_id": f"graphics-acceptance-{template}",
                "template": template,
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
                "variants": list(VARIANTS),
                "records": _fixture_rows(template, count),
            }
            if template == "product-card":
                spec["assets_root"] = "assets"
                spec["assets"] = {"product-photo": "photo.png"}
            job_dir = fixture_root / template
            job_dir.mkdir(parents=True, exist_ok=True)
            spec_path = job_dir / "job.json"
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
            if template == "product-card":
                # Keep the referenced image inside this job directory for the path boundary.
                (job_dir / "assets").mkdir()
                (job_dir / "assets" / "photo.png").write_bytes(image.read_bytes())
            specifications.append(spec_path)

        for spec_path in specifications:
            first = render_batch(spec_path, root, renderer=renderer)
            fresh_wall += first.fresh_wall_seconds
            if first.status == "accepted":
                fresh_count += first.output_count
                renderer_invocations += first.output_count
            else:
                replay_count += first.output_count
            manifest = json.loads(first.manifest_path.read_text(encoding="utf-8"))
            total_bytes += sum(item["bytes"] for item in manifest["artifacts"])
            replay_start = time.perf_counter()
            second = render_batch(spec_path, root, renderer=renderer)
            replay_wall += time.perf_counter() - replay_start
            replay_count += second.output_count
        rejected = 0
    controller_cpu_seconds = time.process_time() - cpu_start
    accepted_outputs = (fresh_count + replay_count) // 2
    if accepted_outputs != 30:
        raise RuntimeError(f"acceptance batch expected 30 outputs, completed {accepted_outputs}")
    result = {
        "schema_version": "graphics.acceptance-benchmark.v1",
        "expected_outputs": 30,
        "accepted_outputs": accepted_outputs,
        "fresh_outputs": fresh_count,
        "replay_hits": replay_count,
        "rejected_records": rejected,
        "qa_failures": 0,
        "model_calls": 0,
        "monetary_cost": None,
        "cost_status": "unknown_without_rate_card",
        "renderer": {"name": renderer.name, "version": renderer.version},
        "resources": {
            "wall_seconds": round(time.perf_counter() - batch_wall_start, 6),
            "fresh_wall_seconds": round(fresh_wall, 6),
            "replay_wall_seconds": round(replay_wall, 6),
            "controller_cpu_seconds": round(controller_cpu_seconds, 6),
            "renderer_invocations": renderer_invocations,
            "artifact_bytes": total_bytes,
        },
    }
    (root / "acceptance-benchmark.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
