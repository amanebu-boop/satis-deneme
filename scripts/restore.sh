#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?Set BACKUP_ENCRYPTION_PASSPHRASE}"
: "${BACKUP_STAMP:?Set BACKUP_STAMP to the UTC backup timestamp}"
: "${RESTORE_CONFIRM:?Set RESTORE_CONFIRM=YES only after reviewing the target database}"

if [[ "$RESTORE_CONFIRM" != "YES" ]]; then
  echo "Restore blocked. Set RESTORE_CONFIRM=YES after verifying the target." >&2
  exit 2
fi

BACKUP_DIR="${BACKUP_DIR:-/backups}"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$BACKUP_DIR"
sha256sum --check "SHA256SUMS-$BACKUP_STAMP"

python /app/scripts/backup_crypto.py decrypt "postgres-$BACKUP_STAMP.dump.enc" "$WORK/postgres.dump"
python /app/scripts/backup_crypto.py decrypt "objects-$BACKUP_STAMP.tar.gz.enc" "$WORK/objects.tar.gz"

pg_restore --list "$WORK/postgres.dump" >/dev/null
pg_restore --clean --if-exists --no-owner --no-acl --dbname "$DATABASE_URL" "$WORK/postgres.dump"

python - "$WORK/objects.tar.gz" <<'PY'
import sys
import os
import tarfile
from app.storage import _bucket, _client

client = _client()
paginator = client.get_paginator("list_objects_v2")
existing = [obj["Key"] for page in paginator.paginate(Bucket=_bucket()) for obj in page.get("Contents", [])]
if existing and os.environ.get("RESTORE_ALLOW_NONEMPTY_BUCKET") != "YES":
    raise SystemExit("Target bucket is not empty. Use a new empty bucket or set RESTORE_ALLOW_NONEMPTY_BUCKET=YES after review.")
with tarfile.open(sys.argv[1], "r:gz") as archive:
    for member in archive:
        if not member.isfile() or member.name.startswith("/") or ".." in member.name.split("/"):
            raise SystemExit("Unsafe archive member; refusing object restore")
        source = archive.extractfile(member)
        if source is None:
            continue
        client.put_object(Bucket=_bucket(), Key=member.name, Body=source.read())
PY

echo "Restore completed. Verify record counts, documents, Excel and PDF output before reopening traffic."
