"""Tests for the vector store Chroma wrapper."""

from __future__ import annotations

import sys
import types

import pytest


if "sentence_transformers" not in sys.modules:
    fake_sentence_transformers = types.ModuleType("sentence_transformers")

    class _SentenceTransformer:  # pragma: no cover - import shim for tests only
        def __init__(self, *args, **kwargs):
            pass

    fake_sentence_transformers.SentenceTransformer = _SentenceTransformer
    sys.modules["sentence_transformers"] = fake_sentence_transformers

if "chromadb" not in sys.modules:
    fake_chromadb = types.ModuleType("chromadb")

    class _HttpClient:  # pragma: no cover - import shim for tests only
        def __init__(self, *args, **kwargs):
            pass

    fake_chromadb.HttpClient = _HttpClient
    sys.modules["chromadb"] = fake_chromadb

from app.vector_store import VectorStore


class FakeCollection:
    def __init__(self, *, get_result: dict[str, object], count_result: int = 0):
        self.get_result = get_result
        self.count_result = count_result
        self.get_calls: list[dict[str, object]] = []
        self.delete_calls: list[dict[str, object]] = []

    def count(self) -> int:
        return self.count_result

    def get(self, **kwargs):
        self.get_calls.append(kwargs)
        return self.get_result

    def delete(self, **kwargs):
        self.delete_calls.append(kwargs)


def _make_store(collection: FakeCollection) -> VectorStore:
    store = VectorStore.__new__(VectorStore)
    store.collection = collection
    return store


def test_normalize_where_filter_wraps_document_id_with_scope():
    store = VectorStore.__new__(VectorStore)

    normalized = store._normalize_where_filter(
        {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-001",
            "document_id": "doc-123",
        }
    )

    assert normalized == {
        "$and": [
            {"tenant_id": "tenant-fixed-001"},
            {"clerk_user_id": "clerk-user-001"},
            {
                "$or": [
                    {"document_id": "doc-123"},
                    {"doc_id": "doc-123"},
                ]
            },
        ]
    }


def test_get_stats_uses_ids_only_for_filtered_scope():
    collection = FakeCollection(
        get_result={"ids": ["chunk-1", "chunk-2", "chunk-3"]}, count_result=99
    )
    store = _make_store(collection)

    stats = store.get_stats(
        {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-001",
        }
    )

    assert stats["total_documents"] == 3
    assert collection.get_calls == [
        {
            "where": {
                "tenant_id": "tenant-fixed-001",
                "clerk_user_id": "clerk-user-001",
            },
            "include": [],
        }
    ]


def test_delete_documents_uses_ids_only_and_scoped_filter():
    collection = FakeCollection(get_result={"ids": ["chunk-1", "chunk-2"]})
    store = _make_store(collection)

    deleted = store.delete_documents(
        {
            "tenant_id": "tenant-fixed-001",
            "clerk_user_id": "clerk-user-001",
            "document_id": "doc-123",
        }
    )

    assert deleted == 2
    assert collection.get_calls == [
        {
            "where": {
                "$and": [
                    {"tenant_id": "tenant-fixed-001"},
                    {"clerk_user_id": "clerk-user-001"},
                    {
                        "$or": [
                            {"document_id": "doc-123"},
                            {"doc_id": "doc-123"},
                        ]
                    },
                ]
            },
            "include": [],
        }
    ]
    assert collection.delete_calls == [
        {
            "where": {
                "$and": [
                    {"tenant_id": "tenant-fixed-001"},
                    {"clerk_user_id": "clerk-user-001"},
                    {
                        "$or": [
                            {"document_id": "doc-123"},
                            {"doc_id": "doc-123"},
                        ]
                    },
                ]
            }
        }
    ]


def test_delete_documents_rejects_empty_scope():
    store = _make_store(FakeCollection(get_result={"ids": []}))

    with pytest.raises(ValueError, match="where_filter is required"):
        store.delete_documents({})
