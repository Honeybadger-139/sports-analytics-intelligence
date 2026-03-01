"""
Unit tests for retrain worker lifecycle handling.
"""

from src.mlops import retrain_worker as retrain_worker_module


class _FakeDB:
    def get_bind(self):
        return object()


def test_worker_simulate_mode_completes_job(monkeypatch):
    monkeypatch.setattr(
        retrain_worker_module,
        "claim_next_retrain_job",
        lambda engine, season=None: {"id": 7, "season": "2025-26", "status": "running"},
    )
    monkeypatch.setattr(
        retrain_worker_module,
        "finalize_retrain_job",
        lambda engine, job_id, status, run_details=None, error=None: {
            "id": job_id,
            "season": "2025-26",
            "status": status,
            "error": error,
        },
    )
    monkeypatch.setattr(retrain_worker_module, "record_intelligence_audit", lambda *args, **kwargs: None)

    payload = retrain_worker_module.process_next_retrain_job(_FakeDB(), season="2025-26", execute=False)
    assert payload["status"] == "completed"
    assert payload["job"]["status"] == "completed"
    assert payload["run_details"]["mode"] == "simulate"


def test_worker_noop_when_no_queued_jobs(monkeypatch):
    monkeypatch.setattr(retrain_worker_module, "claim_next_retrain_job", lambda engine, season=None: None)
    payload = retrain_worker_module.process_next_retrain_job(_FakeDB(), season="2025-26", execute=False)
    assert payload["status"] == "noop"
    assert payload["job"] is None


def test_worker_failure_sets_failed_status(monkeypatch):
    monkeypatch.setattr(
        retrain_worker_module,
        "claim_next_retrain_job",
        lambda engine, season=None: {"id": 11, "season": "2025-26", "status": "running"},
    )

    def _raise(*args, **kwargs):
        raise RuntimeError("trainer failed")

    monkeypatch.setattr(retrain_worker_module, "finalize_retrain_job", lambda *args, **kwargs: {
        "id": 11,
        "season": "2025-26",
        "status": kwargs.get("status", "failed"),
        "error": kwargs.get("error"),
    })
    monkeypatch.setattr(retrain_worker_module, "record_intelligence_audit", lambda *args, **kwargs: None)
    # Force execute-mode branch to fail by patching imported trainer call hook.
    monkeypatch.setattr(retrain_worker_module, "_summarize_training_output", _raise)

    # Monkeypatch run_training_pipeline import path by injecting fake module attr call.
    trainer_stub = __import__("types").SimpleNamespace(run_training_pipeline=lambda season: {"ensemble": {}})
    monkeypatch.setitem(__import__("sys").modules, "src.models.trainer", trainer_stub)

    payload = retrain_worker_module.process_next_retrain_job(_FakeDB(), season="2025-26", execute=True)
    assert payload["status"] == "failed"
    assert payload["job"]["status"] == "failed"
