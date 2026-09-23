# book-media-platform

`Media` platform boundary for the Book Platform portfolio.

## Scope

This repository owns the `media` capability: signed upload, file metadata,
object storage and image processing. The parent registry has no activated
production implementation. This checkout remains scaffolded for platform
activation; it now contains a local, deterministic Graphics V1A pilot without
provider integration, database writes, credentials or customer payloads.

## Graphics V1A

Template Batch accepts a `graphics.job.v1` JSON job whose records are inline,
loaded from JSON, or loaded from CSV. It writes editable SVG and PNG previews
for quote cards, product cards and announcements in square, portrait and story
sizes. The ordinary path uses local layout rules only (`model_calls=0`). See
[`docs/graphics-v1a.md`](docs/graphics-v1a.md) for the job format, limits and
example.

Run a sample from this repository:

```bash
python -m book_media_platform.graphics build \
  --job examples/graphics/quote-cards-job.json \
  --output .runtime/graphics-output
```

The local renderer requires Microsoft Edge Headless and an installed supported
font. Set `BOOK_MEDIA_EDGE_PATH` only when Edge is installed outside the normal
search paths. The renderer runs without background networking and accepts
only generated SVG with embedded local raster assets.

## Boundary

- Owner: `bookchaowalit-backend`
- Repository: `book-media-platform`
- Target remote: `https://github.com/bookchaowalit-backend/book-media-platform.git` (not created by the bootstrap)
- Contract: `book-platform.contract.v1`
- Status: `scaffolded`
- Data owner: the platform boundary identified in `contract.json`

The platform communicates through versioned API or event contracts. Consumers
must not import another platform's database, migration, or private runtime
module. `solo-empire` remains the control plane and compatibility adapter until
parity and rollback evidence permit a cutover.

## Local verification

Run from this repository:

```bash
bash scripts/check.sh
```

The check validates the contract and product suite. It does not claim
deployment, provider connectivity, data migration, or production readiness.

## Migration gate

Before activating a remote or changing a consumer, add sanitized fixtures for
success, duplicate delivery, timeout and provider failure; prove tenant/privacy
isolation; compare the old and new contract; and rehearse rollback on a
disposable state store. Record the evidence in the parent platform registry.
