"""get_professor_ratings, against a recorded RateMyProfessors response (see conftest.py)."""

import pytest

from agent import ratings


def test_matches_are_passages_most_rated_first():
    found = ratings.professor_ratings("Leyk")
    assert [p["title"] for p in found] == [
        "Teresa Leyk on RateMyProfessors",
        "Zbigniew Leyk on RateMyProfessors",
    ]
    first = found[0]
    assert first["id"] == "ratemyprofessors:609101:live"
    assert first["source"] == "ratemyprofessors"
    assert first["source_url"] == "https://www.ratemyprofessors.com/professor/609101"
    assert "overall quality 3.1/5, difficulty 3.5/5, 60% would take again, from 157 ratings" in first["text"]
    assert "CSCE221" in first["text"]


def test_no_match_raises_and_suggests_another_spelling():
    # RMP doesn't fuzzy-match, so the agent needs an error to know to retry (#117)
    with pytest.raises(LookupError, match="another spelling") as err:
        ratings.professor_ratings("Eruhimova")
    assert "start the same way" not in str(err.value)  # 'eruhi', 'eruh', 'eru' find nobody either


def _search(*nodes):
    return {"data": {"newSearch": {"teachers": {"edges": [{"node": n} for n in nodes]}}}}


def _teacher(first, last, ratings=12):
    return {"legacyId": 1, "firstName": first, "lastName": last, "department": "Physics",
            "avgRating": 4.9, "avgDifficulty": 3.3, "numRatings": ratings, "wouldTakeAgainPercent": 99,
            "ratings": {"edges": []}}


def test_a_close_misspelling_returns_that_professor_with_a_note(monkeypatch):
    found = {"eru": _search(_teacher("Tatiana", "Erukhimova "))}
    asked = []
    monkeypatch.setattr(ratings, "_fetch_rmp", lambda name: asked.append(name) or found.get(name, _search()))
    [p] = ratings.professor_ratings("Tatiana Eruhimova")
    assert p["title"] == "Tatiana Erukhimova on RateMyProfessors"
    assert p["text"].startswith("No exact match for 'Tatiana Eruhimova'; Tatiana Erukhimova is the closest name")
    assert asked == ["tatiana eruhimova", "eruhi", "eruh", "eru"]  # the longest word, shortened
    ratings.professor_ratings("tatiana eruhimova")
    assert len(asked) == 4  # cached


@pytest.mark.parametrize("asked, near", [
    ("Hassanikhenar", "Hassani"),  # a different name: maybe the same person, maybe not
    ("Leik", "Lei"),               # too short to correct safely
])
def test_a_different_name_is_only_suggested(monkeypatch, asked, near):
    monkeypatch.setattr(ratings, "_fetch_rmp",
                        lambda name: _search() if name == asked.lower() else _search(_teacher("Ahmad", near)))
    with pytest.raises(LookupError, match=f"start the same way: Ahmad {near}\\. These are different names") as err:
        ratings.professor_ratings(asked)
    assert "None of these" in str(err.value)

def test_a_professor_with_no_ratings_is_empty(monkeypatch):
    unrated = {"data": {"newSearch": {"teachers": {"edges": [{"node": {"numRatings": 0}}]}}}}
    monkeypatch.setattr(ratings, "_fetch_rmp", lambda name: unrated)
    assert ratings.professor_ratings("Hassanikhenar") == []
    assert ratings.professor_ratings("Hassanikhenar") == []  # same from the cache


def test_blank_name_is_rejected():
    with pytest.raises(ValueError):
        ratings.professor_ratings("  ")


def test_changed_response_format_errors(monkeypatch):
    monkeypatch.setattr(ratings, "_fetch_rmp", lambda name: {"data": None})
    with pytest.raises(RuntimeError):
        ratings.professor_ratings("Leyk")


def test_course_keeps_professors_reviewed_for_it():
    titles = lambda course: [p["title"] for p in ratings.professor_ratings("Leyk", course)]  # noqa: E731
    assert titles("CSCE 221") == ["Teresa Leyk on RateMyProfessors"]
    assert titles("csce120") == ["Zbigniew Leyk on RateMyProfessors"]  # review labeled just '120'
    assert len(titles("MATH 151")) == 2  # no reviews for it: keep everyone
