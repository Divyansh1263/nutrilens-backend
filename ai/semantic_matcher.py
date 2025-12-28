# ai/semantic_matcher.py

from sentence_transformers import SentenceTransformer, util

class SemanticMealMatcher:
    def __init__(self, meals):
        self.model = SentenceTransformer("all-MiniLM-L6-v2")

        self.meals = meals
        self.meal_texts = []
        self.meal_embeddings = []

        for meal in meals:
            texts = [meal["mealName"]] + meal.get("searchKeywords", [])
            combined = " | ".join(texts)

            self.meal_texts.append(meal)
            self.meal_embeddings.append(
                self.model.encode(combined, convert_to_tensor=True)
            )

    def find_best_match(self, query, threshold=0.60):
        query_emb = self.model.encode(query, convert_to_tensor=True)

        best_meal = None
        best_score = 0.0

        for meal, emb in zip(self.meal_texts, self.meal_embeddings):
            score = util.cos_sim(query_emb, emb).item()

            if score > best_score:
                best_score = score
                best_meal = meal

        if best_score >= threshold:
            return best_meal, round(best_score, 3)

        return None, best_score
