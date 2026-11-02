"""Canonical company sectors published by Erşen Makina (steel door excluded)."""

COMPANY_SECTORS = [
    "Çelik Eşya",
    "Mobilya",
    "Baza",
    "Kanepe ve Koltuk",
    "Bazalı Kanepe",
    "Hastane Yatağı Üreticileri",
    "Ütü Masası ve Kurutmalık Üreticileri",
    "Otomotiv",
    "Enjeksiyon Plastik Kalıpları",
    "Sac Kalıpları"
]


def is_valid_company_sector(value: str | None) -> bool:
    return isinstance(value, str) and value in COMPANY_SECTORS
