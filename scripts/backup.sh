#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

: "${DATABASE_URL:?DATABASE_URL is required}"
: "${BACKUP_ENCRYPTION_PASSPHRASE:?Set a strong BACKUP_ENCRYPTION_PASSPHRASE}"
: "${S3_ENDPOINT_URL:?S3_ENDPOINT_URL is required}"
: "${S3_BUCKET:?S3_BUCKET is required}"
: "${S3_ACCESS_KEY:?S3_ACCESS_KEY is required}"
: "${S3_SECRET_KEY:?S3_SECRET_KEY is required}"

BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
mkdir -p "$BACKUP_DIR"

pg_dump --format=custom --no-owner --no-acl "$DATABASE_URL" --file "$WORK/postgres.dump"
python /app/scripts/backup_objects.py "$WORK/objects.tar.gz"

python /app/scripts/backup_crypto.py encrypt "$WORK/postgres.dump" "$BACKUP_DIR/postgres-$STAMP.dump.enc"
python /app/scripts/backup_crypto.py encrypt "$WORK/objects.tar.gz" "$BACKUP_DIR/objects-$STAMP.tar.gz.enc"

(
  cd "$BACKUP_DIR"
  sha256sum "postgres-$STAMP.dump.enc" "objects-$STAMP.tar.gz.enc" > "SHA256SUMS-$STAMP"
)

find "$BACKUP_DIR" -type f -mtime +14 -delete
printf 'Backup completed: %s\n' "$STAMP"
