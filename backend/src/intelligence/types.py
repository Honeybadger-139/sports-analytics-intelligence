"""
Types for intelligence (RAG + rules) layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Literal

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


class RetrievalStats(BaseModel):
    docs_considered: int = 0
    docs_used: int = 0
    freshness_window_hours: int = 0


class GameIntelligenceResponse(BaseModel):
    game_id: str
    season: str
    generated_at: str
    summary: str
    risk_signals: List[RiskSignal] = Field(default_factory=list)
    citations: List[Citation] = Field(default_factory=list)
    retrieval: RetrievalStats
    coverage_status: Literal["sufficient", "insufficient"]


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
