# PyTorch Neural Networks Deep Dive

> **Module**: Phase 6.2 — SCR-318
> **Project**: Sports Analytics Intelligence Platform
> **Date**: 2026-03-26

---

## What Is It?

**PyTorch** is a deep learning framework that lets you:
1. Define neural network architectures as Python classes (`nn.Module`)
2. Compute gradients automatically via `autograd`
3. Train models with mini-batch gradient descent
4. Export to ONNX for production deployment without the PyTorch runtime

**The progression in this platform**:
```
Logistic Regression → XGBoost → LightGBM → [PyTorch MLP] → LSTM (Module 6.5)
```

The MLP here is NOT meant to win. It's meant to:
- Show you understand tabular vs deep learning trade-offs
- Add entity embeddings that the LSTM needs in Module 6.5
- Document the comparison honestly (trees beat NNs on tabular data)

---

## Why Does It Matter?

65% of DS/ML job postings require PyTorch or TensorFlow.

But more importantly, interviewers test **judgment**:
- *"When would you use a neural network instead of XGBoost?"*
- A junior says "NNs are more powerful"
- A senior says "On tabular data with <50K samples, XGBoost wins. NNs start winning with images, text, sequences, or when you need embeddings for categorical variables with high cardinality."

---

## How Does It Work? (Intuition)

### MLP Architecture

```
Input (24 features)
  + home_team_embedding (8 dims)   ← learned team representation
  + away_team_embedding (8 dims)   ← learned team representation
= 40-dim input
    │
    ▼
BatchNorm(40) → Linear(40→64) → BatchNorm(64) → ReLU → Dropout(0.3)
    │
    ▼
Linear(64→32) → BatchNorm(32) → ReLU → Dropout(0.3)
    │
    ▼
Linear(32→16) → BatchNorm(16) → ReLU → Dropout(0.3)
    │
    ▼
Linear(16→1) → sigmoid → win probability
```

### Why BatchNorm?
Normalises each mini-batch's activations. Prevents gradient vanishing/explosion. Lets you use higher learning rates.

### Why Dropout(0.3)?
Randomly zeroes 30% of neurons during training. Forces the network to learn redundant representations. Reduces overfitting — critical with only ~3K training samples.

### Why Cosine Annealing LR?
Learning rate starts at 1e-3, smoothly decays to 1e-5 following a cosine curve. Better than step decay (no abrupt drops). Helps escape local minima in the final epochs.

### Entity Embeddings

The key innovation over a vanilla MLP:

```python
self.home_embed = nn.Embedding(31, 8)  # 30 teams + 1 unknown
self.away_embed = nn.Embedding(31, 8)
```

These learn a dense 8-dimensional vector for each team. Unlike one-hot encoding (30 zeros and one 1), embeddings:
- Capture team *similarity* (teams with similar styles end up near each other in embedding space)
- Are the foundation for the LSTM in Module 6.5 (which will encode game sequences using these embeddings)

---

## Trees vs Neural Networks — The Full Picture

| Criterion | XGBoost/LightGBM | PyTorch MLP |
|-----------|-----------------|-------------|
| Tabular data (<100K rows) | ✅ Usually wins | ❌ Usually loses |
| Feature engineering | Required | Can learn it |
| Missing values | Native support | Needs imputation |
| Training time | Seconds | Minutes |
| Interpretability | SHAP values | Harder (Grad-CAM, LIME) |
| Categorical high-cardinality | One-hot (bloats) | Embeddings (compact) |
| Sequential data | ❌ | ✅ LSTM/Transformer |
| Image/text | ❌ | ✅ CNN/BERT |
| Transfer learning | ❌ | ✅ Fine-tune pretrained |

**Our result**: On ~3K NBA games, XGBoost AUC ≈ 0.70+, MLP AUC ≈ 0.65-0.68. Trees win. **This is expected and educational.**

---

## Training Pipeline Design

### Why TimeSeriesSplit (not random k-fold)?

```
❌ Random k-fold:  [Apr '24 game] → train set, [Jan '24 game] → val set
   Problem: Model sees future data during training → inflated metrics

✅ TimeSeriesSplit: [games 1-600] → train, [games 601-800] → val
   Mimics production: always train on past, validate on future
```

### Early Stopping (patience=15)
If validation AUC doesn't improve for 15 epochs, stop. Restores best weights.
Without this, the model memorises training noise — especially bad with 3K samples.

### Gradient Clipping (`max_norm=1.0`)
Clips gradient magnitude to 1.0. Prevents "exploding gradients" where a single bad batch sends weights to infinity. Combined with BatchNorm, this makes training very stable.

### ONNX Export
```python
torch.onnx.export(model, (dummy_x, dummy_h, dummy_a), "model.onnx", opset_version=17)
```
Cloud Run containers don't need PyTorch installed — just `onnxruntime` (50MB vs 2GB). ONNX inference is also 3-5x faster than PyTorch CPU inference.

---

## Interview Questions

### Q1: Why did XGBoost beat your neural network?

**Junior**: "I need to tune it more"
**Senior**: "Expected and intentional. On tabular data with 3K samples, tree-based models have an inductive bias that aligns with structured features: they implicitly handle monotonic relationships, feature interactions, and don't need normalisation. NNs have more parameters to fit with less data. The cross-entropy loss surface for an MLP on 3K samples has many local minima. XGBoost's sequential boosting is more data-efficient for this regime. The NN's value comes from entity embeddings and serving as the encoder backbone for the time-series LSTM."

### Q2: What is BatchNorm and why did you use it?

**Senior**: "BatchNorm normalises each feature across the mini-batch to zero mean and unit variance, then applies learnable scale and shift parameters. This: (1) reduces internal covariate shift, letting each layer train more independently; (2) acts as a regulariser (similar to dropout); (3) allows higher learning rates without divergence. Without it, deep MLPs are sensitive to initialisation and often fail to train on small datasets."

### Q3: How do entity embeddings improve on one-hot encoding?

**Senior**: "One-hot encoding for 30 teams gives a 30-dimensional sparse vector with no notion of similarity. Entity embeddings learn a dense 8-dimensional vector for each team jointly with the rest of the network. After training, similar teams (e.g. fast-paced offensive teams) end up near each other in embedding space. More importantly, they transfer — I'll use these same embeddings as input features for the LSTM in Module 6.5, meaning the NN has already learned team representations that the sequence model can exploit."

### Q4: How would you deploy this PyTorch model to production?

**Senior**: "Two paths: (1) Export to ONNX and serve with onnxruntime — no PyTorch dependency in the container, faster inference, smaller Docker image. (2) TorchServe or Triton Inference Server for high-throughput scenarios. We currently use path (1) — the ONNX export is built into `PyTorchTrainer.export_onnx()`. The existing predictor.py already uses onnxruntime, so integrating the PyTorch model required zero changes to the inference path."

---

## "Awe Moment" Insights

**1. The comparison is the product**
Most DS interviews ask "which model did you use?" The better question is "how did you compare models?". Our trainer runs LR + XGBoost + LightGBM + PyTorch MLP with the same TimeSeriesSplit, same metrics, same data. The comparison table is the output — not just the winning model.

**2. Graceful degradation**
The `train_pytorch_mlp()` function returns `None` if PyTorch isn't installed. The pipeline continues with tree models. This is production thinking: optional dependencies should never break the system.

**3. Embeddings as cross-module currency**
The `NBA_TEAM_INDEX` dict in `pytorch_model.py` is used by both the MLP and the LSTM in Module 6.5. The embedding weights learned by the MLP can be frozen and reused — transfer learning within our own platform.

---

## Files Created (SCR-318)

| File | Purpose |
|------|---------|
| `backend/src/models/pytorch_model.py` | `NBAGamePredictor` MLP + entity embeddings |
| `backend/src/models/pytorch_trainer.py` | `PyTorchTrainer` with TimeSeriesSplit + early stopping + ONNX export |
| `backend/src/models/trainer.py` | Modified: added `train_pytorch_mlp()` + ensemble integration |
| `backend/requirements.txt` | Added: `torch>=2.2.0`, `tensorboard>=2.16.0` |

---

## Next Module

**6.3 Multi-Agent System** (SCR-319) — now that LangChain tools exist (from 6.1), build a supervisor agent that routes complex queries across specialist agents: StatsAgent, NewsAgent, PredictionAgent.
