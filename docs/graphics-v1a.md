# Graphics V1A — Template Batch

Graphics V1A is a local pilot for producing editable, structured graphics from
validated input. Layout and QA use deterministic rules; it does not call an
LLM or image-generation model.

## Supported products

| Template | Required record fields | Optional fields |
|---|---|---|
| `quote-card` | `quote` | `author` |
| `product-card` | `title`, `image_asset` | `description`, `price` |
| `announcement` | `headline` | `body`, `cta` |

Every template supports `square` (1080×1080), `portrait` (1080×1350), and
`story` (1080×1920). A job may request one to three variants. Text is wrapped
by grapheme clusters and bounded auto-fit; copy that cannot fit within the
template is rejected without creating partial output.

## Job input

The job is a UTF-8 JSON file. Supply either an inline `records` array or
`records_source` with a relative JSON/CSV path. Asset paths are relative to the
job file's `assets_root`; the job cannot read outside that directory. Product
images must be local PNG or JPEG files. V1A rejects SVG assets so that an
input cannot introduce scripts, links or external resources.

```json
{
  "schema_version": "graphics.job.v1",
  "job_id": "thai-quote-set",
  "template": "quote-card",
  "brand": {
    "colors": {
      "primary": "#17324D",
      "accent": "#F2A65A",
      "background": "#F8F5EF",
      "foreground": "#14212B",
      "surface": "#FFFFFF"
    },
    "font_family": "Arial"
  },
  "variants": ["square", "portrait", "story"],
  "records_source": {"format": "csv", "path": "quotes.csv"}
}
```

The supported local font families are `Arial`, `Tahoma`, `Leelawadee UI`, and
`DejaVu Sans`; a family is accepted only when its local font file is present.
Set `BOOK_MEDIA_FONT_DIRS` to absolute directories (platform path separator)
to search additional font folders before the operating-system defaults.
Template layout and text-box dimensions are fixed in the recipe. V1A rejects
unknown dimensions rather than accepting arbitrary canvas sizes.

## Outputs and replay

Each accepted record and variant gets `design.svg` and `preview.png`. A
`manifest.json` records input and artifact SHA-256 hashes, template and renderer
versions, output dimensions, fresh resource measurements, `model_calls: 0`,
and `monetary_cost: null` while there is no rate card. The output directory is
committed atomically only after every artifact passes QA. Re-running an
identical job verifies the hashes and returns `replay`; changing inputs or
recipe/renderer versions under an existing job ID is rejected to protect the
previous result.

Batch caps are 100 records, 180 output variants, 4,000 characters per text
field, 10 MiB per source file, 10 MiB per raster asset, 100 assets and 50 MiB
of total source assets. No input URL is fetched. Raster assets are embedded
into the SVG as data URIs, so the SVG has no external asset references.

## Local verification

```bash
python -m unittest discover -s tests -v
python -m book_media_platform.graphics --help
python -m book_media_platform.graphics benchmark --output .runtime/graphics-v1a-acceptance
```

The synthetic acceptance batch has 10 records across the three templates and
three sizes, for 30 output pairs. It includes replay verification and reports
controller CPU time and wall time separately; browser child CPU is not included.
Currency cost stays unknown without a rate card. The generated `.runtime`
directory is local evidence and must not be committed.

The reviewed visual golden set at `tests/golden/graphics-v1a/` covers all nine
template/variant combinations with Thai copy and a local raster product image.
Its SHA-256 baseline is tied to the recorded Edge version and Arial font hash;
the integration test always checks output dimensions and only compares exact
raster hashes when those renderer fingerprints match. Inspect all nine images
before deliberately refreshing the baseline with
`BOOK_MEDIA_GRAPHICS_UPDATE_GOLDENS=1` for
`test_nine_visual_previews_match_reviewed_golden_images`.

Product-card description and price boxes are separated by a fixed gap in every
variant. A real Edge integration case covers long Thai product copy across all
three sizes.

## Status boundary

This is a local synthetic pilot. It does not expose a hosted API, accept
customer uploads, write to object storage, or satisfy the platform's tenant,
provider, migration, rollback or production activation gates. The parent
platform contract therefore remains `scaffolded`.
