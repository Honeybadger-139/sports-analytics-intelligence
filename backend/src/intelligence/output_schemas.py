"""
Pydantic structured output schemas for LangChain tool responses.

WHY STRUCTURED OUTPUT?
----------------------
Raw LLM text is fragile — it breaks parsers when format changes.
Pydantic schemas give us:
  1. Type safety — field types are enforced at validation time
  2. Defaults — partial LLM responses don't crash the system
  3. Serialization — .model_dump() → JSON for API responses
  4. Documentation — schema doubles as API contract

INTERVIEW ANGLE:
  Junior:  "I parse LLM responses with regex"
  Senior:  "I use Pydantic-validated structured output so the graph can
            pass typed objects between nodes — no string parsing, no surprises."

Part of: SCR-317 — Module 6.1 LangChain/LangGraph Enhancement
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Tool Output Schemas ───────────────────────────────────────────────────────


class KeyFactor(BaseModel):
    """A single factor influencing a game outcome."""

    factor: str = Field(description="Factor name, e.g. 'home_court_advantage'")
    value: float = Field(description="SHAP-like importance value, higher = more impactful")
    direction: str = Field(
        default="positive",
        description="'positive' = favours home team, 'negative' = favours away team",
    )

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, v: str) -> str:
        if v not in ("positive", "negative", "neutral"):
            return "neutral"
        return v


class GameAnalysis(BaseModel):
    """
    Structured output for game prediction + analysis.

    Returned by PredictionTool and ExplainabilityTool.
    Maps directly to the ChatResponse.key_numbers field.
    """

    home_team: str = Field(description="Home team name")
    away_team: str = Field(description="Away team name")
    home_win_probability: float = Field(
        ge=0.0, le=1.0, description="Predicted probability of home team winning"
    )
    away_win_probability: float = Field(
        ge=0.0, le=1.0, description="Predicted probability of away team winning"
    )
    confidence: float = Field(
        default=0.6, ge=0.0, le=1.0, description="Model confidence (ensemble agreement)"
    )
    key_factors: List[KeyFactor] = Field(
        default_factory=list, description="Top factors driving the prediction"
    )
    narrative: str = Field(
        default="", description="1-3 sentence plain-language explanation of the prediction"
    )
    model_version: Optional[str] = Field(default=None, description="Which model produced this")

    @field_validator("home_win_probability", "away_win_probability", mode="before")
    @classmethod
    def clamp_probability(cls, v: Any) -> float:
        try:
            f = float(v)
            return max(0.0, min(1.0, f))
        except (TypeError, ValueError):
            return 0.5


class StatsSummary(BaseModel):
    """
    Structured output for team/player statistics queries.

    Returned by SQLQueryTool and TeamStatsTool.
    Designed to feed the frontend table renderer.
    """

    metric_name: str = Field(description="Human-readable metric name, e.g. 'Points Per Game'")
    value: float = Field(description="Numeric metric value")
    unit: str = Field(default="", description="Unit label, e.g. 'pts/game', '%', 'games'")
    trend: str = Field(
        default="stable",
        description="'up', 'down', or 'stable' compared to prior 10 games",
    )
    context: str = Field(
        default="", description="Brief context — league rank, percentile, comparison"
    )
    team: Optional[str] = Field(default=None, description="Team this stat belongs to")
    season: str = Field(default="2025-26", description="Season identifier")
    rows: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Raw SQL result rows for table rendering",
    )

    @field_validator("trend")
    @classmethod
    def validate_trend(cls, v: str) -> str:
        if v not in ("up", "down", "stable"):
            return "stable"
        return v


class Citation(BaseModel):
    """A single source document citation."""

    title: str = Field(description="Article or document title")
    url: str = Field(default="", description="Source URL if available")
    source: str = Field(default="unknown", description="Source name, e.g. 'ESPN', 'NBA.com'")
    relevance_score: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Cosine similarity score from vector search"
    )


class RAGResponse(BaseModel):
    """
    Structured output for RAG (news/injury/context) queries.

    Returned by RAGRetrieverTool.
    Feeds the ChatResponse.sources field.
    """

    answer: str = Field(description="LLM-synthesised answer grounded in retrieved context")
    citations: List[Citation] = Field(
        default_factory=list, description="Source documents used to generate the answer"
    )
    confidence: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Retrieval quality score — high when many relevant docs found",
    )
    source_quality: str = Field(
        default="medium",
        description="'high' (4+ docs), 'medium' (2-3 docs), 'low' (0-1 docs)",
    )
    docs_retrieved: int = Field(default=0, description="Number of documents retrieved")

    @field_validator("source_quality")
    @classmethod
    def validate_source_quality(cls, v: str) -> str:
        if v not in ("high", "medium", "low"):
            return "medium"
        return v

    @classmethod
    def from_retrieval(cls, answer: str, docs: List[Dict[str, Any]], meta: Dict[str, Any]) -> "RAGResponse":
        """Build a RAGResponse from raw retriever output."""
        docs_used = int(meta.get("docs_used", len(docs)))
        if docs_used >= 4:
            quality = "high"
            confidence = 0.9
        elif docs_used >= 2:
            quality = "medium"
            confidence = 0.75
        else:
            quality = "low"
            confidence = 0.4

        citations = [
            Citation(
                title=doc.get("title") or "Source",
                url=doc.get("url") or "",
                source=doc.get("source") or "unknown",
                relevance_score=float(doc.get("score", 0.0)),
            )
            for doc in docs[:5]
        ]
        return cls(
            answer=answer,
            citations=citations,
            confidence=confidence,
            source_quality=quality,
            docs_retrieved=docs_used,
        )


# ── Graph-level Contract ──────────────────────────────────────────────────────


class ToolResult(BaseModel):
    """
    Wrapper returned by any LangChain tool in this system.

    Normalises heterogeneous tool outputs into a single shape
    that graph nodes can unpack without conditional branching.
    """

    tool_name: str = Field(description="Which tool produced this result")
    success: bool = Field(default=True)
    text: str = Field(default="", description="Plain-text answer for LLM context")
    structured: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Typed payload — GameAnalysis, StatsSummary, or RAGResponse dict",
    )
    error: Optional[str] = Field(default=None, description="Error message if success=False")
    latency_ms: Optional[float] = Field(default=None, description="Tool execution latency")
