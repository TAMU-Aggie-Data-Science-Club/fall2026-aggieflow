"""library_tools (#121): hours and Tech Bar equipment against recorded LibCal
responses (see conftest.py), search over sample passages, and the collector's
page filter and splitting. No network."""

import importlib.util
from pathlib import Path

import pytest

from agent import data
from agent.checks import finalize
from agent.tools import GROUP_OF
from agent.tools.libraries import get_library_hours, list_library_equipment, search_libraries

_path = Path(__file__).resolve().parents[1] / "pipeline" / "collect" / "libraries.py"
_spec = importlib.util.spec_from_file_location("libraries_collect", _path)
collect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(collect)


# --- hours ------------------------------------------------------------------------

def test_hours_for_one_library_cover_two_weeks_with_today_marked():
    [p] = data.library_hours("west campus library")
    assert p["id"] == "libraries:hours/3516:1:live"
    assert p["source"] == "libraries"
    assert p["source_url"] == "https://library.tamu.edu/about/hours.html"  # the page students open, not the feed
    assert p["title"] == "West Campus Library hours"
    assert "Today is Sunday, November 22, 2026." in p["text"]
    assert "Sunday, November 22 (today): noon - 11pm" in p["text"]
    assert "Thursday, November 26: Closed" in p["text"]  # Thanksgiving, from next week
    assert "Wednesday, November 25: 7am - noon" in p["text"]


def test_midnight_and_wcl_shorthand():
    [p] = data.library_hours("wcl")
    assert p["title"] == "West Campus Library hours"
    evans = data.library_hours("evans annex")
    assert [e["title"] for e in evans] == ["Sterling C. Evans Library Annex hours"]
    assert "Monday, November 16: 7am - 3am" in evans[0]["text"]
    assert "past midnight run into the next morning" in evans[0]["text"]


def test_evans_means_the_library_and_the_annex():
    found = data.library_hours("Evans Library")
    assert sorted(p["title"] for p in found) == ["Sterling C. Evans Library Annex hours",
                                                 "Sterling C. Evans Library hours"]
    library = next(p for p in found if p["title"] == "Sterling C. Evans Library hours")
    assert "Friday, November 20: 7am - 7pm" in library["text"]
    assert "Monday, November 16: 7am - midnight" in library["text"]  # 12am closes at night


def test_no_location_lists_libraries_with_hours_set():
    titles = {p["title"] for p in data.library_hours()}
    assert "West Campus Library hours" in titles
    assert "Swipe Access hours" not in titles  # a service, not a library
    assert "Policy Sciences & Economics Library hours" not in titles  # no hours set


def test_a_library_without_hours_set_says_so():
    [p] = data.library_hours("policy sciences")
    assert "Monday, November 16: hours not posted" in p["text"]


def test_unknown_location_names_the_libraries():
    with pytest.raises(LookupError, match="West Campus Library"):
        data.library_hours("zachry")


def test_hours_are_cached(monkeypatch):
    calls = []
    real = data._fetch_libcal
    monkeypatch.setattr(data, "_fetch_libcal", lambda url, params: calls.append(url) or real(url, params))
    data.library_hours("wcl")
    data.library_hours("evans")
    assert len(calls) == 1


def test_a_changed_feed_raises_instead_of_answering(monkeypatch):
    monkeypatch.setattr(data, "_fetch_libcal", lambda url, params: {"oops": []})
    with pytest.raises(RuntimeError, match="changed its hours format"):
        data.library_hours("wcl")


# --- equipment --------------------------------------------------------------------

def test_a_category_lists_each_tech_bar_with_its_reserve_page():
    found = data.library_equipment("calculators")
    assert [p["title"] for p in found] == ["Calculators at the Tech Bar at Evans Library Annex",
                                           "Calculators at the Tech Bar at West Campus Library"]
    annex = found[0]
    assert annex["id"] == "libraries:equipment/20326-42841:1:live"
    assert annex["source_url"] == "https://tamu.libcal.com/equipment?lid=20326&gid=42841"
    assert "(5 listed;" in annex["text"]
    assert "- TI-84 Plus CE (G) (2 listed; Only one unit per UIN)" in annex["text"]
    assert "- Casio FX-CG10 (Graphing Calculator One per UIN)" in annex["text"]  # HTML stripped
    assert "<" not in annex["text"] and "&nbsp;" not in annex["text"]
    assert "NetID" in annex["text"]
    # Category ids differ per Tech Bar: West Campus calculators are gid 43366, not 42841.
    assert found[1]["source_url"] == "https://tamu.libcal.com/equipment?lid=20467&gid=43366"


@pytest.mark.parametrize("asked", ["laptops", "Chromebook", "chromebooks"])
def test_everyday_words_find_the_category(asked):
    found = data.library_equipment(asked, "evans annex")
    assert [p["title"] for p in found] == ["Chromebooks at the Tech Bar at Evans Library Annex"]


def test_a_location_narrows_to_one_tech_bar():
    [p] = data.library_equipment("calculators", "WCL")
    assert p["title"] == "Calculators at the Tech Bar at West Campus Library"
    assert "- TI - BA II Plus" in p["text"]


def test_a_model_name_searches_items_across_categories():
    [p] = data.library_equipment("TI-84", "annex")
    assert p["title"] == "Items matching 'TI-84' at the Tech Bar at Evans Library Annex"
    assert p["source_url"] == "https://tamu.libcal.com/equipment?lid=20326"
    assert "TI-84 Data Transfer Cable: USB-A to Mini-B cable (Chargers, cables and adaptors)" in p["text"]
    assert "Ti-84 plus (Calculators)" in p["text"]


def test_an_exact_category_name_wins_over_its_words(monkeypatch):
    # 'accessories' alone means computer accessories; the full name is its own category.
    asked = []
    monkeypatch.setattr(data, "_equipment_items",
                        lambda lid, gid, query="": asked.append((lid, gid, query)) or ([], "x"))
    with pytest.raises(LookupError):
        data.library_equipment("Photography accessories", "annex")
    assert asked == [(20326, 42971, "")]


def test_a_category_one_tech_bar_lacks():
    with pytest.raises(LookupError, match="doesn't lend astronomy"):
        data.library_equipment("telescope", "west campus")


def test_nothing_matching_lists_the_categories():
    with pytest.raises(LookupError, match="Calculators, Chargers"):
        data.library_equipment("xbox")


def test_unknown_tech_bar():
    with pytest.raises(LookupError, match="Tech Bar at West Campus Library"):
        data.library_equipment("calculators", "zachry")


def test_equipment_follows_libcals_pages(monkeypatch):
    monkeypatch.setattr(data, "LIBCAL_PER_PAGE", 2)
    [p] = data.library_equipment("calculators", "annex")
    assert "(5 listed;" in p["text"]  # 3 pages of 2


# --- the tools and the agent's checks ---------------------------------------------

def test_tools_are_one_group():
    assert {GROUP_OF[t] for t in ("search_libraries", "get_library_hours", "list_library_equipment")} \
        == {"library_tools"}


def test_search_libraries_finds_the_tech_bar_rules():
    found = search_libraries.invoke({"query": "tech bar late fee"})
    assert found[0]["source_url"] == "https://library.tamu.edu/services/techbar.html"
    assert all(p["source"] == "libraries" for p in found)  # only this source


def test_tools_return_live_passages_the_check_dates():
    hours = get_library_hours.invoke({"location": "west campus library"})
    gear = list_library_equipment.invoke({"category": "calculators", "location": "wcl"})
    answer = (f"WCL is open noon to 11pm today ({hours[0]['source_url']}) and lends calculators "
              f"({gear[0]['source_url']}).")
    text, cited = finalize(answer, hours + gear)
    assert len(cited) == 2
    assert "(as of " in text  # live data says when it was fetched


def test_a_library_search_that_finds_nothing_points_to_the_library_site():
    text, cited = finalize("I couldn't find that.", [], ["search_libraries"])
    assert cited == [] and "the University Libraries (https://library.tamu.edu)" in text


def test_every_tool_has_a_site_for_not_sure():
    from agent.checks import SITES
    from agent.tools import ALL_TOOLS
    assert {t.name for t in ALL_TOOLS} <= set(SITES)


# --- the collector ----------------------------------------------------------------

@pytest.mark.parametrize("url,kept", [
    ("https://library.tamu.edu/services/techbar.html", True),
    ("https://library.tamu.edu/borrowing/returns.html", True),
    ("https://library.tamu.edu/spaces/reserve-a-room.html", True),
    ("https://library.tamu.edu/medical-sciences/borrowing/index.html", True),
    ("https://library.tamu.edu/askus.html", True),
    ("https://library.tamu.edu/about/hours.html", False),  # times load with JavaScript
    ("https://library.tamu.edu/medical-sciences/about/hours.html", False),
    ("https://library.tamu.edu/about/annual-report/2025/ai-expert.html", False),
    ("https://library.tamu.edu/cushing/about/contact-us.html", False),
    ("https://example.com/services/techbar.html", False),
])
def test_collector_keeps_student_sections(url, kept):
    assert collect.keep(url) is kept


def test_page_keys():
    assert collect.page_key("https://library.tamu.edu/services/techbar.html") == "services/techbar"
    assert collect.page_key("https://library.tamu.edu/borrowing/index.html") == "borrowing"


def test_sitemap_keeps_student_pages_once():
    xml = b"""<?xml version="1.0" encoding="utf-8" ?>
<urlset xmlns="https://www.sitemaps.org/schemas/sitemap/0.9">
<url><loc>https://library.tamu.edu/services/techbar.html</loc></url>
<url><loc>https://library.tamu.edu/about/hours.html</loc></url>
<url><loc>https://library.tamu.edu/cushing/visit.html</loc></url>
<url><loc>https://library.tamu.edu/services/techbar.html</loc></url>
</urlset>"""
    assert collect.sitemap_urls(xml) == ["https://library.tamu.edu/services/techbar.html"]


def test_passages_come_from_main_without_menus():
    rule = "Calculators are limited to a 3-day loan period and other equipment to 7 days. " * 5
    html = f"""<html><head><title>The Tech Bar | University Libraries</title></head><body>
<header><nav>Home Hours Ask Us</nav></header>
<main><nav class="breadcrumb">Home / Services</nav><h1>The Tech Bar</h1>
<h2>Borrowing Policies</h2><p>{rule}</p><form><button>Search</button></form></main>
<footer>Texas A&amp;M University Libraries</footer></body></html>"""
    [p] = collect.build_passages([("https://library.tamu.edu/services/techbar.html", html, "2026-11-22T00:00:00Z")])
    assert p["id"] == "libraries:services/techbar:1"
    assert p["title"] == "The Tech Bar"
    assert p["source_url"] == "https://library.tamu.edu/services/techbar.html"
    assert "3-day loan" in p["text"]
    assert "Ask Us" not in p["text"] and "Search" not in p["text"] and "Texas A&M University Libraries" not in p["text"]


def test_a_page_with_almost_no_text_is_skipped():
    html = "<html><body><main><h1>Appeal a charge</h1><p>Use this form.</p></main></body></html>"
    assert collect.build_passages([("https://library.tamu.edu/services/x.html", html, "2026-11-22T00:00:00Z")]) == []
