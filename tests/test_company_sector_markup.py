from pathlib import Path

from app.company_sectors import COMPANY_SECTORS


def test_company_sector_form_uses_the_canonical_required_list():
    html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    assert '<select id="company-sector" required>' in html
    for sector in COMPANY_SECTORS:
        assert f'<option value="{sector}">{sector}</option>' in html
    assert "Çelik Kapı" not in html
    assert 'sector:document.getElementById("company-sector").value' in html


def test_dashboard_ai_action_creates_records_instead_of_opening_a_draft():
    html = (Path(__file__).resolve().parents[1] / "web" / "index.html").read_text(encoding="utf-8")
    assert "Yapay zekâ ile firma ve görüşme kaydı" in html
    assert "Firma ve görüşme kaydı oluştur" in html
    assert 'fetch("/api/meetings/capture"' in html
    assert "/api/meetings/prepare" not in html
    assert "Taslak hazırla" not in html
