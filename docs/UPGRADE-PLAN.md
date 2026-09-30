# Upgrade plan: book-media-platform

## Current state

Score: 6.5/10 (6 after pass 1, 4 before). A crashed run no longer blocks later runs of the same job. Graphics V1A is a well-tested local CLI with atomic,
replayable output; the repository now has a schema-validated contract, a
documented surface, CI, and host-independent contract tests. Signed upload,
file metadata, object storage and access policy are not implemented.

## Backlog

### P0

- Define the first `file-metadata` contract (id, content type, size, sha256,
  owner subject, retention class) before any upload path exists.

### P1

- Job lock heartbeat: a run longer than `STALE_LOCK_MAX_AGE_SECONDS` (1 h)
  can have its lock reclaimed. Refresh the lock mtime while rendering, or move
  to an OS lock (`fcntl.flock` / `msvcrt.locking`) released on process exit.
- Exercise the Windows `_pid_alive` path (`OpenProcess`/`GetExitCodeProcess`)
  in a Windows CI job; it is only verified by review.

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

## Done in this pass (pass 2)

- P0 fixed: stale job locks. `_JobLock` now writes `{pid, host, created_at}`
  and, when the lock exists, reclaims it if the pid is gone on this host, it
  is older than 1 h (pid reuse / other hosts), or it is empty/unparseable past
  a 5 s grace; legacy bare-pid locks are understood. Reclaim is an atomic
  rename with a verify-and-restore step so a lock that was replaced by a live
  run in the meantime is not stolen. Windows uses `OpenProcess` instead of
  `os.kill(pid, 0)` (which would terminate the process there).
- Tests: `tests/test_job_lock.py` (8 cases) plus an end-to-end regression in
  `tests/test_graphics.py` (it takes 15 s and fails on the old code; passes in
  well under 1 s now). `bash scripts/check.sh`: 53 tests OK (6 renderer tests
  skipped), ruff clean.
