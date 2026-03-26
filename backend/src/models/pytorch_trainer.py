"""
PyTorch training pipeline for NBA game prediction.

WHY A SEPARATE TRAINER CLASS?
-------------------------------
trainer.py handles the sklearn/XGBoost pipeline. Mixing PyTorch training
(DataLoader, backward pass, LR scheduler) into that file would make it a
monolith. Separation keeps each trainer focused on its framework.

The PyTorchTrainer is designed to match the sklearn trainer interface:
  trainer.train(X, y) → metrics dict
  trainer.save(path)
  trainer.load(path)

So trainer.py can call it identically to LogisticRegression.fit().

TRAINING LOOP DESIGN DECISIONS:
  1. TimeSeriesSplit — same split as tree models (no data leakage)
  2. Early stopping — patience=10 to avoid overfitting on ~3K samples
  3. Cosine annealing LR scheduler — better than step decay for small datasets
  4. Gradient clipping — prevents exploding gradients (important with BatchNorm)
  5. ONNX export — makes the model deployable without PyTorch runtime

INTERVIEW ANGLE:
  "I used TimeSeriesSplit for validation — the same strategy as our tree
   models — so comparisons are apples-to-apples. Early stopping prevents
   the NN from memorising training noise on our small dataset (~3K games).
   The cosine annealing scheduler helps the model escape local minima in the
   final training epochs."

Part of: SCR-318 — Module 6.2 PyTorch Neural Network Baseline
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

try:
    import torch
    import torch.nn as nn
    from torch.utils.data import DataLoader, Dataset, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch not installed — PyTorchTrainer unavailable.")


# ── Custom Dataset ────────────────────────────────────────────────────────────


if TORCH_AVAILABLE:
    class NBADataset(Dataset):
        """
        PyTorch Dataset wrapping numpy feature arrays.

        Holds X (features), y (labels), and optional team IDs for embeddings.
        """

        def __init__(
            self,
            X: np.ndarray,
            y: np.ndarray,
            home_team_ids: Optional[np.ndarray] = None,
            away_team_ids: Optional[np.ndarray] = None,
        ) -> None:
            self.X = torch.FloatTensor(X)
            self.y = torch.FloatTensor(y).unsqueeze(1)
            self.home_ids = torch.LongTensor(home_team_ids) if home_team_ids is not None else None
            self.away_ids = torch.LongTensor(away_team_ids) if away_team_ids is not None else None

        def __len__(self) -> int:
            return len(self.X)

        def __getitem__(self, idx: int) -> Tuple:
            h_id = self.home_ids[idx] if self.home_ids is not None else torch.tensor(0)
            a_id = self.away_ids[idx] if self.away_ids is not None else torch.tensor(0)
            return self.X[idx], self.y[idx], h_id, a_id


# ── PyTorch Trainer ───────────────────────────────────────────────────────────


class PyTorchTrainer:
    """
    Training orchestrator for NBAGamePredictor.

    Interface matches sklearn estimators for easy integration into trainer.py.

    Example:
        trainer = PyTorchTrainer(n_epochs=50, patience=10)
        metrics = trainer.train(X_train, y_train)
        prob = trainer.predict_proba(X_test)[:, 1]
    """

    def __init__(
        self,
        n_epochs: int = 100,
        patience: int = 15,
        batch_size: int = 64,
        learning_rate: float = 1e-3,
        dropout: float = 0.3,
        n_splits: int = 3,
        device: Optional[str] = None,
    ) -> None:
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch required: pip install torch>=2.2.0")

        self.n_epochs = n_epochs
        self.patience = patience
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.dropout = dropout
        self.n_splits = n_splits
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        self.model: Optional["NBAGamePredictor"] = None
        self.scaler = StandardScaler()
        self.train_history: List[Dict[str, float]] = []

    # ── Public API ────────────────────────────────────────────────────────────

    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        home_team_ids: Optional[np.ndarray] = None,
        away_team_ids: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """
        Full training run with TimeSeriesSplit cross-validation.

        Returns metrics dict compatible with trainer.py's metrics structure:
            {accuracy, auc_roc, log_loss, brier_score, cv_scores}
        """
        from src.models.pytorch_model import NBAGamePredictor

        logger.info(
            "PyTorchTrainer: starting training on %d samples | device=%s",
            len(X), self.device,
        )

        # Scale features (NNs need normalised inputs; trees don't)
        X_scaled = self.scaler.fit_transform(X)

        # ── Cross-validation (TimeSeriesSplit — matches tree model strategy) ──
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        cv_aucs: List[float] = []

        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_scaled)):
            X_tr, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]
            h_tr = home_team_ids[train_idx] if home_team_ids is not None else None
            a_tr = away_team_ids[train_idx] if away_team_ids is not None else None
            h_val = home_team_ids[val_idx] if home_team_ids is not None else None
            a_val = away_team_ids[val_idx] if away_team_ids is not None else None

            fold_model = NBAGamePredictor(
                n_features=X_scaled.shape[1],
                dropout=self.dropout,
            ).to(self.device)
            fold_auc = self._train_fold(
                fold_model, X_tr, y_tr, X_val, y_val, h_tr, a_tr, h_val, a_val, fold
            )
            cv_aucs.append(fold_auc)
            logger.info("Fold %d AUC-ROC: %.4f", fold + 1, fold_auc)

        # ── Final model training on all data ──────────────────────────────────
        self.model = NBAGamePredictor(
            n_features=X_scaled.shape[1],
            dropout=self.dropout,
        ).to(self.device)
        self._train_fold(
            self.model, X_scaled, y, X_scaled, y,
            home_team_ids, away_team_ids, home_team_ids, away_team_ids,
            fold=-1, is_final=True,
        )

        # ── Compute final metrics ─────────────────────────────────────────────
        from sklearn.metrics import accuracy_score, roc_auc_score, log_loss, brier_score_loss

        y_prob = self._predict_proba_internal(X_scaled, home_team_ids, away_team_ids)
        y_pred = (y_prob >= 0.5).astype(int)

        metrics = {
            "accuracy": float(accuracy_score(y, y_pred)),
            "auc_roc": float(roc_auc_score(y, y_prob)),
            "log_loss": float(log_loss(y, y_prob)),
            "brier_score": float(brier_score_loss(y, y_prob)),
            "cv_auc_mean": float(np.mean(cv_aucs)),
            "cv_auc_std": float(np.std(cv_aucs)),
            "cv_scores": cv_aucs,
            "n_epochs_trained": self.n_epochs,
            "device": str(self.device),
        }
        logger.info(
            "PyTorch MLP final: accuracy=%.4f auc=%.4f cv_auc=%.4f±%.4f",
            metrics["accuracy"], metrics["auc_roc"],
            metrics["cv_auc_mean"], metrics["cv_auc_std"],
        )
        return metrics

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Sklearn-compatible predict_proba — returns (n, 2) array [prob_loss, prob_win]."""
        if self.model is None:
            raise RuntimeError("Model not trained. Call train() first.")
        X_scaled = self.scaler.transform(X)
        probs = self._predict_proba_internal(X_scaled)
        return np.column_stack([1 - probs, probs])

    def save(self, path: str) -> None:
        """Save model + scaler to disk."""
        if self.model is None:
            raise RuntimeError("No model to save.")
        import joblib
        model_path = str(path).replace(".pt", "") + ".pt"
        scaler_path = str(path).replace(".pt", "") + "_scaler.joblib"
        self.model.save(model_path)
        joblib.dump(self.scaler, scaler_path)
        logger.info("PyTorchTrainer saved to %s + %s", model_path, scaler_path)

    def load(self, path: str) -> None:
        """Load model + scaler from disk."""
        import joblib
        from src.models.pytorch_model import NBAGamePredictor
        model_path = str(path).replace(".pt", "") + ".pt"
        scaler_path = str(path).replace(".pt", "") + "_scaler.joblib"
        self.model = NBAGamePredictor.load(model_path)
        self.scaler = joblib.load(scaler_path)
        logger.info("PyTorchTrainer loaded from %s", model_path)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _train_fold(
        self,
        model: "NBAGamePredictor",
        X_tr: np.ndarray,
        y_tr: np.ndarray,
        X_val: np.ndarray,
        y_val: np.ndarray,
        h_tr=None, a_tr=None,
        h_val=None, a_val=None,
        fold: int = 0,
        is_final: bool = False,
    ) -> float:
        """Train a single model for one fold. Returns validation AUC-ROC."""
        from sklearn.metrics import roc_auc_score

        dataset = NBADataset(X_tr, y_tr, h_tr, a_tr)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

        criterion = nn.BCEWithLogitsLoss()
        optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate, weight_decay=1e-4)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer, T_max=self.n_epochs, eta_min=1e-5
        )

        best_val_auc = 0.0
        patience_counter = 0
        best_state = None

        for epoch in range(self.n_epochs):
            # ── Training step ─────────────────────────────────────────────────
            model.train()
            epoch_loss = 0.0
            for batch_x, batch_y, batch_h, batch_a in loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                batch_h = batch_h.to(self.device)
                batch_a = batch_a.to(self.device)

                optimizer.zero_grad()
                logits = model(batch_x, batch_h, batch_a)
                loss = criterion(logits, batch_y)
                loss.backward()
                # Gradient clipping — prevents exploding gradients
                nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
                optimizer.step()
                epoch_loss += loss.item()

            scheduler.step()

            # ── Validation step ───────────────────────────────────────────────
            if not is_final:
                val_probs = self._predict_proba_fold(model, X_val, h_val, a_val)
                try:
                    val_auc = roc_auc_score(y_val, val_probs)
                except Exception:
                    val_auc = 0.5

                if val_auc > best_val_auc:
                    best_val_auc = val_auc
                    best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
                    patience_counter = 0
                else:
                    patience_counter += 1

                if patience_counter >= self.patience:
                    logger.debug("Early stopping at epoch %d (fold %d)", epoch + 1, fold)
                    break

            if (epoch + 1) % 20 == 0:
                logger.debug(
                    "Fold %d | Epoch %d | Loss: %.4f | Best AUC: %.4f",
                    fold, epoch + 1, epoch_loss / max(len(loader), 1), best_val_auc,
                )

        # Restore best weights
        if best_state is not None:
            model.load_state_dict({k: v.to(self.device) for k, v in best_state.items()})

        return best_val_auc

    def _predict_proba_fold(
        self,
        model: "NBAGamePredictor",
        X: np.ndarray,
        h_ids=None,
        a_ids=None,
    ) -> np.ndarray:
        """Internal predict for a fold without scaling (already scaled)."""
        model.eval()
        with torch.no_grad():
            x = torch.FloatTensor(X).to(self.device)
            h = torch.LongTensor(h_ids if h_ids is not None else np.zeros(len(X), dtype=int)).to(self.device)
            a = torch.LongTensor(a_ids if a_ids is not None else np.zeros(len(X), dtype=int)).to(self.device)
            logits = model(x, h, a)
            probs = torch.sigmoid(logits).cpu().numpy().flatten()
        return probs

    def _predict_proba_internal(
        self,
        X_scaled: np.ndarray,
        h_ids=None,
        a_ids=None,
    ) -> np.ndarray:
        return self._predict_proba_fold(self.model, X_scaled, h_ids, a_ids)

    def export_onnx(self, path: str, n_features: int = N_FEATURES) -> None:
        """
        Export model to ONNX format for deployment without PyTorch runtime.

        WHY ONNX?
          - Cloud Run containers can run onnxruntime (much smaller than PyTorch)
          - ONNX models load ~10x faster than PyTorch checkpoints
          - Enables TensorRT optimisation on GPU instances
        """
        if self.model is None:
            raise RuntimeError("No model to export.")
        try:
            dummy_x = torch.zeros(1, n_features)
            dummy_h = torch.zeros(1, dtype=torch.long)
            dummy_a = torch.zeros(1, dtype=torch.long)
            torch.onnx.export(
                self.model,
                (dummy_x, dummy_h, dummy_a),
                path,
                input_names=["features", "home_team_id", "away_team_id"],
                output_names=["logit"],
                dynamic_axes={
                    "features": {0: "batch"},
                    "home_team_id": {0: "batch"},
                    "away_team_id": {0: "batch"},
                    "logit": {0: "batch"},
                },
                opset_version=17,
            )
            logger.info("ONNX model exported to %s", path)
        except Exception as exc:
            logger.warning("ONNX export failed: %s", exc)


# Keep N_FEATURES accessible for other modules
try:
    from src.models.pytorch_model import N_FEATURES
except ImportError:
    N_FEATURES = 24
