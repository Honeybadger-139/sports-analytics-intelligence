"""
TensorFlow Wide & Deep Learning Model for NBA game outcome prediction.

WHY WIDE & DEEP?
----------------
The Wide & Deep architecture (Cheng et al., 2016) replaces our previous PyTorch MLP.
It is the standard for production tabular datasets with a mix of dense continuous
features and highly specific sparse features (like IDs).

1. DEEP COMPONENT: Generalizes using continuous features (Rolling averages, SRS) 
   and dense embeddings.
2. WIDE COMPONENT: Memorizes specific interactions (Home Team vs Away Team exceptions)
   using wide combinations fed directly to the output.

By training both jointly, we mimic how massive recommendation systems (like YouTube
or Google Play) handle tabular feature crosses.

Wait, why not just XGBoost?
Trees are amazing, but they struggle with high-cardinality categorical variables.
This architecture maps those inputs into a learned vector space (embeddings).
"""

import logging
from typing import Optional
import numpy as np

logger = logging.getLogger(__name__)

try:
    import tensorflow as tf
    from tensorflow.keras import layers, models, regularizers
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logger.warning("TensorFlow not installed. tf_model.py will be unavailable.")

N_FEATURES = 24
N_TEAMS = 31  # 30 teams + 1 unknown
TEAM_EMBED_DIM = 8

class NBAWideDeepPredictor:
    """
    TensorFlow Keras model wrapper using the Wide & Deep architecture.
    """
    def __init__(self, n_features: int = N_FEATURES, n_teams: int = N_TEAMS, embed_dim: int = TEAM_EMBED_DIM):
        if not TF_AVAILABLE:
            raise ImportError("TensorFlow is required: pip install tensorflow")
        
        self.n_features = n_features
        self.n_teams = n_teams
        self.embed_dim = embed_dim
        self.model = self._build_model()

    def _build_model(self) -> "tf.keras.Model":
        # 1. Inputs
        features_input = layers.Input(shape=(self.n_features,), name="dense_features")
        home_team_input = layers.Input(shape=(1,), name="home_team_id", dtype=tf.int32)
        away_team_input = layers.Input(shape=(1,), name="away_team_id", dtype=tf.int32)

        # 2. Embeddings (Deep Path)
        # Learn rich dense vectors for teams to generalize team strength
        team_embedding_deep = layers.Embedding(
            input_dim=self.n_teams, 
            output_dim=self.embed_dim, 
            name="team_embedding_deep",
            embeddings_initializer="random_normal"
        )
        home_emb_deep = layers.Flatten()(team_embedding_deep(home_team_input))
        away_emb_deep = layers.Flatten()(team_embedding_deep(away_team_input))

        # 3. Deep Component
        deep_concat = layers.Concatenate(name="deep_concat")([features_input, home_emb_deep, away_emb_deep])
        
        d = layers.BatchNormalization()(deep_concat)
        d = layers.Dense(64, activation="relu", kernel_regularizer=regularizers.l2(1e-4))(d)
        d = layers.Dropout(0.3)(d)
        d = layers.Dense(32, activation="relu", kernel_regularizer=regularizers.l2(1e-4))(d)
        d = layers.Dropout(0.3)(d)
        deep_out = layers.Dense(16, activation="relu")(d)

        # 4. Wide Component (Memorization)
        # Embeddings designed to be fed straight to the linear output layer.
        team_embedding_wide = layers.Embedding(
            input_dim=self.n_teams, 
            output_dim=4, # lower dim for wide
            name="team_embedding_wide"
        )
        home_emb_wide = layers.Flatten()(team_embedding_wide(home_team_input))
        away_emb_wide = layers.Flatten()(team_embedding_wide(away_team_input))
        
        wide_concat = layers.Concatenate(name="wide_concat")([home_emb_wide, away_emb_wide])
        # In a true wide layout, we might cross these manually, but passing directly to the final layer acts as a linear wide memory.

        # 5. Joint Final Layer
        final_concat = layers.Concatenate(name="wide_and_deep_concat")([deep_out, wide_concat])
        output = layers.Dense(1, activation="sigmoid", name="win_probability")(final_concat)

        model = models.Model(
            inputs=[features_input, home_team_input, away_team_input], 
            outputs=output,
            name="NBA_Wide_And_Deep"
        )
        return model

    def predict_proba(self, features: np.ndarray, home_team_id: Optional[int] = None, away_team_id: Optional[int] = None) -> float:
        """Single-game inference."""
        h_id = home_team_id or 0
        a_id = away_team_id or 0
        
        pred = self.model.predict({
            "dense_features": np.expand_dims(features, 0),
            "home_team_id": np.expand_dims([h_id], 0),
            "away_team_id": np.expand_dims([a_id], 0)
        }, verbose=0)
        
        return float(pred[0][0])
    
    def save(self, path: str):
        """Save as TensorFlow SavedModel format."""
        self.model.save(path)
        logger.info(f"TF Wide & Deep Model saved to {path}")
    
    @classmethod
    def load(cls, path: str):
        instance = cls()
        instance.model = models.load_model(path)
        logger.info(f"TF Wide & Deep Model loaded from {path}")
        return instance

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
    return NBA_TEAM_INDEX.get(str(team_name).lower().strip(), 0)
