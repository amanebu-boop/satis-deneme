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

openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
  -in "postgres-$BACKUP_STAMP.dump.enc" -out "$WORK/postgres.dump"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
  -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
  -in "objects-$BACKUP_STAMP.tar.gz.enc" -out "$WORK/objects.tar.gz"

pg_restore --list "$WORK/postgres.dump" >/dev/null
pg_restore --clean --if-exists --no-owner --no-acl --dbname "$DATABASE_URL" "$WORK/postgres.dump"

python - "$WORK/objects.tar.gz" <<'PY'
import os
import sys
import tarfile
from app.storage import _bucket, _client

client = _client()
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
