"""
Tests for Langfuse fallback logging behavior.
"""

import json

from src import config
from src.intelligence import langfuse_client


def test_record_generation_writes_jsonl_when_langfuse_disabled(tmp_path, monkeypatch):
    target = tmp_path / "llm_calls.jsonl"
    monkeypatch.setattr(langfuse_client, "_initialized", False)
    monkeypatch.setattr(config, "LLM_FALLBACK_LOG_PATH", target, raising=False)

    langfuse_client.record_generation(
        name="llm.generate.rag",
        prompt="Explain the matchup",
        output="No relevant context found.",
        model="gemini-2.0-flash",
        input_tokens=11,
        output_tokens=6,
        latency_ms=123.4,
        intent="rag",
        success=True,
    )

    payload = json.loads(target.read_text(encoding="utf-8").strip())
    assert payload["model"] == "gemini-2.0-flash"
    assert payload["intent"] == "rag"
    assert payload["latency_ms"] == 123.4
    assert payload["success"] is True
