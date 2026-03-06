"""
Phase 7 evaluation harness for chatbot engine comparison.

Usage:
  cd backend
  PYTHONPATH=. venv/bin/python src/intelligence/chat_eval.py --output data/chat_eval_phase7.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# Force offline-safe tracing behavior for local/sandbox eval runs.
os.environ.setdefault("LANGFUSE_ENABLED", "false")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")
os.environ.setdefault("GEMINI_API_KEY", "")
os.environ.setdefault("RAG_COLLECTION", "nba_context_eval_offline")
os.environ.setdefault("RAG_CHROMA_DIR", "data/chroma_eval")

from sqlalchemy import text

from src.data.db import SessionLocal
from src.intelligence.chat_service import ChatService, IntentRouter
from src.intelligence.langgraph_chat_service import LangGraphChatService


@dataclass
class EvalCase:
    name: str
    message: str
    expected_intent: str
    must_include_any: List[str]


CASES: List[EvalCase] = [
    EvalCase(
        name="db_team_win_rate",
        message="Which NBA team has the best win rate this season?",
        expected_intent="db",
        must_include_any=["win", "rate", "team", "season"],
    ),
    EvalCase(
        name="rag_injury_context",
        message="Any injury updates for tonight's games?",
        expected_intent="rag",
        must_include_any=["injury", "context", "recent", "source"],
    ),
    EvalCase(
        name="off_topic_guard",
        message="Give me a pasta recipe with mushrooms.",
        expected_intent="off_topic",
        must_include_any=["sports analytics", "sports"],
    ),
]


def _passes_contains(reply: str, tokens: List[str]) -> bool:
    lower = (reply or "").lower()
    return any(token.lower() in lower for token in tokens)


def _safe_reply(engine_name: str, fn, message: str) -> tuple[str, str | None]:
    try:
        return str(fn(message, history=[])), None
    except Exception as exc:
        return "", f"{engine_name} error: {str(exc)[:220]}"


def run_eval() -> Dict:
    db = SessionLocal()
    try:
        db_available = True
        db_error = None
        try:
            db.execute(text("SELECT 1"))
        except Exception as exc:
            db_available = False
            db_error = str(exc)[:220]

        legacy = ChatService(db=db, sport="nba")
        graph = LangGraphChatService(db=db, sport="nba")

        rows = []
        for case in CASES:
            intent = IntentRouter.route(case.message)
            if not db_available and case.expected_intent == "db":
                legacy_reply, graph_reply = "", ""
                legacy_error = "legacy skipped: db unavailable"
                graph_error = "langgraph skipped: db unavailable"
            else:
                legacy_reply, legacy_error = _safe_reply("legacy", legacy.reply, case.message)
                graph_reply, graph_error = _safe_reply("langgraph", graph.reply, case.message)
            rows.append(
                {
                    "case": case.name,
                    "message": case.message,
                    "expected_intent": case.expected_intent,
                    "detected_intent": intent,
                    "intent_match": intent == case.expected_intent,
                    "legacy_reply_len": len(legacy_reply or ""),
                    "langgraph_reply_len": len(graph_reply or ""),
                    "legacy_contains_signal": _passes_contains(legacy_reply, case.must_include_any),
                    "langgraph_contains_signal": _passes_contains(graph_reply, case.must_include_any),
                    "langgraph_engine_active": graph.active_engine,
                    "legacy_error": legacy_error,
                    "langgraph_error": graph_error,
                }
            )

        return {
            "generated_at": datetime.now(tz=timezone.utc).isoformat(),
            "cases_total": len(rows),
            "db_available": db_available,
            "db_error": db_error,
            "results": rows,
        }
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Phase 7 chatbot evaluation harness.")
    parser.add_argument(
        "--output",
        default="data/chat_eval_phase7.json",
        help="Path to JSON output report (default: data/chat_eval_phase7.json)",
    )
    args = parser.parse_args()

    report = run_eval()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"saved_to": str(out_path), "cases_total": report["cases_total"]}))


if __name__ == "__main__":
    main()
