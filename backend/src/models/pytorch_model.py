"""
PyTorch MLP for NBA game outcome prediction.

WHY A NEURAL NETWORK HERE?
---------------------------
The existing model stack is all tree-based (XGBoost, LightGBM, LogReg).
Trees are excellent on tabular data — they don't need feature scaling,
handle missing values, and are fast to train.

BUT neural networks bring two things trees can't easily do:
  1. Entity embeddings — learn a dense vector for each team that captures
     team identity (style, arena, roster composition) in a learnable way
  2. Sequence modelling — later (Module 6.5), we'll build an LSTM on top
     of these embeddings for time-series forecasting

So this MLP is step 1 of a progression. By itself, it WON'T beat XGBoost
on raw tabular features. But the embedding layer becomes the foundation
for the LSTM in Module 6.5.

ARCHITECTURE: 24 → 64 → 32 → 16 → 1
  - Input: 24 engineered features (same FEATURE_COLUMNS as tree models)
  - Hidden: 3 layers with BatchNorm + ReLU + Dropout(0.3)
  - Output: sigmoid → win probability

INTERVIEW ANGLE:
  Junior:  "NNs beat trees on everything"
  Senior:  "On tabular data with ~3K training examples, a well-tuned
            XGBoost ensemble will usually beat an MLP. I built this NN
            to: (a) document the comparison, (b) add entity embeddings for
            team identity, and (c) serve as the encoder backbone for the
            time-series LSTM in Module 6.5."

  Awe moment: "The entity embedding layer learns that 'Lakers vs Warriors'
               encodes stylistic matchup information that win-rate features
               can't fully capture."

Part of: SCR-318 — Module 6.2 PyTorch Neural Network Baseline
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# ── PyTorch import guard ──────────────────────────────────────────────────────
# Torch is an optional dependency — if not installed, we log a warning
# and the model gracefully degrades. The rest of the platform keeps working.

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning(
        "PyTorch not installed. pytorch_model.py will be unavailable. "
        "Install with: pip install torch>=2.2.0"
    )


# Feature count must match FEATURE_COLUMNS in trainer.py
N_FEATURES = 24
# Number of unique NBA teams (30 teams + 1 for unknown/padding)
N_TEAMS = 31
# Entity embedding dimension — small enough to avoid overfitting on 30 teams
TEAM_EMBED_DIM = 8


class NBAGamePredictor(nn.Module if TORCH_AVAILABLE else object):
    """
    MLP for predicting NBA game outcomes.

    Architecture:
        [tabular features (24)] + [home_team embedding (8)] + [away_team embedding (8)]
        → BatchNorm → 64 → 32 → 16 → 1 (sigmoid)

    The entity embedding layers are the key addition over a vanilla MLP.
    They learn a dense representation of each team that the linear layers
    can use to model team-specific effects.

    Usage (inference):
        model = NBAGamePredictor.load("models/pytorch_mlp_v1.pt")
        prob = model.predict_proba(features_array)  # → float [0, 1]
    """

    def __init__(
        self,
        n_features: int = N_FEATURES,
        n_teams: int = N_TEAMS,
        embed_dim: int = TEAM_EMBED_DIM,
        hidden_dims: tuple = (64, 32, 16),
        dropout: float = 0.3,
    ) -> None:
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required. pip install torch>=2.2.0")
        super().__init__()

        self.n_features = n_features
        self.embed_dim = embed_dim

        # ── Entity embeddings ─────────────────────────────────────────────────
        # Two separate embedding tables: home team and away team
        # Each learns independently because home/away context differs
        self.home_embed = nn.Embedding(n_teams, embed_dim, padding_idx=0)
        self.away_embed = nn.Embedding(n_teams, embed_dim, padding_idx=0)

        # ── Input size: tabular features + 2 team embeddings ──────────────────
        input_dim = n_features + 2 * embed_dim  # 24 + 8 + 8 = 40

        # ── MLP body ──────────────────────────────────────────────────────────
        layers = []
        layers.append(nn.BatchNorm1d(input_dim))

        prev_dim = input_dim
        for h_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.ReLU(),
                nn.Dropout(dropout),
            ])
            prev_dim = h_dim

        # Output layer — no activation (applied at loss/inference time)
        layers.append(nn.Linear(prev_dim, 1))

        self.mlp = nn.Sequential(*layers)

        # ── Weight initialisation ─────────────────────────────────────────────
        self._init_weights()

    def _init_weights(self) -> None:
        """Xavier uniform for linear layers (good default for sigmoid output)."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0.0, std=0.01)

    def forward(
        self,
        x: "torch.Tensor",
        home_team_id: Optional["torch.Tensor"] = None,
        away_team_id: Optional["torch.Tensor"] = None,
    ) -> "torch.Tensor":
        """
        Forward pass.

        Args:
            x: (batch, n_features) — tabular engineered features
            home_team_id: (batch,) int tensor — home team index
            away_team_id: (batch,) int tensor — away team index

        Returns:
            (batch, 1) logits (apply sigmoid for probabilities)
        """
        parts = [x]

        if home_team_id is not None:
            parts.append(self.home_embed(home_team_id))
        else:
            # Zero embedding when team IDs not available (fallback mode)
            zeros = torch.zeros(x.size(0), self.embed_dim, device=x.device)
            parts.append(zeros)

        if away_team_id is not None:
            parts.append(self.away_embed(away_team_id))
        else:
            zeros = torch.zeros(x.size(0), self.embed_dim, device=x.device)
            parts.append(zeros)

        combined = torch.cat(parts, dim=1)
        return self.mlp(combined)

    def predict_proba(
        self,
        features: np.ndarray,
        home_team_id: Optional[int] = None,
        away_team_id: Optional[int] = None,
    ) -> float:
        """
        Convenience inference method matching sklearn's predict_proba interface.

        Args:
            features: (n_features,) numpy array (single game)
            home_team_id: integer team index (optional)
            away_team_id: integer team index (optional)

        Returns:
            Home team win probability as float [0.0, 1.0]
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch not available")

        self.eval()
        with torch.no_grad():
            x = torch.FloatTensor(features).unsqueeze(0)
            h_id = torch.LongTensor([home_team_id or 0])
            a_id = torch.LongTensor([away_team_id or 0])
            logit = self.forward(x, h_id, a_id)
            prob = torch.sigmoid(logit).item()
        return float(prob)

    def save(self, path: str) -> None:
        """Save model state dict to disk."""
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch not available")
        torch.save(
            {
                "state_dict": self.state_dict(),
                "config": {
                    "n_features": self.n_features,
                    "embed_dim": self.embed_dim,
                    "n_teams": self.home_embed.num_embeddings,
                },
            },
            path,
        )
        logger.info("NBAGamePredictor saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "NBAGamePredictor":
        """Load model from disk."""
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch not available")
        checkpoint = torch.load(path, map_location="cpu", weights_only=True)
        cfg = checkpoint.get("config", {})
        model = cls(
            n_features=cfg.get("n_features", N_FEATURES),
            n_teams=cfg.get("n_teams", N_TEAMS),
            embed_dim=cfg.get("embed_dim", TEAM_EMBED_DIM),
        )
        model.load_state_dict(checkpoint["state_dict"])
        model.eval()
        logger.info("NBAGamePredictor loaded from %s", path)
        return model


# ── Team index registry ───────────────────────────────────────────────────────
# Maps team names to stable integer IDs for the embedding layer.
# Index 0 is reserved for unknown/padding.

NBA_TEAM_INDEX: dict[str, int] = {
    "atlanta hawks": 1, "boston celtics": 2, "brooklyn nets": 3,
    "charlotte hornets": 4, "chicago bulls": 5, "cleveland cavaliers": 6,
    "dallas mavericks": 7, "denver nuggets": 8, "detroit pistons": 9,
    "golden state warriors": 10, "houston rockets": 11, "indiana pacers": 12,
    "los angeles clippers": 13, "los angeles lakers": 14, "memphis grizzlies": 15,
    "miami heat": 16, "milwaukee bucks": 17, "minnesota timberwolves": 18,
    "new orleans pelicans": 19, "new york knicks": 20, "oklahoma city thunder": 21,
    "orlando magic": 22, "philadelphia 76ers": 23, "phoenix suns": 24,
    "portland trail blazers": 25, "sacramento kings": 26, "san antonio spurs": 27,
    "toronto raptors": 28, "utah jazz": 29, "washington wizards": 30,
}


def get_team_id(team_name: str) -> int:
    """Return stable team index for embedding lookup. 0 = unknown."""
    return NBA_TEAM_INDEX.get(str(team_name).lower().strip(), 0)
