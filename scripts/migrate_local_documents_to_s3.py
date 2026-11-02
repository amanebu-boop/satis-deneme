"""Dry-run-first migration of local template and generated document files to RustFS."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from app import storage


def _target_key(path: Path) -> str:
    name = path.name
    if name.endswith(".source") or name.endswith(".json"):
        return f"templates/{name}"
    if ".output." in name:
        return f"outputs/{name}"
    raise ValueError(f"Unsupported document file: {name}")


def migrate_documents(root: Path, *, apply: bool = False) -> dict:
    if not root.is_dir():
        raise FileNotFoundError(f"Local document directory not found: {root}")
    if not storage.is_s3():
        raise RuntimeError("Set SALES_STORAGE_BACKEND=s3 and configure RustFS before running this migration")
    files = sorted(path for path in root.iterdir() if path.is_file() and (path.name.endswith(".source") or path.name.endswith(".json") or ".output." in path.name))
    report = []
    for path in files:
        data = path.read_bytes()
        key = _target_key(path)
        digest = hashlib.sha256(data).hexdigest()
        if storage.exists(key):
            existing = storage.get_bytes(key)
            if hashlib.sha256(existing).hexdigest() != digest:
                raise RuntimeError(f"Target object differs; refusing overwrite: {key}")
            report.append({"key": key, "bytes": len(data), "sha256": digest, "action": "already-matches"})
            continue
        if apply:
            content_type = "application/json; charset=utf-8" if key.endswith(".json") else "application/octet-stream"
            storage.put_bytes(key, data, content_type)
            copied = storage.get_bytes(key)
            if hashlib.sha256(copied).hexdigest() != digest:
                raise RuntimeError(f"Object checksum verification failed: {key}")
        report.append({"key": key, "bytes": len(data), "sha256": digest, "action": "copied" if apply else "would-copy"})
    return {"mode": "apply" if apply else "dry-run", "files": len(report), "total_bytes": sum(item["bytes"] for item in report), "objects": report}


def main() -> int:
    parser = argparse.ArgumentParser(description="Copy local documents to RustFS; dry-run is the default.")
    parser.add_argument("--source", type=Path, default=Path(os.environ.get("SALES_DOCUMENTS_PATH", "data/documents")))
    parser.add_argument("--apply", action="store_true", help="Upload files; otherwise only list and hash.")
    args = parser.parse_args()
    result = migrate_documents(args.source, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not args.apply:
        print("DRY RUN ONLY: no objects were uploaded. Review the report, then rerun with --apply.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
