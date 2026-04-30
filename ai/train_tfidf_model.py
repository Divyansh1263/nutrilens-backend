# ai/train_tfidf_model.py
# Utility script to pre-train and save TF-IDF model from Firestore meals
# Can also be used to test the TF-IDF matcher independently

import firebase_admin
from firebase_admin import credentials, firestore
import os
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer

print("🔥 Building TF-IDF Meal Matcher Model 🔥")

# -----------------------------------------------
# Firebase Init
# -----------------------------------------------
if not firebase_admin._apps:
    key_path = "serviceAccountKey.json"
    if os.path.exists(key_path):
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        print("✅ Local Auth")
    else:
        firebase_admin.initialize_app()
        print("✅ Cloud Auth")

db = firestore.client()

# -----------------------------------------------
# Load meals from Firestore
# -----------------------------------------------
print("Loading meals from Firestore...")
meal_docs = db.collection("meals_v3").stream()

meals = []
texts = []

for doc in meal_docs:
    meal = doc.to_dict()
    meal["id"] = doc.id
    meals.append(meal)

    # Build text representation
    name = meal.get("mealName", "")
    keywords = meal.get("searchKeywords", [])
    text = name.lower() + " " + " ".join(k.lower() for k in keywords)
    texts.append(text)

print(f"✅ Loaded {len(meals)} meals")

# -----------------------------------------------
# Build TF-IDF Vectorizer
# -----------------------------------------------
vectorizer = TfidfVectorizer(
    ngram_range=(1, 2),
    max_features=3000,
    lowercase=True,
    sublinear_tf=True,
)

tfidf_matrix = vectorizer.fit_transform(texts)
print(f"✅ TF-IDF matrix shape: {tfidf_matrix.shape}")

# -----------------------------------------------
# Save model
# -----------------------------------------------
model_data = {
    "vectorizer": vectorizer,
    "tfidf_matrix": tfidf_matrix,
    "meals": meals,
    "texts": texts,
}

output_path = "models/tfidf_meal_matcher.joblib"
joblib.dump(model_data, output_path)
print(f"✅ TF-IDF model saved to {output_path}")

# -----------------------------------------------
# Quick test
# -----------------------------------------------
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

test_queries = [
    "paneer curry",
    "dal fry",
    "curd rice",
    "roti",
    "chicken biryani",
]

print("\n--- Quick Test ---")
for query in test_queries:
    query_vec = vectorizer.transform([query.lower()])
    sims = cosine_similarity(query_vec, tfidf_matrix).flatten()
    top_idx = np.argsort(sims)[::-1][:3]

    print(f"\nQuery: '{query}'")
    for idx in top_idx:
        print(f"  → {meals[idx]['mealName']} (score={sims[idx]:.3f})")

print("\n🎉 TF-IDF model training complete!")
