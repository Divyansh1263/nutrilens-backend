"""
ml/train_daily_rater.py
=======================
Trains a Random Forest Regressor on the synthetic daily-rater dataset.
Evaluates with R2 and MAE, then saves the fitted model via joblib.
"""

import os
import sys

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import train_test_split

# Paths
_DIR         = os.path.dirname(__file__)
DATASET_PATH = os.path.join(_DIR, "daily_rater_dataset.csv")
MODEL_PATH   = os.path.join(_DIR, "daily_rater.joblib")

FEATURE_COLS = ["cal_error", "protein_error", "fat_error", "carb_error"]
TARGET_COL   = "score"


# 1. Load
def load_data():
    if not os.path.exists(DATASET_PATH):
        print("[train] Dataset not found at {}".format(DATASET_PATH))
        print("[train] Run  python ml/generate_dataset.py  first.")
        sys.exit(1)

    df = pd.read_csv(DATASET_PATH)
    print("[train] Loaded {:,} samples from {}".format(len(df), DATASET_PATH))

    X = df[FEATURE_COLS].values
    y = df[TARGET_COL].values
    return X, y


# 2. Split
def split(X, y, test_size=0.2, random_state=42):
    return train_test_split(X, y, test_size=test_size, random_state=random_state)


# 3. Train
def train(X_train, y_train):
    model = RandomForestRegressor(
        n_estimators=150,
        max_depth=8,
        random_state=42,
        n_jobs=-1,           # use all CPU cores
    )
    print("[train] Fitting RandomForestRegressor ...")
    model.fit(X_train, y_train)
    print("[train] Fitting complete.")
    return model


# 4. Evaluate
def evaluate(model, X_test, y_test):
    y_pred = model.predict(X_test)
    r2  = r2_score(y_test, y_pred)
    mae = mean_absolute_error(y_test, y_pred)

    print("\n-- Evaluation Results ------------------------------------------")
    print("  R2  score : {:.6f}".format(r2))
    print("  MAE       : {:.6f}".format(mae))

    # Feature importance
    fi = model.feature_importances_
    print("\n-- Feature Importances -----------------------------------------")
    for name, imp in sorted(zip(FEATURE_COLS, fi), key=lambda x: -x[1]):
        print("  {:18s}: {:.4f}".format(name, imp))

    return r2, mae


# 5. Save
def save(model):
    joblib.dump(model, MODEL_PATH)
    size_kb = os.path.getsize(MODEL_PATH) / 1024
    print("\n[train] Model saved -> {}  ({:.1f} KB)".format(MODEL_PATH, size_kb))


# Entry point
if __name__ == "__main__":
    X, y = load_data()
    X_train, X_test, y_train, y_test = split(X, y)
    model = train(X_train, y_train)
    r2, mae = evaluate(model, X_test, y_test)
    save(model)

    print("\n[train] Pipeline complete.")
    print("        R2 = {:.4f}  |  MAE = {:.4f}".format(r2, mae))
