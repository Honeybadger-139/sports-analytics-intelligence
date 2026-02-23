# Model Selection & Ensemble Learning

## What Is It?
Model selection is choosing the right ML algorithm for your problem. We don't just pick one — we train multiple and combine them (ensemble) for better performance.

## Why Does It Matter?
- Different models capture different patterns in data
- No single model is best for all problems ("No Free Lunch" theorem)
- Ensembles reduce variance and are more robust to overfitting
- Industry standard: most production ML systems use ensembles

## Our Model Progression

### 1. Logistic Regression (Baseline)
- **What**: Linear classifier using sigmoid function: P(y=1) = 1/(1+e^(-z))
- **Why first**: Establishes baseline. If LR can't beat 50%, features lack signal
- **Strengths**: Interpretable coefficients, calibrated probabilities, fast
- **Weakness**: Can't capture non-linear feature interactions
- **Our result**: 55.9% CV accuracy, 0.542 AUC

### 2. XGBoost (Gradient Boosting)
- **What**: Sequential ensemble of decision trees, each correcting prior errors
- **Analogy**: Team of specialists, each one fixing what the last one missed
- **Key params**: n_estimators (200), max_depth (5), learning_rate (0.1)
- **Why use it**: Handles non-linear relationships, built-in regularization
- **Our result**: 54.3% CV accuracy, 0.545 AUC

### 3. LightGBM (Microsoft's Alternative)
- **What**: Same idea but leaf-wise growth (vs level-wise), histogram splits
- **Why use it**: 10-20x faster than XGBoost on large datasets
- **Key difference**: Leaf-wise = grows most impactful leaf first (asymmetric trees)
- **Our result**: 55.0% CV accuracy, 0.529 AUC

### 4. Weighted Ensemble
- **How**: Average probabilities weighted by CV AUC score
- **Why**: Different models → different error patterns → combination reduces variance
- **Weights**: LR 33.5%, XGBoost 33.7%, LightGBM 32.7%

## Time-Series Cross Validation

**Critical design decision**: We use `TimeSeriesSplit` instead of random k-fold.

```
Random k-fold (WRONG for time-series):
  Train: [Jan, Mar, May]  Test: [Feb, Apr]  ← Future leaks into training!

TimeSeriesSplit (CORRECT):
  Fold 1: Train [Oct-Nov]     Test [Dec]
  Fold 2: Train [Oct-Dec]     Test [Jan]
  Fold 3: Train [Oct-Jan]     Test [Feb]
```

Sports data has temporal dependencies (momentum, injuries, trades). Random splits leak future information.

## SHAP Explainability

**What**: SHapley Additive exPlanations — per-prediction feature attribution from game theory.

**Why SHAP over alternatives**:
| Method | Scope | Theory | Speed |
|--------|-------|--------|-------|
| Feature Importance | Global | Heuristic | Fast |
| Permutation Importance | Global | Statistical | Slow |
| LIME | Local | Approximate | Medium |
| **SHAP** | **Both** | **Axiomatic** | **Medium** |

**Example output**: "BOS wins because: Opp Off Rating (+12%), Home Court (+5%), Recent Form (+3%)"

## Kelly Criterion

**Formula**: f* = (b·p - q) / b
- f* = fraction of bankroll to bet
- b = decimal odds - 1
- p = model probability, q = 1 - p

**Why quarter Kelly**: Full Kelly maximizes growth but has 50%+ drawdowns. Quarter Kelly gives 50% of optimal growth with 75% less variance.

## Interview Questions

1. **"Why not just use the best model?"** → Ensembles reduce variance. Different models make different errors. Combining them gives more robust predictions.

2. **"How do you prevent overfitting?"** → Time-series CV, regularization (L1+L2), early stopping, subsample/colsample.

3. **"What's the difference between bagging and boosting?"** → Bagging (Random Forest): parallel, reduces variance. Boosting (XGBoost): sequential, reduces bias.

4. **"How do you evaluate probability calibration?"** → Brier score, reliability diagrams, log loss. A well-calibrated model saying 70% should win ~70% of the time.

5. **"Why SHAP over feature importance?"** → SHAP provides per-prediction explanations with mathematical guarantees (additivity, consistency). Feature importance is just a global average.

## Senior Manager Perspective
> "We chose an ensemble approach because production reliability matters more than marginal accuracy gains from a single model. The ensemble's robustness to distribution shift (new season, roster changes) justifies the added complexity. SHAP explanations build user trust — without them, the model is a black box that users won't adopt."
