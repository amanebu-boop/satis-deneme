"""Streaming authenticated backup encryption using AES-256-GCM."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import tempfile

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"SALESBK1"
SALT_BYTES = 16
NONCE_BYTES = 12
TAG_BYTES = 16
ITERATIONS = 600_000
CHUNK_BYTES = 1024 * 1024


def _key(passphrase: str, salt: bytes) -> bytes:
    if not passphrase or len(passphrase) < 24:
        raise ValueError("Backup passphrase must contain at least 24 characters")
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return kdf.derive(passphrase.encode("utf-8"))


def _temporary_output(destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    return tempfile.NamedTemporaryFile(prefix=destination.name + ".", suffix=".partial", dir=destination.parent, delete=False)


def encrypt_file(source: Path, destination: Path, passphrase: str) -> None:
    salt = os.urandom(SALT_BYTES)
    nonce = os.urandom(NONCE_BYTES)
    header = MAGIC + salt + nonce
    encryptor = Cipher(algorithms.AES(_key(passphrase, salt)), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(header)
    temporary = _temporary_output(destination)
    try:
        with source.open("rb") as input_file, temporary as output_file:
            output_file.write(header)
            while chunk := input_file.read(CHUNK_BYTES):
                output_file.write(encryptor.update(chunk))
            output_file.write(encryptor.finalize())
            output_file.write(encryptor.tag)
            output_file.flush()
            os.fsync(output_file.fileno())
        os.replace(temporary.name, destination)
    except Exception:
        Path(temporary.name).unlink(missing_ok=True)
        raise


def decrypt_file(source: Path, destination: Path, passphrase: str) -> None:
    total_size = source.stat().st_size
    header_size = len(MAGIC) + SALT_BYTES + NONCE_BYTES
    if total_size < header_size + TAG_BYTES:
        raise ValueError("Encrypted backup is truncated")
    temporary = _temporary_output(destination)
    try:
        with source.open("rb") as input_file:
            header = input_file.read(header_size)
            if header[:len(MAGIC)] != MAGIC:
                raise ValueError("Unknown encrypted backup format")
            salt = header[len(MAGIC):len(MAGIC) + SALT_BYTES]
            nonce = header[len(MAGIC) + SALT_BYTES:]
            input_file.seek(-TAG_BYTES, os.SEEK_END)
            tag = input_file.read(TAG_BYTES)
            ciphertext_size = total_size - header_size - TAG_BYTES
            input_file.seek(header_size)
            decryptor = Cipher(algorithms.AES(_key(passphrase, salt)), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(header)
            with temporary as output_file:
                remaining = ciphertext_size
                while remaining:
                    chunk = input_file.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise ValueError("Encrypted backup is truncated")
                    remaining -= len(chunk)
                    output_file.write(decryptor.update(chunk))
                output_file.write(decryptor.finalize())
                output_file.flush()
                os.fsync(output_file.fileno())
        os.replace(temporary.name, destination)
    except Exception:
        Path(temporary.name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["encrypt", "decrypt"])
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    passphrase = os.environ.get("BACKUP_ENCRYPTION_PASSPHRASE", "")
    if args.action == "encrypt":
        encrypt_file(args.source, args.destination, passphrase)
    else:
        decrypt_file(args.source, args.destination, passphrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
