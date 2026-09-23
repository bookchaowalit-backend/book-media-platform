# Graphics V1A visual goldens

This reviewed set contains square, portrait, and story PNG previews for all
three templates. Fixtures include Thai text and a local raster product image.

The baseline was rendered with Microsoft Edge `153.0.4234.48` and Arial font
SHA-256 `b3658eadae55e682b5f69eb64c439c1ecc8f196c0bb8d4756d145d13bc86476a`.
The integration test checks dimensions on every Edge installation and compares
exact PNG hashes when both fingerprints match.

After visually reviewing every preview, regenerate intentionally from the
product repository root with:

```powershell
$env:BOOK_MEDIA_GRAPHICS_UPDATE_GOLDENS = '1'
py -3 -m unittest discover -s tests -p test_graphics_renderer.py -v
Remove-Item Env:BOOK_MEDIA_GRAPHICS_UPDATE_GOLDENS
```

Increment the graphics recipe version when changing rendered output, then
review the updated images before committing them.
