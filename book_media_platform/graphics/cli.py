from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .benchmark import run_acceptance_benchmark
from .errors import GraphicsError
from .service import render_batch


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="book-media-graphics", description="Local deterministic graphics template batch")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="validate a JSON job and render editable SVG plus PNG previews")
    build.add_argument("--job", required=True, type=Path, help="graphics.job.v1 JSON file")
    build.add_argument("--output", required=True, type=Path, help="local output directory")
    benchmark = subparsers.add_parser("benchmark", help="run the 30-output synthetic acceptance batch")
    benchmark.add_argument("--output", required=True, type=Path, help="local output directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "build":
            result = render_batch(args.job, args.output)
            payload = {
                "status": result.status,
                "job_id": result.job_id,
                "outputs": result.output_count,
                "model_calls": result.model_calls,
                "monetary_cost": result.monetary_cost,
                "manifest": str(result.manifest_path),
                "fresh_wall_seconds": result.fresh_wall_seconds,
                "replay_wall_seconds": result.replay_wall_seconds,
            }
        else:
            payload = run_acceptance_benchmark(args.output)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except GraphicsError as exc:
        print(json.dumps({"status": "rejected", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
