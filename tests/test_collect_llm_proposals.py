"""Batch LLM dùng backend thật nhưng kiểm bằng hàm sinh giả, không gọi Groq/MySQL."""

import pytest

from data.queries.queries import QUERIES
from mcp_server.store.proposals import ProposalStore
from scripts import collect_llm_proposals


def _query(query_id):
    return next(item for item in QUERIES if item["id"] == query_id)


def _index(query_id):
    return {
        "type": "index", "table": "orders", "index_name": "idx_orders_status",
        "columns": [{"name": "status", "order": "ASC"}],
        "rationale": "Lọc trạng thái", "target_query_ids": [query_id],
    }


@pytest.mark.asyncio
async def test_batch_skips_saved_query_and_continues_after_error(monkeypatch, tmp_path):
    store = ProposalStore(tmp_path / "q02.sqlite3")
    store.add("q02", _query("q02")["sql"], _index("q02"))
    calls = []

    async def fake_generate(store, query_id, sql):
        calls.append(query_id)
        assert sql == _query(query_id)["sql"]
        if query_id == "q08":
            raise RuntimeError("secret SQL that must not be logged")
        return [store.add(query_id, sql, _index(query_id))]

    monkeypatch.setattr(collect_llm_proposals, "generate_proposals_from_dashboard",
                        fake_generate)
    result = await collect_llm_proposals.collect_many(
        ["q02", "q08", "q19"], tmp_path,
    )

    assert calls == ["q08", "q19"]
    assert result == [
        {"query_id": "q02", "status": "skipped", "proposal_count": 1},
        {"query_id": "q08", "status": "error", "error_type": "RuntimeError"},
        {"query_id": "q19", "status": "ok", "proposal_count": 1},
    ]
    assert "secret" not in str(result)
    assert len(ProposalStore(tmp_path / "q19.sqlite3").recent_proposals()) == 1


@pytest.mark.asyncio
async def test_batch_rejects_unknown_id_before_calling_backend(monkeypatch, tmp_path):
    async def unexpected(*_):
        pytest.fail("backend called")

    monkeypatch.setattr(collect_llm_proposals, "generate_proposals_from_dashboard",
                        unexpected)
    with pytest.raises(ValueError, match="query_id"):
        await collect_llm_proposals.collect_many(["q02", "q99"], tmp_path)
    assert list(tmp_path.iterdir()) == []
