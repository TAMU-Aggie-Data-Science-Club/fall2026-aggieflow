"""Offline tests for pipeline/check.py, the passage-format checker.

Run from the repo root:  python -m pytest tests
"""

import importlib.util
import json
from pathlib import Path

import pytest

_path = Path(__file__).resolve().parents[1] / "pipeline" / "check.py"
_spec = importlib.util.spec_from_file_location("check", _path)
check = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check)

WORDS_200 = " ".join(["An absence is excused when the student documents it."] * 22)


def good(**changes):
    p = {
        "id": "student-rules:rule07:3",
        "source": "student-rules",
        "title": "Rule 7: Attendance",
        "text": WORDS_200,
        "source_url": "https://student-rules.tamu.edu/rule07/",
        "fetched_at": "2026-11-10T18:04:00Z",
    }
    p.update(changes)
    return p


def errors_for(**changes):
    return check.check_passage(good(**changes))[0]


def write(tmp_path, rows, name="student-rules.jsonl"):
    f = tmp_path / name
    f.write_text("\n".join(r if isinstance(r, str) else json.dumps(r) for r in rows) + "\n",
                 encoding="utf-8")
    return f


# --- one passage -----------------------------------------------------------

def test_good_passage_has_no_problems():
    assert check.check_passage(good()) == ([], [])


def test_colons_in_page_key_are_allowed():
    assert errors_for(id="catalog:CSCE:120:0", source="catalog") == []


def test_missing_field():
    p = good()
    del p["fetched_at"]
    assert any("missing field(s): fetched_at" in e for e in check.check_passage(p)[0])


def test_extra_field():
    assert any("unknown field(s): url" in e for e in errors_for(url="x"))


def test_non_string_field():
    assert any("text must be a string" in e for e in errors_for(text=None))


def test_not_an_object():
    assert check.check_passage(["a"])[0] == ["line is not a JSON object"]


def test_unknown_source():
    assert any("source 'reddit'" in e for e in errors_for(source="reddit", id="reddit:x:1"))


@pytest.mark.parametrize("bad_id", ["student-rules:rule07", "rule07:3", "student-rules:rule07:x",
                                    "student-rules::3", "student-rules:rule 07:3", ""])
def test_bad_id_format(bad_id):
    assert any("is not <source>:<page key>:<chunk number>" in e for e in errors_for(id=bad_id))


def test_id_prefix_must_match_source():
    assert any("id starts with 'catalog'" in e for e in errors_for(id="catalog:rule07:3"))


def test_empty_title():
    assert "title is empty" in errors_for(title="  ")


def test_empty_text():
    assert "text is empty" in errors_for(text="   \n ")


def test_huge_text():
    assert any("over 800" in e for e in errors_for(text="word " * 801))


@pytest.mark.parametrize("n", [20, 450])
def test_text_outside_target_is_a_warning(n):
    errors, warnings = check.check_passage(good(text="word " * n))
    assert errors == [] and any(f"{n} words" in w for w in warnings)


@pytest.mark.parametrize("text", ["<p>Rule 7</p>", "See <a href='x'>here</a>", "line<br/>break",
                                  "Rule&nbsp;7", "Q&#8211;drop"])
def test_html_left_in_text(text):
    assert any(e.startswith("text still has") for e in errors_for(text=WORDS_200 + " " + text))


def test_html_in_title():
    assert any("title still has HTML" in e for e in errors_for(title="<b>Rule 7</b>"))


def test_comparisons_and_ampersands_are_not_html():
    assert errors_for(text=WORDS_200 + " If x < 5 and y > 3, Texas A&M applies.") == []


@pytest.mark.parametrize("url", ["student-rules.tamu.edu/rule07/", "ftp://tamu.edu/x",
                                 "https://student rules.tamu.edu", "https://localhost/x"])
def test_bad_source_url(url):
    assert any("is not a web address" in e for e in errors_for(source_url=url))


@pytest.mark.parametrize("url", ["https://student-rules.tamu.edu/wp-json/wp/v2/pages",
                                 "https://anex.us/api/grades?course=120",
                                 "https://x.tamu.edu/courses.json",
                                 "https://x.tamu.edu/list?format=json"])
def test_api_source_url(url):
    assert any("looks like an API URL" in e for e in errors_for(source_url=url))


@pytest.mark.parametrize("ts", ["2026-11-10 18:04:00", "2026-11-10T18:04:00+00:00",
                                "2026-11-10T18:04:00.123Z", "11/10/2026"])
def test_bad_fetched_at_format(ts):
    assert any("is not UTC ISO 8601" in e for e in errors_for(fetched_at=ts))


def test_impossible_fetched_at():
    assert any("not a real date" in e for e in errors_for(fetched_at="2026-02-30T25:00:00Z"))


# --- whole files -----------------------------------------------------------

def test_clean_file(tmp_path):
    f = write(tmp_path, [good(), good(id="student-rules:rule07:4")])
    assert check.check_file(f) == ([], [], 2)
    assert check.main([str(f)]) == 0


def test_duplicate_ids(tmp_path):
    f = write(tmp_path, [good(), good()])
    errors, _, count = check.check_file(f)
    assert count == 2 and errors == [(2, "duplicate id 'student-rules:rule07:3' (first on line 1)")]


def test_bad_json_and_blank_lines(tmp_path):
    f = write(tmp_path, [good(), "{not json", "", good(id="student-rules:rule07:4")])
    errors, _, count = check.check_file(f)
    assert count == 2
    assert [n for n, _ in errors] == [2, 3]


def test_empty_file(tmp_path):
    f = tmp_path / "student-rules.jsonl"
    f.write_text("", encoding="utf-8")
    assert check.check_file(f)[0] == [(0, "file has no passages")]


def test_odd_file_name_is_a_warning(tmp_path):
    f = write(tmp_path, [good()], name="rules.jsonl")
    errors, warnings, _ = check.check_file(f)
    assert errors == [] and warnings and warnings[0][0] == 0


def test_missing_file(tmp_path):
    errors, _, _ = check.check_file(tmp_path / "nope.jsonl")
    assert errors and "cannot read file" in errors[0][1]


def test_every_problem_in_one_made_up_bad_file(tmp_path, capsys):
    rows = [
        good(),
        good(),                                                    # duplicate id
        good(id="student-rules:rule08:0", text="<p>" + WORDS_200 + "</p>"),
        good(id="student-rules:rule09:0", text=""),
        good(id="student-rules:rule10:0", text="word " * 900),
        good(id="oops", source_url="https://student-rules.tamu.edu/wp-json/wp/v2/pages"),
        {k: v for k, v in good(id="student-rules:rule11:0").items() if k != "title"},
        good(id="student-rules:rule12:0", fetched_at="yesterday"),
        "not json",
    ]
    f = write(tmp_path, rows)
    assert check.main([str(f)]) == 1
    out = capsys.readouterr().out
    for expected in ["duplicate id", "text still has HTML", "text is empty", "over 800",
                     "is not <source>:<page key>", "looks like an API URL", "missing field(s): title",
                     "is not UTC ISO 8601", "not valid JSON", "FAIL"]:
        assert expected in out, expected


def test_usage_without_arguments(capsys):
    assert check.main([]) == 2
    assert "usage" in capsys.readouterr().out
