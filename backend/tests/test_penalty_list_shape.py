# tests/test_penalty_list_shape.py
# Regression tests for the 'list object has no attribute get' crash.
# The bug occurred in apply_repetition_penalty and apply_diversity_penalty
# when slot data in a saved plan is stored as a list (the real Firestore shape).
#
# Run: python -m pytest tests/test_penalty_list_shape.py -v
#
# NOTE: These tests mock all Firebase/repository dependencies so they run
#       without credentials/Firestore access.

import sys
import os
import types
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ---------------------------------------------------------------------------
# Patch Firebase and repository imports BEFORE importing the service module
# ---------------------------------------------------------------------------
def _make_mock_db():
    db = mock.MagicMock()
    col = mock.MagicMock()
    db.collection.return_value = col
    col.stream.return_value = []
    return db


_firebase_admin_mock  = mock.MagicMock()
_firestore_mock       = mock.MagicMock()
_firestore_mock.client.return_value = _make_mock_db()

# Stub out firebase_admin
sys.modules.setdefault("firebase_admin", _firebase_admin_mock)
sys.modules.setdefault("firebase_admin.firestore", _firestore_mock)

# Stub out google.cloud.firestore (used by tracker_repository)
_gcloud_firestore = mock.MagicMock()
sys.modules.setdefault("google", mock.MagicMock())
sys.modules.setdefault("google.cloud", mock.MagicMock())
sys.modules.setdefault("google.cloud.firestore_v1", mock.MagicMock())
sys.modules.setdefault("google.cloud.firestore_v1.base_query", mock.MagicMock())

# Stub the dev_store module that repositories import
_dev_store_mock = mock.MagicMock()
_dev_store_mock.MEALS_CACHE = []
_dev_store_mock.USERS_CACHE = {}
_dev_store_mock.ensure_meals_available = mock.MagicMock()
_dev_store_mock.get_meal_by_name = mock.MagicMock(return_value=None)
_dev_store_mock.SEED_MEALS = []
sys.modules.setdefault("dev_store", _dev_store_mock)

# Now import the service under test
from services.meal_generator_service import MealGeneratorService


@pytest.fixture
def svc():
    return MealGeneratorService()


# ---------------------------------------------------------------------------
# apply_repetition_penalty
# ---------------------------------------------------------------------------

class TestRepetitionPenaltySlotShapes:

    def test_slot_as_list_does_not_crash(self, svc):
        """Slot stored as a plain list (real Firestore shape) must not crash."""
        plans = [{"date": "2026-03-22", "breakfast": [{"mealName": "Poha"}]}]
        penalty = svc.apply_repetition_penalty("Poha", plans)
        assert penalty >= 0

    def test_slot_as_dict_still_works(self, svc):
        """Legacy shape {items: [...]} must still work."""
        plans = [{"date": "2026-03-22", "breakfast": {"items": [{"mealName": "Poha"}]}}]
        penalty = svc.apply_repetition_penalty("Poha", plans)
        assert penalty >= 0

    def test_non_matching_meal_returns_zero(self, svc):
        plans = [{"date": "2026-03-22", "breakfast": [{"mealName": "Idli"}]}]
        assert svc.apply_repetition_penalty("Poha", plans) == 0

    def test_empty_plans_returns_zero(self, svc):
        assert svc.apply_repetition_penalty("Poha", []) == 0

    def test_none_plans_returns_zero(self, svc):
        """Non-list recent_plans (e.g. None) must not raise."""
        assert svc.apply_repetition_penalty("Poha", None) == 0

    def test_plan_with_mixed_slot_types(self, svc):
        """One slot is list, another is dict — must both work in same plan."""
        plans = [{
            "date": "2026-03-22",
            "breakfast": [{"mealName": "Poha"}],
            "lunch":     {"items": [{"mealName": "Roti"}, {"mealName": "Dal"}]},
        }]
        assert svc.apply_repetition_penalty("Poha", plans) >= 0
        assert svc.apply_repetition_penalty("Roti", plans) >= 0
        assert svc.apply_repetition_penalty("Upma", plans) == 0


# ---------------------------------------------------------------------------
# apply_diversity_penalty
# ---------------------------------------------------------------------------

class TestDiversityPenaltySlotShapes:

    def test_slot_as_list(self, svc):
        from config.config import PENALTY_WEEK_FREQ_3
        plans = [
            {"breakfast": [{"mealName": "Poha"}]},
            {"breakfast": [{"mealName": "Poha"}]},
            {"breakfast": [{"mealName": "Poha"}]},
        ]
        assert svc.apply_diversity_penalty("Poha", plans) == PENALTY_WEEK_FREQ_3

    def test_slot_as_dict(self, svc):
        from config.config import PENALTY_WEEK_FREQ_2
        plans = [
            {"breakfast": {"items": [{"mealName": "Poha"}]}},
            {"breakfast": {"items": [{"mealName": "Poha"}]}},
        ]
        assert svc.apply_diversity_penalty("Poha", plans) == PENALTY_WEEK_FREQ_2

    def test_none_plans_returns_zero(self, svc):
        assert svc.apply_diversity_penalty("Poha", None) == 0


# ---------------------------------------------------------------------------
# calculate_preference_score — guard against non-dict user_history
# ---------------------------------------------------------------------------

class TestPreferenceScore:

    def test_none_history_returns_zero(self, svc):
        assert svc.calculate_preference_score("Poha", None) == 0

    def test_list_history_returns_zero(self, svc):
        assert svc.calculate_preference_score("Poha", []) == 0

    def test_valid_history_returns_score(self, svc):
        from config.config import PREFERENCE_MULTIPLIER
        history = {"Poha": {"meal_name": "Poha", "count": 5}}
        assert svc.calculate_preference_score("Poha", history) == 5 * PREFERENCE_MULTIPLIER


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
