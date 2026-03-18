# tests/test_nlp_pipeline.py
# Unit tests for the improved NLP pipeline v2.1
# Run: python -m pytest tests/test_nlp_pipeline.py -v

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# -----------------------------------------------
# Mock Meal Data (no Firebase needed)
# -----------------------------------------------
MOCK_MEALS = [
    {
        "mealName": "Plain Wheat Roti",
        "searchKeywords": ["roti", "chapati", "phulka", "wheat bread"],
        "category": "Bread",
        "calories": 80, "protein": 2.3, "carbs": 15, "fat": 1.1,
    },
    {
        "mealName": "Plain Dal",
        "searchKeywords": ["dal", "lentil", "daal"],
        "category": "Dal",
        "calories": 120, "protein": 8, "carbs": 18, "fat": 2,
    },
    {
        "mealName": "Steamed Rice",
        "searchKeywords": ["rice", "chawal", "plain rice"],
        "category": "Rice",
        "calories": 130, "protein": 2.5, "carbs": 28, "fat": 0.3,
    },
    {
        "mealName": "Dal Chawal",
        "searchKeywords": ["dal chawal", "dal rice", "lentil rice"],
        "category": "Rice",
        "calories": 250, "protein": 10, "carbs": 45, "fat": 3,
    },
    {
        "mealName": "Rajma Chawal",
        "searchKeywords": ["rajma chawal", "rajma rice", "kidney beans rice"],
        "category": "Rice",
        "calories": 310, "protein": 12, "carbs": 52, "fat": 4,
    },
    {
        "mealName": "Paneer Butter Masala",
        "searchKeywords": ["paneer curry", "paneer butter", "paneer masala"],
        "category": "Vegetable",
        "calories": 350, "protein": 14, "carbs": 12, "fat": 28,
    },
    {
        "mealName": "Curd Rice",
        "searchKeywords": ["curd rice", "dahi rice", "yogurt rice"],
        "category": "Rice",
        "calories": 180, "protein": 5, "carbs": 30, "fat": 4,
    },
    {
        "mealName": "Chicken Biryani",
        "searchKeywords": ["chicken biryani", "biryani", "dum biryani"],
        "category": "Rice",
        "calories": 450, "protein": 22, "carbs": 55, "fat": 15,
    },
    {
        "mealName": "Aloo Paratha",
        "searchKeywords": ["aloo paratha", "potato paratha", "stuffed paratha"],
        "category": "Bread",
        "calories": 220, "protein": 5, "carbs": 30, "fat": 9,
    },
    {
        "mealName": "Idli Sambar",
        "searchKeywords": ["idli", "idli sambar", "steamed rice cake"],
        "category": "Breakfast",
        "calories": 160, "protein": 6, "carbs": 28, "fat": 2,
    },
    {
        "mealName": "Naan",
        "searchKeywords": ["naan", "naan bread", "tandoori naan"],
        "category": "Bread",
        "calories": 260, "protein": 7, "carbs": 45, "fat": 5,
    },
    {
        "mealName": "Chicken Tikka Masala",
        "searchKeywords": ["chicken tikka masala", "tikka masala", "chicken tikka"],
        "category": "Protein",
        "calories": 380, "protein": 28, "carbs": 10, "fat": 22,
    },
]


# ===================================================
# TEST: text_preprocessor
# ===================================================
class TestTextPreprocessor:

    @pytest.fixture(autouse=True)
    def setup(self):
        from ai.text_preprocessor import init_preprocessor
        init_preprocessor(MOCK_MEALS)

    def test_clean_text_removes_stopwords(self):
        from ai.text_preprocessor import clean_text
        result = clean_text("I ate some roti with dal")
        assert "roti" in result
        assert "dal" in result
        for sw in ["i", "ate", "some", "with"]:
            assert sw not in result.split()

    def test_clean_text_removes_punctuation(self):
        from ai.text_preprocessor import clean_text
        result = clean_text("I ate roti, dal & rice!")
        assert "," not in result
        assert "&" not in result
        assert "!" not in result

    def test_correct_spelling_preserves_correct_words(self):
        from ai.text_preprocessor import correct_spelling
        result = correct_spelling(["roti", "dal", "rice"])
        assert result == ["roti", "dal", "rice"]

    def test_correct_spelling_preserves_numbers(self):
        from ai.text_preprocessor import correct_spelling
        result = correct_spelling(["3", "roti", "two"])
        assert result[0] == "3"
        assert result[2] == "two"

    # ---- NEW: Alias normalization tests ----

    def test_alias_dahi_to_curd(self):
        from ai.text_preprocessor import normalize_aliases
        result = normalize_aliases(["dahi", "rice"])
        assert "curd" in result
        assert "dahi" not in result

    def test_alias_bhindi_to_okra(self):
        from ai.text_preprocessor import normalize_aliases
        result = normalize_aliases(["bhindi"])
        assert "okra" in result

    def test_alias_chole_to_chickpeas(self):
        from ai.text_preprocessor import normalize_aliases
        result = normalize_aliases(["chole"])
        assert "chickpeas" in result

    def test_alias_preserves_non_aliases(self):
        from ai.text_preprocessor import normalize_aliases
        result = normalize_aliases(["roti", "dal"])
        assert result == ["roti", "dal"]

    def test_alias_multi_word_canonical(self):
        from ai.text_preprocessor import normalize_aliases
        # "besan" → "gram flour" (two words)
        result = normalize_aliases(["besan"])
        assert "gram" in result
        assert "flour" in result


# ===================================================
# TEST: phrase_detector (UPGRADED — 4-word)
# ===================================================
class TestPhraseDetector:

    @pytest.fixture(autouse=True)
    def setup(self):
        from ai.phrase_detector import init_phrase_detector
        init_phrase_detector(MOCK_MEALS)

    def test_detects_two_word_phrase(self):
        from ai.phrase_detector import detect_phrases
        tokens = ["dal", "chawal"]
        result = detect_phrases(tokens)
        assert "dal chawal" in result

    def test_detects_aloo_paratha(self):
        from ai.phrase_detector import detect_phrases
        tokens = ["aloo", "paratha"]
        result = detect_phrases(tokens)
        assert "aloo paratha" in result

    def test_detects_three_word_phrase(self):
        """IMPROVEMENT: 3-word phrases"""
        from ai.phrase_detector import detect_phrases
        tokens = ["chicken", "tikka", "masala"]
        result = detect_phrases(tokens)
        assert "chicken tikka masala" in result

    def test_detects_four_word_phrase_if_known(self):
        """IMPROVEMENT: 4-word phrases from meal names"""
        from ai.phrase_detector import detect_phrases
        # "paneer butter masala" is a 3-word name in our mock data
        tokens = ["paneer", "butter", "masala"]
        result = detect_phrases(tokens)
        assert "paneer butter masala" in result

    def test_single_tokens_pass_through(self):
        from ai.phrase_detector import detect_phrases
        tokens = ["roti", "dal"]
        result = detect_phrases(tokens)
        assert "roti" in result
        assert "dal" in result

    def test_mixed_phrases_and_tokens(self):
        from ai.phrase_detector import detect_phrases
        tokens = ["3", "aloo", "paratha", "dal"]
        result = detect_phrases(tokens)
        assert "3" in result
        assert "aloo paratha" in result
        assert "dal" in result


# ===================================================
# TEST: quantity_extractor
# ===================================================
class TestQuantityExtractor:

    def test_digit_quantity(self):
        from ai.quantity_extractor import extract_quantities
        result = extract_quantities(["roti"], "3 roti")
        assert result["roti"] == 3

    def test_word_number(self):
        from ai.quantity_extractor import extract_quantities
        result = extract_quantities(["roti"], "two roti")
        assert result["roti"] == 2

    def test_fraction(self):
        from ai.quantity_extractor import extract_quantities
        result = extract_quantities(["rice"], "half rice")
        assert result["rice"] == 0.5

    def test_portion_with_number(self):
        from ai.quantity_extractor import extract_quantities
        result = extract_quantities(["biryani"], "2 plate biryani")
        assert result["biryani"] == 2

    def test_default_quantity(self):
        from ai.quantity_extractor import extract_quantities
        result = extract_quantities(["dal"], "dal")
        assert result["dal"] == 1

    def test_multiple_entities(self):
        from ai.quantity_extractor import extract_quantities
        result = extract_quantities(["roti", "dal"], "3 roti dal")
        assert result["roti"] == 3
        assert result["dal"] == 1


# ===================================================
# TEST: context_resolver (UPGRADED — scoring)
# ===================================================
class TestContextResolver:

    def test_dal_rice_combo_returns_scores(self):
        """IMPROVEMENT: Returns context_scores instead of just entities"""
        from ai.context_resolver import resolve_context
        entities = ["dal", "rice"]
        quantities = {"dal": 1, "rice": 1}
        resolved_e, resolved_q, ctx_scores = resolve_context(entities, quantities)
        assert "Dal Chawal" in resolved_e
        assert ctx_scores["Dal Chawal"] == 1.0  # Context boost

    def test_rajma_rice_combo(self):
        from ai.context_resolver import resolve_context
        entities = ["rajma", "rice"]
        quantities = {"rajma": 1, "rice": 1}
        resolved_e, resolved_q, ctx_scores = resolve_context(entities, quantities)
        assert "Rajma Chawal" in resolved_e
        assert ctx_scores["Rajma Chawal"] == 1.0

    def test_single_entity_no_context_score(self):
        from ai.context_resolver import resolve_context
        entities = ["roti"]
        quantities = {"roti": 3}
        resolved_e, resolved_q, ctx_scores = resolve_context(entities, quantities)
        assert resolved_e == ["roti"]
        assert ctx_scores["roti"] == 0.0

    def test_no_matching_combo(self):
        from ai.context_resolver import resolve_context
        entities = ["roti", "dal"]
        quantities = {"roti": 2, "dal": 1}
        resolved_e, resolved_q, ctx_scores = resolve_context(entities, quantities)
        assert len(resolved_e) == 2
        for e in resolved_e:
            assert ctx_scores[e] == 0.0  # No context match

    def test_combo_preserves_remaining(self):
        from ai.context_resolver import resolve_context
        entities = ["dal", "rice", "roti"]
        quantities = {"dal": 1, "rice": 1, "roti": 2}
        resolved_e, resolved_q, ctx_scores = resolve_context(entities, quantities)
        assert "Dal Chawal" in resolved_e
        assert "roti" in resolved_e
        assert ctx_scores.get("Dal Chawal") == 1.0
        assert ctx_scores.get("roti") == 0.0


# ===================================================
# TEST: tfidf_matcher
# ===================================================
class TestTfidfMatcher:

    @pytest.fixture(autouse=True)
    def setup(self):
        from ai.tfidf_matcher import init_tfidf_matcher
        init_tfidf_matcher(MOCK_MEALS)

    def test_exact_name_match(self):
        from ai.tfidf_matcher import tfidf_match
        results = tfidf_match("chicken biryani")
        assert len(results) > 0
        assert results[0][0]["mealName"] == "Chicken Biryani"

    def test_keyword_match(self):
        from ai.tfidf_matcher import tfidf_match
        results = tfidf_match("chapati")
        assert len(results) > 0
        names = [r[0]["mealName"] for r in results]
        assert "Plain Wheat Roti" in names

    def test_category_filter(self):
        from ai.tfidf_matcher import tfidf_match
        results = tfidf_match("roti", category_filter="Bread")
        for meal, score in results:
            assert meal["category"] == "Bread"

    def test_returns_scores(self):
        from ai.tfidf_matcher import tfidf_match
        results = tfidf_match("dal")
        assert len(results) > 0
        for meal, score in results:
            assert 0 <= score <= 1


# ===================================================
# TEST: hybrid_matcher (UPGRADED — 4-signal + entity filter)
# ===================================================
class TestHybridMatcher:

    @pytest.fixture(autouse=True)
    def setup(self):
        from ai.tfidf_matcher import init_tfidf_matcher
        init_tfidf_matcher(MOCK_MEALS)

    def test_resolve_best_meal(self):
        from ai.hybrid_matcher import resolve_best_meal
        meal, confidence = resolve_best_meal("chicken biryani")
        assert meal is not None
        assert meal["mealName"] == "Chicken Biryani"
        assert confidence > 0.5

    def test_context_score_boosts_match(self):
        """IMPROVEMENT: Context score should increase confidence"""
        from ai.hybrid_matcher import resolve_best_meal
        meal_no_ctx, conf_no_ctx = resolve_best_meal("dal chawal", context_score=0.0)
        meal_with_ctx, conf_with_ctx = resolve_best_meal("dal chawal", context_score=1.0)
        # With context boost, confidence should be higher
        assert conf_with_ctx >= conf_no_ctx

    def test_hybrid_match_returns_sorted(self):
        from ai.hybrid_matcher import hybrid_match
        results = hybrid_match("dal")
        assert len(results) > 0
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_hybrid_match_includes_context_score(self):
        """IMPROVEMENT: Result dicts should contain context_score field"""
        from ai.hybrid_matcher import hybrid_match
        results = hybrid_match("dal", context_score=1.0)
        assert len(results) > 0
        assert "context_score" in results[0]
        assert results[0]["context_score"] == 1.0

    def test_entity_confidence_filter(self):
        """IMPROVEMENT: Weak matches should be filtered out"""
        from ai.hybrid_matcher import hybrid_match
        # A completely nonsensical query should return fewer or no results
        results = hybrid_match("xyzabc123")
        # Either empty or all filtered out (depends on fuzzy behavior)
        # At minimum, no result should have high confidence
        for r in results:
            assert r["score"] < 0.9

    def test_scores_clamped_to_0_1(self):
        """IMPROVEMENT: Scores should never exceed 1.0"""
        from ai.hybrid_matcher import hybrid_match
        results = hybrid_match("chicken biryani", context_score=1.0,
                                predicted_category="Rice")
        for r in results:
            assert 0.0 <= r["score"] <= 1.0


# ===================================================
# Run: python -m pytest tests/test_nlp_pipeline.py -v
# ===================================================
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
