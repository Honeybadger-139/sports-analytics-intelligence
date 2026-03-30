"""
TensorFlow training pipeline for NBA game prediction.

Matches the existing sklearn-compatible trainer interface.
Uses EarlyStopping and ReduceLROnPlateau.
"""

import logging
import numpy as np
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    from src.models.tf_model import NBAWideDeepPredictor
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not installed.")

class TFTrainer:
    def __init__(self, n_epochs: int = 100, patience: int = 15, batch_size: int = 64, learning_rate: float = 1e-3, n_splits: int = 3):
        if not TF_AVAILABLE:
            raise ImportError("TensorFlow required: pip install tensorflow")
        self.n_epochs = n_epochs
        self.patience = patience
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.n_splits = n_splits
        self.scaler = StandardScaler()
        self.predictor = None

    def train(self, X: np.ndarray, y: np.ndarray, home_team_ids: np.ndarray, away_team_ids: np.ndarray) -> Dict[str, Any]:
        logger.info(f"TFTrainer: starting training on {len(X)} samples")
        X_scaled = self.scaler.fit_transform(X)
        
        tscv = TimeSeriesSplit(n_splits=self.n_splits)
        cv_aucs = []
        
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X_scaled)):
            X_tr, X_val = X_scaled[train_idx], X_scaled[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]
            h_tr, a_tr = home_team_ids[train_idx], away_team_ids[train_idx]
            h_val, a_val = home_team_ids[val_idx], away_team_ids[val_idx]
            
            fold_pred = NBAWideDeepPredictor(n_features=X_scaled.shape[1])
            acc, auc = self._train_single_model(fold_pred.model, X_tr, y_tr, h_tr, a_tr, X_val, y_val, h_val, a_val)
            cv_aucs.append(auc)
            logger.info(f"Fold {fold + 1} AUC-ROC: {auc:.4f}")
            
        # Final train on all data
        self.predictor = NBAWideDeepPredictor(n_features=X_scaled.shape[1])
        # Use a nominal 10% validation split for early stopping on full dataset
        split_idx = int(len(X_scaled) * 0.9)
        self._train_single_model(self.predictor.model, 
                                 X_scaled[:split_idx], y[:split_idx], home_team_ids[:split_idx], away_team_ids[:split_idx],
                                 X_scaled[split_idx:], y[split_idx:], home_team_ids[split_idx:], away_team_ids[split_idx:])

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
            "n_epochs_trained": self.n_epochs
        }
        logger.info(f"TF Wide&Deep final: accuracy={metrics['accuracy']:.4f} auc={metrics['auc_roc']:.4f}")
        return metrics

    def _train_single_model(self, model, X_tr, y_tr, h_tr, a_tr, X_val, y_val, h_val, a_val):
        model.compile(
            optimizer=tf.keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss="binary_crossentropy",
            metrics=["accuracy", tf.keras.metrics.AUC(name="auc")]
        )
        early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_auc", mode="max", patience=self.patience, restore_best_weights=True)
        lr_reduce = tf.keras.callbacks.ReduceLROnPlateau(monitor="val_auc", mode="max", factor=0.5, patience=5)
        
        hist = model.fit(
            {"dense_features": X_tr, "home_team_id": h_tr, "away_team_id": a_tr}, y_tr,
            validation_data=({"dense_features": X_val, "home_team_id": h_val, "away_team_id": a_val}, y_val),
            batch_size=self.batch_size,
            epochs=self.n_epochs,
            callbacks=[early_stop, lr_reduce],
            verbose=0
        )
        val_acc = max(hist.history["val_accuracy"])
        val_auc = max(hist.history["val_auc"])
        return val_acc, val_auc

    def _predict_proba_internal(self, X_scaled, h_ids, a_ids):
        preds = self.predictor.model.predict({
            "dense_features": X_scaled,
            "home_team_id": h_ids, 
            "away_team_id": a_ids
        }, verbose=0)
        return preds.flatten()

    def predict_proba(self, X: np.ndarray, home_team_ids: np.ndarray, away_team_ids: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        probs = self._predict_proba_internal(X_scaled, home_team_ids, away_team_ids)
        return np.column_stack([1 - probs, probs])

    def save(self, path: str):
        if self.predictor is None:
            raise RuntimeError("No model to save.")
        import joblib
        model_path = str(path).replace(".pt", "").replace(".keras", "") + ".keras"
        scaler_path = str(path).replace(".pt", "").replace(".keras", "") + "_scaler.joblib"
        self.predictor.save(model_path)
        joblib.dump(self.scaler, scaler_path)
        logger.info(f"TFTrainer saved to {model_path} and {scaler_path}")
