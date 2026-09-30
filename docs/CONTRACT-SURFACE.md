# Contract surface: book-media-platform

This page documents the CLI, storage and configuration surface that
`book-media-platform` owns or consumes. The machine-readable list is
`interfaces` in [`contract.json`](../contract.json); `scripts/check.py` fails
when an interface listed there is missing from this page.

- Platform: `media` (contract `book-platform.contract.v1`, API `v1`)
- Status: `scaffolded`; source status: `implemented-in-this-repository`
- Current implementation: `book_media_platform/graphics` in this repository
- Depends on: `identity`, `security`, `observability` (not yet wired; the pilot
  is a local CLI with no network or credential use)

## Interfaces

| ID | Kind | Direction | Interface | Contract | Status |
|---|---|---|---|---|---|
| `media.cli.graphics-build` | cli | provides | `python -m book_media_platform.graphics build --job <job.json> --output <dir>` | `graphics.job.v1` | implemented |
| `media.cli.graphics-benchmark` | cli | provides | `python -m book_media_platform.graphics benchmark --output <dir>` | - | implemented |
| `media.object-store.artifact-manifest` | object-store | provides | `<output>/<job_id>/manifest.json` plus `<record_id>/<variant>/design.svg` and `preview.png` | `graphics.artifact-manifest.v1` | implemented |
| `media.config.local-renderer` | config | consumes | `BOOK_MEDIA_EDGE_PATH`, `BOOK_MEDIA_FONT_DIRS` | - | implemented |

## Behaviour notes

- `build` validates a `graphics.job.v1` job (see
  [`graphics-v1a.md`](graphics-v1a.md)) and prints a JSON summary with
  `status` (`accepted` or `replay`), `job_id`, `outputs`, `model_calls` (always
  0), `monetary_cost` (`null`), `manifest` and wall-clock timings. A rejected
  job prints `{"status": "rejected", "error": "..."}` to stderr and exits 2.
- Output commit is atomic per job: artifacts are staged, QA-checked and moved
  into `<output>/<job_id>` only when every output passes. Re-running an
  identical job verifies every artifact hash and returns `replay`; different
  inputs for an existing `job_id` are rejected.
- The manifest records `input_sha256` (job, recipe
  `graphics-template-batch.v1.2`, font file hash, asset hashes and renderer
  version), per-artifact `sha256`, `bytes`, `width` and `height`, and
  `usage.cost_status: "unknown_without_rate_card"`.
- Inputs never leave the job directory: record sources and assets must be
  relative paths, SVG assets are rejected, and PNG/JPEG headers are verified.
- `BOOK_MEDIA_FONT_DIRS` is an optional list of absolute directories (platform
  path separator) searched before the operating-system font folders; relative
  entries are ignored.
- Signed upload, file metadata, object storage and access policy are registry
  capabilities with no implementation yet.

## Migration gates

- content-type validation
- access-control parity
- retention policy

## Out of scope

No production provider integration, credential, database writer or customer
payload lives in this repository.
