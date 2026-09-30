# Upgrade plan: book-media-platform

## Current state

Score: 6/10 (was 4/10). Graphics V1A is a well-tested local CLI with atomic,
replayable output; the repository now has a schema-validated contract, a
documented surface, CI, and host-independent contract tests. Signed upload,
file metadata, object storage and access policy are not implemented.

## Backlog

### P0

- Stale job lock: a crash leaves `<output>/.locks/<job_id>.lock` behind and
  every later run of that job times out after 15 s. Replace the exclusive-create
  lock with an OS lock (`fcntl.flock` / `msvcrt.locking`) that the kernel
  releases on process exit, with a regression test.
- Define the first `file-metadata` contract (id, content type, size, sha256,
  owner subject, retention class) before any upload path exists.

### P1

- Run the renderer integration tests in a Windows CI job with the reviewed Edge
  build and Arial fingerprint, or record why they stay local-only.
- Add a JSON schema file for `graphics.job.v1` and `graphics.artifact-manifest.v1`
  and validate `examples/graphics/*.json` against it in tests.
- Keep `schema/book-platform.contract.v1.schema.json` identical to
  `bookchaowalit-backend-core/contracts/`.

### P2

- Content-type validation and retention-policy fixtures for the registry
  migration gates.

## Done in this pass

- Fixed: the contract tests required a host-installed Arial font, so 14 of 22
  tests errored on Linux; they now use a stand-in font through the new
  `BOOK_MEDIA_FONT_DIRS` override (absolute directories only).
- Fixed: real-renderer tests errored instead of skipping when Edge was present
  but Arial was not; `BOOK_MEDIA_SKIP_RENDERER_TESTS=1` disables them in CI.
- Font discovery also searches `/usr/share/fonts/dejavu-sans-fonts` and
  `/usr/share/fonts/TTF`.
- Contract: registry-aligned capabilities, dependencies and gates, an
  `interfaces` list, JSON schema validation in `scripts/check.py`,
  `tests/test_contract_check.py`, `.github/workflows/check.yml`, and
  `docs/CONTRACT-SURFACE.md`.
