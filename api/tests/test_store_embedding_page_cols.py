"""Supabase store_embedding tolerates missing page columns."""

from unittest.mock import MagicMock

import pytest

from app.models import AIEngineType, Embedding
from app.storage import SupabaseStorage


def _emb(**kwargs) -> Embedding:
    base = dict(
        embedding_id="emb_1",
        data_id="data_1",
        data_version=1,
        version_label="v1",
        user_id="user_1",
        ai_engine=AIEngineType.GEMINI,
        model="text-embedding-004",
        dimensions=3,
        chunk_index=0,
        chunk_text="hello",
        vector=[0.1, 0.2, 0.3],
        created_at="2026-01-01T00:00:00Z",
        page=2,
        embedding_kind="body",
    )
    base.update(kwargs)
    return Embedding(**base)


@pytest.fixture
def storage(monkeypatch):
    monkeypatch.setattr("app.storage.config.is_ai_enabled", lambda: True)
    s = object.__new__(SupabaseStorage)
    s._embedding_page_cols_ok = None
    client = MagicMock()
    s._supa_client_instance = client
    return s, client


class TestStoreEmbeddingPageColumns:
    def test_retries_without_page_when_column_missing(self, storage):
        storage, client = storage
        table = client.table.return_value
        upsert = table.upsert.return_value
        upsert.execute.side_effect = [
            Exception("Could not find the 'page' column of 'mem_dog_embeddings' in the schema cache"),
            MagicMock(),
        ]

        storage.store_embedding(_emb())

        assert upsert.execute.call_count == 2
        first_payload = table.upsert.call_args_list[0].args[0]
        second_payload = table.upsert.call_args_list[1].args[0]
        assert "page" in first_payload
        assert "page" not in second_payload
        assert storage._embedding_page_cols_ok is False

    def test_skips_page_after_probe_fails(self, storage):
        storage, client = storage
        storage._embedding_page_cols_ok = False
        table = client.table.return_value
        table.upsert.return_value.execute.return_value = MagicMock()

        storage.store_embedding(_emb())

        payload = table.upsert.call_args.args[0]
        assert "page" not in payload
        assert table.upsert.return_value.execute.call_count == 1
