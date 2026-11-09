from __future__ import annotations

import ast
import re
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
SECTOR_SOURCE = (ROOT / "app" / "company_sectors.py").read_text(encoding="utf-8")


class CompanySectorParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_sector_select = False
        self.sector_select_attrs: dict[str, str | None] = {}
        self.options: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "select" and attributes.get("id") == "company-sector":
            self.in_sector_select = True
            self.sector_select_attrs = attributes
        elif tag == "option" and self.in_sector_select:
            self.options.append(attributes.get("value") or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "select" and self.in_sector_select:
            self.in_sector_select = False


def canonical_sectors() -> list[str]:
    module = ast.parse(SECTOR_SOURCE)
    assignment = next(
        node for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "COMPANY_SECTORS"
                for target in node.targets)
    )
    return ast.literal_eval(assignment.value)


def test_company_create_and_search_are_separate_tabs() -> None:
    assert 'data-company-tab="create"' in HTML
    assert 'data-company-tab="search"' in HTML
    assert 'id="company-create-tab"' in HTML
    assert 'id="company-search-tab"' in HTML
    assert 'document.getElementById("company-search-tab").hidden=tab!=="search"' in HTML
    assert 'if(tab==="search")loadCompanies()' in HTML


def test_sector_picker_is_required_multi_select_and_matches_backend_catalog() -> None:
    parser = CompanySectorParser()
    parser.feed(HTML)
    assert parser.sector_select_attrs.get("multiple") is None
    assert "required" in parser.sector_select_attrs
    assert parser.options == canonical_sectors()
    assert "Çelik Kapı" not in parser.options


def test_company_save_sends_selected_sectors_using_api_field_name() -> None:
    assert 'sectors:Array.from(document.getElementById("company-sector").selectedOptions).map(option=>option.value)' in HTML
    assert 'if(!payload.sectors.length)' in HTML
    assert not re.search(r'if\s*\(\s*!payload\.sector\s*\)', HTML)


def test_editing_a_company_opens_the_company_create_tab() -> None:
    edit_handler = HTML.split("function fillCompanyForm(company){", 1)[1].split("\n}", 1)[0]
    assert 'document.querySelector(\'[data-company-tab="create"]\')' in edit_handler
    assert "createTab.click()" in edit_handler


def test_company_search_and_filters_are_inside_search_tab() -> None:
    search_panel = HTML.split('id="company-search-tab"', 1)[1].split("</section>", 1)[0]
    assert 'id="company-search"' in search_panel
    assert 'id="company-filter-city-search"' in search_panel
    assert 'id="company-filter-district-search"' in search_panel
    assert 'id="company-rows"' in search_panel
