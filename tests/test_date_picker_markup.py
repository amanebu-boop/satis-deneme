from pathlib import Path


def test_meeting_and_follow_up_use_in_app_date_popovers():
    html = (Path(__file__).parents[1] / "web" / "index.html").read_text(encoding="utf-8")

    assert 'id="meeting-date-display"' in html
    assert 'id="follow-up-date-display"' in html
    assert 'aria-controls="meeting-date-calendar"' in html
    assert 'aria-controls="follow-up-date-calendar"' in html
    assert "Uygula" in html
    assert "new Intl.DateTimeFormat(\"tr-TR\"" in html



def test_date_picker_keeps_tapped_day_selected_until_apply():
    html = (Path(__file__).parents[1] / "web" / "index.html").read_text(encoding="utf-8")

    assert 'panel.addEventListener("click",event=>event.stopPropagation())' in html
    assert 'event.preventDefault();event.stopPropagation();selected=new Date(date.getFullYear(),date.getMonth(),date.getDate());render();' in html
    assert '!panel.contains(event.target)&&!display.contains(event.target)' in html
