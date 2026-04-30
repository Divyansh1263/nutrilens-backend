"""
ml/generate_dataset.py
======================
Generates 10,000 realistic synthetic training samples for the Daily Rater model.

User-type distribution:
  - weight_loss  40%
  - muscle_gain  25%
  - unbalanced   25%
  - ideal        10%

Each row: cal_error, protein_error, fat_error, carb_error, score
  error = (actual - target) / target in [-0.5, +0.5]

Scoring:
  score = 1 - (|cal|*1.0 + |protein|*1.5 + |fat|*1.0 + |carbs|*1.0)
  clamped to [0,1], with Gaussian noise +-0.05
"""

import numpy as np
import pandas as pd
import os

# Reproducibility
RNG = np.random.default_rng(seed=42)
N_SAMPLES = 10_000
OUT_PATH = os.path.join(os.path.dirname(__file__), "daily_rater_dataset.csv")

# Per-user-type error distributions (mean, std) per macro
USER_TYPES = {
    "weight_loss": {
        "weight": 0.40,
        # Caloric deficit: eat ~15-20% below target -> negative cal_error
        "cal":    (-0.18, 0.10),
        # Tend to over-eat protein slightly (high-protein diet)
        "protein": (0.05, 0.12),
        # Cut fat significantly
        "fat":    (-0.15, 0.10),
        # Reduce carbs
        "carb":   (-0.20, 0.12),
    },
    "muscle_gain": {
        "weight": 0.25,
        # Slight calorie surplus
        "cal":    (0.10, 0.10),
        # Very high protein intake
        "protein": (0.20, 0.12),
        # Higher fat (whole foods)
        "fat":    (0.05, 0.10),
        # Higher carbs for energy
        "carb":   (0.10, 0.12),
    },
    "unbalanced": {
        "weight": 0.25,
        # Highly variable - large swings
        "cal":    (0.05, 0.25),
        "protein": (-0.20, 0.20),
        "fat":    (0.25, 0.20),
        "carb":   (0.15, 0.20),
    },
    "ideal": {
        "weight": 0.10,
        # Very close to targets
        "cal":    (0.00, 0.05),
        "protein": (0.00, 0.05),
        "fat":    (0.00, 0.05),
        "carb":   (0.00, 0.05),
    },
}

NOISE_STD = 0.05   # label noise std dev
CLIP_LOW  = -0.50  # error clipping range
CLIP_HIGH = +0.50


def _sample_error(mu, std, n):
    """Sample errors from a normal distribution, clipped to [-0.5, +0.5]."""
    raw = RNG.normal(loc=mu, scale=std, size=n)
    return np.clip(raw, CLIP_LOW, CLIP_HIGH)


def _score(cal_err, prot_err, fat_err, carb_err):
    """Compute base score before noise."""
    raw = 1.0 - (
        np.abs(cal_err)  * 1.0 +
        np.abs(prot_err) * 1.5 +
        np.abs(fat_err)  * 1.0 +
        np.abs(carb_err) * 1.0
    )
    return np.clip(raw, 0.0, 1.0)


def generate_dataset():
    rows = []

    # Number of samples per user type (weighted)
    counts = {
        ut: int(cfg["weight"] * N_SAMPLES)
        for ut, cfg in USER_TYPES.items()
    }
    # Fix rounding drift - assign remainder to "weight_loss"
    shortfall = N_SAMPLES - sum(counts.values())
    counts["weight_loss"] += shortfall

    for user_type, cfg in USER_TYPES.items():
        n = counts[user_type]
        cal_err  = _sample_error(*cfg["cal"],     n)
        prot_err = _sample_error(*cfg["protein"], n)
        fat_err  = _sample_error(*cfg["fat"],     n)
        carb_err = _sample_error(*cfg["carb"],    n)

        base_score = _score(cal_err, prot_err, fat_err, carb_err)
        noise      = RNG.normal(loc=0.0, scale=NOISE_STD, size=n)
        final_score = np.clip(base_score + noise, 0.0, 1.0)

        for i in range(n):
            rows.append({
                "cal_error":     round(float(cal_err[i]),   6),
                "protein_error": round(float(prot_err[i]),  6),
                "fat_error":     round(float(fat_err[i]),   6),
                "carb_error":    round(float(carb_err[i]),  6),
                "score":         round(float(final_score[i]), 6),
                "user_type":     user_type,
            })

    df = pd.DataFrame(rows)
    # Shuffle rows
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    return df


if __name__ == "__main__":
    print("[generate_dataset] Building dataset ...")
    df = generate_dataset()

    # Drop the user_type label - model only uses numeric features
    df_model = df.drop(columns=["user_type"])

    df_model.to_csv(OUT_PATH, index=False)
    print("[generate_dataset] Saved {:,} rows -> {}".format(len(df_model), OUT_PATH))

    # Quick sanity-check stats
    print("\n-- Feature Statistics ----------------------------------")
    print(df_model.describe().to_string())
    print("\n-- Score distribution ----------------------------------")
    bins   = [0, 0.5, 0.7, 0.85, 1.01]
    labels = ["Poor (<0.5)", "Average (0.5-0.7)", "Good (0.7-0.85)", "Excellent (>=0.85)"]
    df_model["tier"] = pd.cut(df_model["score"], bins=bins, labels=labels, right=False)
    print(df_model["tier"].value_counts().to_string())
