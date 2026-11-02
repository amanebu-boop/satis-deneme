from pathlib import Path
import pytest
from scripts.backup_crypto import decrypt_file, encrypt_file

def test_backup_crypto_round_trip(tmp_path: Path):
    source = tmp_path / 'source.bin'
    encrypted = tmp_path / 'source.enc'
    restored = tmp_path / 'restored.bin'
    source.write_bytes(bytes(range(256)) * 4096)
    encrypt_file(source, encrypted, 'a-strong-backup-passphrase-123')
    assert encrypted.read_bytes() != source.read_bytes()
    decrypt_file(encrypted, restored, 'a-strong-backup-passphrase-123')
    assert restored.read_bytes() == source.read_bytes()

def test_backup_crypto_rejects_wrong_passphrase_without_output(tmp_path: Path):
    source = tmp_path / 'source.bin'
    encrypted = tmp_path / 'source.enc'
    restored = tmp_path / 'restored.bin'
    source.write_bytes(b'private backup payload')
    encrypt_file(source, encrypted, 'a-strong-backup-passphrase-123')
    with pytest.raises(Exception):
        decrypt_file(encrypted, restored, 'a-different-backup-passphrase-456')
    assert not restored.exists()

def test_backup_crypto_requires_long_passphrase(tmp_path: Path):
    source = tmp_path / 'source.bin'
    source.write_bytes(b'payload')
    with pytest.raises(ValueError):
        encrypt_file(source, tmp_path / 'source.enc', 'too-short')
