#!/usr/bin/env python3
"""Offline contract, product package and test check for Book Media Platform."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "schema_version",
    "platform_id",
    "repository",
    "status",
    "api_version",
    "data_owner",
    "capabilities",
    "depends_on",
    "current_implementation",
    "migration",
}


def fail(message: str) -> None:
    raise SystemExit(f"FAIL: {message}")


def main() -> int:
    contract_path = ROOT / "contract.json"
    readme_path = ROOT / "README.md"
    if not contract_path.is_file():
        fail("contract.json is missing")
    if not readme_path.is_file():
        fail("README.md is missing")
    if not (ROOT / "scripts" / "check.sh").is_file():
        fail("scripts/check.sh is missing")

    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"contract.json is invalid JSON: {exc}")
    if not isinstance(contract, dict):
        fail("contract.json root must be an object")
    missing = sorted(REQUIRED - set(contract))
    if missing:
        fail(f"contract.json missing keys: {missing}")
    if contract["schema_version"] != "book-platform.contract.v1":
        fail("unsupported schema_version")
    if contract["status"] != "scaffolded":
        fail("scaffold status must remain scaffolded until activation evidence exists")
    for key in ("platform_id", "repository", "api_version", "data_owner"):
        if not isinstance(contract[key], str) or not contract[key].strip():
            fail(f"{key} must be a non-empty string")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", contract["platform_id"]):
        fail("platform_id has an invalid slug")
    if not re.fullmatch(r"book-[a-z0-9][a-z0-9-]{1,62}", contract["repository"]):
        fail("repository has an invalid slug")
    for key in ("capabilities", "depends_on"):
        if not isinstance(contract[key], list) or not all(
            isinstance(item, str) and item.strip() for item in contract[key]
        ):
            fail(f"{key} must be a list of non-empty strings")
    implementation = contract["current_implementation"]
    if not isinstance(implementation, dict):
        fail("current_implementation must be an object")
    implementation_repository = implementation.get("repository")
    source_path = implementation.get("source_path")
    if implementation_repository not in {"solo-empire", "book-media-platform"}:
        fail("current_implementation.repository must identify the control plane or this platform")
    if not isinstance(source_path, str) or not source_path.strip():
        fail("current_implementation.source_path must be a non-empty string")
    if implementation_repository == "book-media-platform" and not (ROOT / source_path).is_dir():
        fail("current_implementation.source_path must identify the local product package")
    migration = contract["migration"]
    if not isinstance(migration, dict):
        fail("migration must be an object")
    for key in ("compatibility_adapter", "shadow_parity", "cutover", "rollback"):
        if not isinstance(migration.get(key), str) or not migration[key].strip():
            fail(f"migration.{key} must be a non-empty string")

    readme = readme_path.read_text(encoding="utf-8")
    for heading in ("## Scope", "## Graphics V1A", "## Boundary", "## Local verification", "## Migration gate"):
        if heading not in readme:
            fail(f"README.md is missing {heading}")
    if "__" in readme or "__" in contract_path.read_text(encoding="utf-8"):
        fail("scaffold placeholder remains")
    if "graphics-template-batch" not in contract["capabilities"]:
        fail("graphics-template-batch capability is missing from the platform contract")
    graphics_package = ROOT / "book_media_platform" / "graphics"
    if not (graphics_package / "service.py").is_file() or not (graphics_package / "cli.py").is_file():
        fail("Graphics V1A package is incomplete")
    print(f"OK: {contract['repository']} ({contract['platform_id']}) local product contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
