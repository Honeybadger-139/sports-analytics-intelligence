from src.intelligence.service import IntelligenceService


def test_fallback_summary_contains_matchup_and_rest_profile():
    game = {
        "away_team_name": "New York Knicks",
        "away_team": "NYK",
        "home_team_name": "Charlotte Hornets",
        "home_team": "CHA",
        "home_days_rest": 2,
        "away_days_rest": 1,
    }
    retrieval_stats = {"docs_used": 0, "max_similarity": 0.21}
    risk_signals = []
    feed_health = [{"source": "espn.com", "status": "ok"}]

    summary = IntelligenceService._fallback_matchup_summary(
        game,
        retrieval_stats=retrieval_stats,
        risk_signals=risk_signals,
        max_age_hours=120,
        feed_health=feed_health,
    )

    assert "New York Knicks" in summary
    assert "Charlotte Hornets" in summary
    assert "Rest profile" in summary
    assert "NYK has 1 day(s)" in summary
    assert "CHA has 2 day(s)" in summary


def test_fallback_summary_surfaces_risk_and_feed_errors():
    game = {
        "away_team_name": "Sacramento Kings",
        "away_team": "SAC",
        "home_team_name": "Orlando Magic",
        "home_team": "ORL",
        "home_days_rest": None,
        "away_days_rest": None,
    }
    retrieval_stats = {"docs_used": 0, "max_similarity": 0.15}
    risk_signals = [{"label": "Short Rest / Back-to-Back Risk", "severity": "medium"}]
    feed_health = [{"source": "rotowire.com", "status": "error"}]

    summary = IntelligenceService._fallback_matchup_summary(
        game,
        retrieval_stats=retrieval_stats,
        risk_signals=risk_signals,
        max_age_hours=120,
        feed_health=feed_health,
    )

    assert "Short Rest / Back-to-Back Risk" in summary
    assert "fetch issues" in summary
    assert "threshold" in summary
