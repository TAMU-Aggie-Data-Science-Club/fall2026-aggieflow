
"""Offline tests for the MongoDB Atlas loader."""

import json

import pytest

from pipeline.load import read_passages, upsert_passages


def make_passage(source, key, number=1):
    """Create a valid sample passage."""
    return {
        "id": f"{source}:{key}:{number}",
        "source": source,
        "title": "Example university information",
        "text": " ".join(
            ["This page explains important university policies and procedures."]
            * 20
        ),
        "source_url": "https://student-rules.tamu.edu/rule01/",
        "fetched_at": "2026-11-16T18:00:00Z",
    }


def write_jsonl(path, passages):
    with path.open("w", encoding="utf-8") as file:
        for passage in passages:
            file.write(json.dumps(passage) + "\n")


class FakeCollection:
    """Simulate MongoDB replace_one without a database."""

    def __init__(self):
        self.documents = {}

    def replace_one(self, query, document, upsert=False):
        assert upsert is True
        self.documents[query["id"]] = document.copy()


def test_read_multiple_sources(tmp_path):
    write_jsonl(
        tmp_path / "student-rules.jsonl",
        [make_passage("student-rules", "rule01")],
    )
    write_jsonl(
        tmp_path / "catalog.jsonl",
        [make_passage("catalog", "csce121")],
    )

    passages, counts = read_passages(tmp_path)

    assert len(passages) == 2
    assert counts["student-rules"] == 1
    assert counts["catalog"] == 1


def test_loading_twice_does_not_duplicate():
    collection = FakeCollection()
    passages = [
        make_passage("student-rules", "rule01"),
        make_passage("student-rules", "rule07"),
    ]

    upsert_passages(collection, passages)
    assert len(collection.documents) == 2

    upsert_passages(collection, passages)
    assert len(collection.documents) == 2

    passages[0]["title"] = "Updated university information"
    upsert_passages(collection, passages)

    assert len(collection.documents) == 2
    assert (
        collection.documents["student-rules:rule01:1"]["title"]
        == "Updated university information"
    )


def test_invalid_passage_is_rejected(tmp_path):
    passage = make_passage("student-rules", "rule01")
    del passage["source_url"]

    write_jsonl(tmp_path / "student-rules.jsonl", [passage])

    with pytest.raises(ValueError, match="Invalid passages"):
        read_passages(tmp_path)


def test_missing_files_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="No processed JSONL files"):
        read_passages(tmp_path)
