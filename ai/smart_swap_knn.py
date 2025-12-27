# ai/smart_swap_knn.py

import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import joblib

FEATURE_COLS = ["calories", "protein", "carbs", "fat"]

class SmartSwapKNN:
    def __init__(self):
        self.scaler = StandardScaler()
        self.knn = None
        self.meals = []   # full meal dicts

    def fit(self, meals):
        X = []
        for m in meals:
            X.append([m.get(c, 0) for c in FEATURE_COLS])
            self.meals.append(m)

        X = np.array(X, dtype=float)
        X_scaled = self.scaler.fit_transform(X)

        self.knn = NearestNeighbors(
            n_neighbors=6,
            metric="euclidean"
        )
        self.knn.fit(X_scaled)

    def find_replacements(self, meal, k=5):
        x = np.array([[meal.get(c, 0) for c in FEATURE_COLS]])
        x_scaled = self.scaler.transform(x)

        _, idxs = self.knn.kneighbors(x_scaled, n_neighbors=k+1)

        results = []
        for idx in idxs[0]:
            candidate = self.meals[idx]
            if candidate["mealName"] != meal["mealName"]:
                results.append(candidate)
            if len(results) >= k:
                break
        return results

    def save(self, path):
        joblib.dump({
            "scaler": self.scaler,
            "knn": self.knn,
            "meals": self.meals
        }, path)

    def load(self, path):
        data = joblib.load(path)
        self.scaler = data["scaler"]
        self.knn = data["knn"]
        self.meals = data["meals"]
