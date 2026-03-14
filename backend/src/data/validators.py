"""
Ingestion Payload Validators
==============================

Wave 3: All NBA API payloads are validated through Pydantic models before
being written to the database. Any record that fails validation is routed to
the dead-letter store (`failed_ingestion` table) instead of silently dropped
or crashing the pipeline.

🎓 WHY VALIDATE AT INGESTION?
    Data quality problems compound. A game record with a negative score gets
    stored, features are computed from it, models are trained on bad features,
    predictions are wrong. Catching bad data at the source is orders of
    magnitude cheaper than debugging model drift.

    Pattern: Validate → persist valid records → dead-letter invalid records.
    This is the standard approach in data engineering (Kafka, Flink, Spark).

💡 INTERVIEW ANGLE:
    Junior: "I added try/except around the database insert."
    Senior: "I use Pydantic models to validate every incoming payload before
    any DB write. Invalid records are persisted in a dead-letter table with
    the full payload and structured error messages. This gives ops visibility
    into data quality issues without losing records, and the API exposes the
    dead-letter queue for investigation."

Wave 3 — SCR-298
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, field_validator, model_validator


# ── Team Payload ──────────────────────────────────────────────────────────────

class TeamPayload(BaseModel):
    """Validates a team record before upsert."""

    team_id: int = Field(..., gt=0, description="NBA API team ID (must be positive)")
    abbreviation: str = Field(..., min_length=2, max_length=10)
    full_name: str = Field(..., min_length=2, max_length=100)
    city: Optional[str] = Field(default=None, max_length=50)
    conference: Optional[str] = Field(default=None, max_length=10)
    division: Optional[str] = Field(default=None, max_length=20)

    @field_validator("abbreviation")
    @classmethod
    def abbreviation_uppercase(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("conference")
    @classmethod
    def valid_conference(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in {"East", "West", "east", "west", "Eastern", "Western", "E", "W"}:
            # Normalize rather than reject — conferences can vary in format
            pass
        return v


# ── Game Payload ──────────────────────────────────────────────────────────────

class GamePayload(BaseModel):
    """Validates a game/match record before upsert."""

    game_id: str = Field(..., min_length=5, max_length=20)
    game_date: str = Field(..., description="ISO date string YYYY-MM-DD")
    season: str = Field(..., pattern=r"^\d{4}-\d{2}$", description="e.g. 2025-26")
    home_team_id: int = Field(..., gt=0)
    away_team_id: int = Field(..., gt=0)
    home_score: Optional[int] = Field(default=None, ge=0, le=250)
    away_score: Optional[int] = Field(default=None, ge=0, le=250)
    winner_team_id: Optional[int] = Field(default=None, gt=0)
    is_completed: bool = Field(default=False)
    venue: Optional[str] = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def winner_must_be_a_team(self) -> "GamePayload":
        if self.is_completed and self.winner_team_id is not None:
            if self.winner_team_id not in {self.home_team_id, self.away_team_id}:
                raise ValueError(
                    f"winner_team_id={self.winner_team_id} is not home ({self.home_team_id}) "
                    f"or away ({self.away_team_id}) team"
                )
        return self

    @model_validator(mode="after")
    def home_away_different(self) -> "GamePayload":
        if self.home_team_id == self.away_team_id:
            raise ValueError(
                f"home_team_id and away_team_id must differ (got {self.home_team_id})"
            )
        return self


# ── Player Payload ────────────────────────────────────────────────────────────

class PlayerPayload(BaseModel):
    """Validates a player record before upsert."""

    player_id: int = Field(..., gt=0)
    full_name: str = Field(..., min_length=2, max_length=100)
    team_id: Optional[int] = Field(default=None, gt=0)
    position: Optional[str] = Field(default=None, max_length=10)
    is_active: bool = Field(default=True)


# ── Validation helpers ────────────────────────────────────────────────────────

_ENTITY_MAP = {
    "team": TeamPayload,
    "game": GamePayload,
    "player": PlayerPayload,
}


def validate_payload(
    entity_type: str, raw: Dict[str, Any]
) -> Tuple[Optional[BaseModel], List[str]]:
    """
    Validate a raw dict payload against its entity schema.

    Parameters
    ----------
    entity_type : "team" | "game" | "player"
    raw         : raw dict from NBA API or ingestion pipeline

    Returns
    -------
    (validated_model, errors)
        On success: (Pydantic model instance, [])
        On failure: (None, list of error strings)
    """
    schema = _ENTITY_MAP.get(entity_type)
    if schema is None:
        return None, [f"Unknown entity_type: '{entity_type}'"]

    try:
        validated = schema.model_validate(raw)
        return validated, []
    except Exception as exc:
        # Pydantic v2 raises ValidationError; stringify each error cleanly
        errors: List[str] = []
        if hasattr(exc, "errors"):
            for e in exc.errors():
                loc = ".".join(str(x) for x in e.get("loc", []))
                msg = e.get("msg", str(e))
                errors.append(f"{loc}: {msg}" if loc else msg)
        else:
            errors = [str(exc)]
        return None, errors


def validate_batch(
    entity_type: str, records: List[Dict[str, Any]]
) -> Tuple[List[BaseModel], List[Dict[str, Any]]]:
    """
    Validate a batch of records.

    Returns
    -------
    (valid_records, failed_records)
        failed_records items: {"raw": {...}, "errors": [...]}
    """
    valid: List[BaseModel] = []
    failed: List[Dict[str, Any]] = []

    for raw in records:
        model, errors = validate_payload(entity_type, raw)
        if model is not None:
            valid.append(model)
        else:
            failed.append({"raw": raw, "errors": errors})

    return valid, failed
