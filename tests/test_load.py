
"""Offline tests for the MongoDB Atlas loader."""

import json
from types import SimpleNamespace

import pytest

from pipeline.load import read_passages, remove_stale, upsert_passages


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
    """Simulate the MongoDB calls the loader makes, without a database."""

    def __init__(self):
        self.documents = {}
        self.batches = 0

    def bulk_write(self, requests, ordered=True):
        self.batches += 1
        for request in requests:
            doc = request._doc
            assert request._upsert is True
            assert set(doc) == {"$set"}
            _id = request._filter["_id"]
            self.documents.setdefault(_id, {"_id": _id}).update(doc["$set"])

    def delete_many(self, query):
        keep = set(query["_id"]["$nin"])
        stale = [
            _id for _id, d in self.documents.items()
            if d["source"] == query["source"] and _id not in keep
        ]
        for _id in stale:
            del self.documents[_id]
        return SimpleNamespace(deleted_count=len(stale))


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


def test_reload_keeps_fields_added_later():
    collection = FakeCollection()
    passage = make_passage("student-rules", "rule01")

    upsert_passages(collection, [passage])
    collection.documents[passage["id"]]["embedding"] = [0.1, 0.2]
    upsert_passages(collection, [passage])

    assert collection.documents[passage["id"]]["embedding"] == [0.1, 0.2]


def test_writes_are_batched():
    collection = FakeCollection()
    passages = [make_passage("catalog", "csce121", n) for n in range(1, 6)]

    upsert_passages(collection, passages, batch_size=2)

    assert collection.batches == 3
    assert len(collection.documents) == 5


def test_stale_passages_are_removed_only_for_loaded_sources():
    collection = FakeCollection()
    old = [
        make_passage("student-rules", "rule01"),
        make_passage("student-rules", "rule99"),
        make_passage("catalog", "csce121"),
    ]
    upsert_passages(collection, old)

    new = [make_passage("student-rules", "rule01")]
    upsert_passages(collection, new)
    deleted = remove_stale(collection, new, ["student-rules"])

    assert deleted == {"student-rules": 1}
    assert set(collection.documents) == {
        "student-rules:rule01:1",
        "catalog:csce121:1",
    }


def test_source_option_reads_one_file(tmp_path):
    write_jsonl(tmp_path / "student-rules.jsonl", [make_passage("student-rules", "rule01")])
    write_jsonl(tmp_path / "catalog.jsonl", [make_passage("catalog", "csce121")])

    passages, counts = read_passages(tmp_path, sources=["catalog"])

    assert [p["source"] for p in passages] == ["catalog"]
    assert dict(counts) == {"catalog": 1}


def test_unknown_source_is_rejected(tmp_path):
    write_jsonl(tmp_path / "catalog.jsonl", [make_passage("catalog", "csce121")])

    with pytest.raises(ValueError, match="No such file"):
        read_passages(tmp_path, sources=["oal"])


def test_anex_is_never_loaded(tmp_path):
    write_jsonl(tmp_path / "catalog.jsonl", [make_passage("catalog", "csce121")])
    write_jsonl(tmp_path / "anex.jsonl", [make_passage("anex", "csce-121")])

    _, counts = read_passages(tmp_path)
    assert dict(counts) == {"catalog": 1}

    with pytest.raises(ValueError, match="fetched live"):
        read_passages(tmp_path, sources=["anex"])
