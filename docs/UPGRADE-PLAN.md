# Upgrade plan: book-media-platform

## Current state

Score: 7/10 (6.5 after pass 1, 4 originally). Job locks survive long runs
and recover from crashes on any host. Graphics V1A is a well-tested local CLI with atomic,
replayable output; the repository now has a schema-validated contract, a
documented surface, CI, and host-independent contract tests. Signed upload,
file metadata, object storage and access policy are not implemented.

## Backlog

### P0

- Define the first `file-metadata` contract (id, content type, size, sha256,
  owner subject, retention class) before any upload path exists.

### P1

- Detect lock loss: if a holder is suspended for more than 10 minutes its
  lock can be reclaimed; compare the lock file's inode with the held fd
  before committing output and abort instead of racing the new holder.
- Exercise the Windows `_pid_alive` path (`OpenProcess`/`GetExitCodeProcess`)
  in a Windows CI job; it is only verified by review.

- Run the renderer integration tests in a Windows CI job with the reviewed Edge
  build and Arial fingerprint, or record why they stay local-only.
- Add a JSON schema file for `graphics.job.v1` and `graphics.artifact-manifest.v1`
  and validate `examples/graphics/*.json` against it in tests.
- Replace the vendored schema and its pin with a reusable workflow or tagged
  package from `bookchaowalit-backend-core` once one exists (the pin check
  already fails on drift).

### P2

- Content-type validation and retention-policy fixtures for the registry
  migration gates.

## Done in this pass (pass 2)

- P1 done: job lock heartbeat. The holder refreshes the lock mtime every 30 s
  from a daemon thread (via its own fd, so it never touches another run's
  lock) and stops it on release. New locks carry `heartbeat_seconds`; they are
  stale only after 10 minutes without a heartbeat, so renders longer than 1 h
  keep their lock and a crash on another host is recovered in 10 minutes
  instead of 1 h. Legacy locks keep the 1 h age rule.
- 5 new tests in `tests/test_job_lock.py`; `bash scripts/check.sh` 58 tests OK
  (6 renderer tests skipped), ruff clean. Behaviour documented in
  `docs/CONTRACT-SURFACE.md`.
- Schema pin: `schema/book-platform.contract.v1.schema.json.sha256` pins the
  canonical digest; `scripts/check_schema_pin.py` fails on drift (and, with
  `--canonical`, compares with a local backend-core checkout). It runs in
  `scripts/check.sh` and as its own CI step.
- `scripts/check_registry_alignment.py --solo-empire PATH` compares the
  contract with `repository-catalog/registries/platforms.yaml` (local,
  read-only; not in CI). Interface sources that exist in this repository are
  skipped instead of reported as missing solo-empire paths.
- `tests/test_drift_checks.py` covers both checks offline. Verified against
  `solo-empire` `5b43c85` (no drift, no warnings) and
  `bookchaowalit-backend-core/scripts/check_platform_sync.py --require-pin`.

## Done in pass 1

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

## Done in pass 1 (follow-up)

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
