# ai/smart_swap_knn.py

import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
import joblib

from utils.diet_utils import apply_diet_filter

FEATURE_COLS = ["calories", "protein", "carbs", "fat"]

class SmartSwapKNN:
    def __init__(self):
        self.scaler = StandardScaler()
        self.knn = None
        self.meals = []   # full meal dicts (all meals, unfiltered — used for fitting)

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
        """
        Find k nearest neighbours for meal from the full unfiltered pool.
        Use find_replacements_for_user() when a user profile is available.
        """
        x = np.array([[meal.get(c, 0) for c in FEATURE_COLS]])
        x_scaled = self.scaler.transform(x)

        # Request more neighbours so we still get k after filtering self
        _, idxs = self.knn.kneighbors(x_scaled, n_neighbors=min(k + 1, len(self.meals)))

        results = []
        for idx in idxs[0]:
            candidate = self.meals[idx]
            if candidate["mealName"] != meal["mealName"]:
                results.append(candidate)
            if len(results) >= k:
                break
        return results

    # ------------------------------------------------------------------
    # TASK 1.2 — User-aware replacement with pre-filtered neighbor pool
    # ------------------------------------------------------------------

    def find_replacements_for_user(self, meal: dict, user: dict, k: int = 5) -> list:
        """
        Find k nearest neighbours that pass the user's dietary filter.

        Algorithm:
          1. Apply apply_diet_filter() to the full meal pool.
          2. Project each allowed meal into the scaled feature space.
          3. Pick the k nearest by Euclidean distance (excluding self).

        This avoids returning non-veg items to a vegetarian user even when
        the KNN model was trained on the full unfiltered corpus.

        Args:
            meal: the meal to find replacements for
            user: Firestore user profile dict

        Returns:
            list of meal dicts (at most k items)
        """
        if not self.knn or not self.meals:
            return []

        # 1. Filter the pool by dietary flags
        allowed_meals = apply_diet_filter(self.meals, user)

        # Remove the original meal from the allowed pool
        allowed_meals = [m for m in allowed_meals if m.get("mealName") != meal.get("mealName")]

        if not allowed_meals:
            return []

        # 2. Project allowed meals into the SAME scaled feature space
        X_allowed = np.array(
            [[m.get(c, 0) for c in FEATURE_COLS] for m in allowed_meals],
            dtype=float
        )
        X_allowed_scaled = self.scaler.transform(X_allowed)

        # 3. Query vector
        x = np.array([[meal.get(c, 0) for c in FEATURE_COLS]], dtype=float)
        x_scaled = self.scaler.transform(x)

        # 4. Compute distances to every allowed meal, pick k nearest
        dists = np.linalg.norm(X_allowed_scaled - x_scaled, axis=1)
        sorted_idxs = np.argsort(dists)

        return [allowed_meals[i] for i in sorted_idxs[:k]]

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
