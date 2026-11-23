"""get_professor_ratings, against a recorded RateMyProfessors response (see conftest.py)."""

import pytest

from agent import data


def test_matches_are_passages_most_rated_first():
    found = data.professor_ratings("Leyk")
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
    with pytest.raises(LookupError, match="another spelling"):
        data.professor_ratings("Eruhimova")


def test_a_professor_with_no_ratings_is_empty(monkeypatch):
    unrated = {"data": {"newSearch": {"teachers": {"edges": [{"node": {"numRatings": 0}}]}}}}
    monkeypatch.setattr(data, "_fetch_rmp", lambda name: unrated)
    assert data.professor_ratings("Hassanikhenar") == []
    assert data.professor_ratings("Hassanikhenar") == []  # same from the cache


def test_blank_name_is_rejected():
    with pytest.raises(ValueError):
        data.professor_ratings("  ")


def test_changed_response_format_errors(monkeypatch):
    monkeypatch.setattr(data, "_fetch_rmp", lambda name: {"data": None})
    with pytest.raises(RuntimeError):
        data.professor_ratings("Leyk")


def test_course_keeps_professors_reviewed_for_it():
    titles = lambda course: [p["title"] for p in data.professor_ratings("Leyk", course)]  # noqa: E731
    assert titles("CSCE 221") == ["Teresa Leyk on RateMyProfessors"]
    assert titles("csce120") == ["Zbigniew Leyk on RateMyProfessors"]  # review labeled just '120'
    assert len(titles("MATH 151")) == 2  # no reviews for it: keep everyone
