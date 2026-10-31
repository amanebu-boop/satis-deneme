from pathlib import Path


def test_meeting_and_follow_up_use_in_app_date_popovers():
    html = (Path(__file__).parents[1] / "web" / "index.html").read_text(encoding="utf-8")

    assert 'id="meeting-date-display"' in html
    assert 'id="follow-up-date-display"' in html
    assert 'aria-controls="meeting-date-calendar"' in html
    assert 'aria-controls="follow-up-date-calendar"' in html
    assert "Uygula" in html
    assert "new Intl.DateTimeFormat(\"tr-TR\"" in html
