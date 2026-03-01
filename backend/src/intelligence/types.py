"""
Types for intelligence (RAG + rules) layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


@dataclass
class ContextDocument:
    doc_id: str
    source: str
    title: str
    url: str
    published_at: datetime
    team_tags: List[str]
    player_tags: List[str]
    content: str


class RiskSignal(BaseModel):
    id: str
    label: str
    severity: Literal["low", "medium", "high"]
    rationale: str


class Citation(BaseModel):
    title: str
    url: str
    source: str
    published_at: str
    snippet: str
    quality_score: Optional[float] = None
    freshness_hours: Optional[float] = None
    is_stale: bool = False
    is_noisy: bool = False


class SourceQuality(BaseModel):
    source: str
    docs_used: int
    avg_quality_score: float
    avg_freshness_hours: Optional[float] = None
    fresh_docs: int = 0
    stale_docs: int = 0
    noisy_docs: int = 0


class FeedHealth(BaseModel):
    source: str
    status: Literal["ok", "empty", "error"]
    items_fetched: int = 0
    latency_ms: Optional[int] = None
    error: Optional[str] = None


class RetrievalStats(BaseModel):
    docs_considered: int = 0
    docs_used: int = 0
    freshness_window_hours: int = 0
    source_quality: List[SourceQuality] = Field(default_factory=list)


class GameIntelligenceResponse(BaseModel):
    game_id: str
    season: str
    generated_at: str
    summary: str
    risk_signals: List[RiskSignal] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    retrieval: RetrievalStats
    coverage_status: Literal["sufficient", "insufficient"]
    feed_health: List[FeedHealth] = Field(default_factory=list)


class BriefItem(BaseModel):
    game_id: str
    matchup: str
    summary: str
    risk_level: Literal["low", "medium", "high"]
    citation_count: int


class DailyBriefResponse(BaseModel):
    date: str
    season: str
    items: List[BriefItem] = Field(default_factory=list)
