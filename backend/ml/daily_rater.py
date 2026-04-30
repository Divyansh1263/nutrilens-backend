"""
ml/daily_rater.py
=================
Lazy-loaded Daily Rater model wrapper.

Usage:
    from ml.daily_rater import predict_score

    score = predict_score({
        "calories": -0.05,
        "protein":   0.10,
        "fat":       0.02,
        "carbs":    -0.08,
    })
    # → float in [0, 1]

The model file (daily_rater.joblib) is loaded once on first call.
Subsequent calls reuse the cached model object (thread-safe for reads).
"""

import os
import logging

logger = logging.getLogger(__name__)

# ── Lazy model cache ─────────────────────────────────────────────────────────
_model = None

# Resolve path relative to this file so imports work regardless of CWD
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "daily_rater.joblib")


def get_model():
    """Return the fitted RandomForest model, loading from disk on first call."""
    global _model
    if _model is None:
        import joblib
        if not os.path.exists(_MODEL_PATH):
            raise FileNotFoundError(
                f"[daily_rater] Model file not found: {_MODEL_PATH}. "
                "Run ml/generate_dataset.py then ml/train_daily_rater.py first."
            )
        logger.info("[daily_rater] Loading model from %s", _MODEL_PATH)
        _model = joblib.load(_MODEL_PATH)
        logger.info("[daily_rater] Model loaded successfully.")
    return _model


def predict_score(macro_dev: dict) -> float:
    """
    Predict a [0, 1] diet quality score for a given set of macro deviations.

    Parameters
    ----------
    macro_dev : dict
        Keys: "calories", "protein", "fat", "carbs"
        Values: relative error  (actual - target) / target  ∈ [-1, 1]

    Returns
    -------
    float
        Clamped score in [0.0, 1.0]. Higher is better.
    """
    try:
        model = get_model()

        features = [[
            float(macro_dev.get("calories", 0.0)),
            float(macro_dev.get("protein",  0.0)),
            float(macro_dev.get("fat",      0.0)),
            float(macro_dev.get("carbs",    0.0)),
        ]]

        raw_score = model.predict(features)[0]
        return max(0.0, min(1.0, float(raw_score)))

    except Exception as exc:
        logger.warning(
            "[daily_rater] predict_score failed (%s) — returning -1 to trigger fallback.",
            exc,
        )
        return -1.0   # sentinel: caller should fall back to optimization_score


def interpret_score(score: float) -> str:
    """Map a [0, 1] score to a human-readable label."""
    if score >= 0.85:
        return "Excellent"
    elif score >= 0.70:
        return "Good"
    elif score >= 0.50:
        return "Average"
    else:
        return "Needs Improvement"
