# ML Engine — Learning Notes

> 📌 **Status**: This folder has initial content. Full README will be expanded as we work on Phase 2 enhancements.

## What Is the ML Engine?

The ML Engine is the **prediction brain** of the platform — it takes the features computed by the Data Layer and trains models to predict game outcomes, explain predictions with SHAP, and size bets using the Kelly Criterion.

## Files in This Folder

| File | Topic | Key Concepts |
|------|-------|-------------|
| [model-selection.md](model-selection.md) | **Model Selection** — Why XGBoost + LightGBM ensemble | Baseline vs advanced models, ensemble methods, cross-validation |

## Modules (Covered in Detail Later)

- `trainer.py` — Model training pipeline (Logistic Regression → XGBoost → LightGBM → Ensemble)
- `predictor.py` — Model serving for live predictions
- `explainability.py` — SHAP values for per-prediction feature attribution
- `bet_sizing.py` — Kelly Criterion for optimal stake sizing
