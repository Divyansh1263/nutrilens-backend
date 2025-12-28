# ai/train_food_category_model.py

import joblib
from sklearn.pipeline import Pipeline
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

X = [
    "roti", "chapati", "phulka",
    "dal", "dal tadka",
    "rice", "steamed rice",
    "sabzi", "mixed vegetable",
    "chai", "tea",
    "milk", "curd"
]

y = [
    "Bread", "Bread", "Bread",
    "Dal", "Dal",
    "Rice", "Rice",
    "Vegetable", "Vegetable",
    "Beverage", "Beverage",
    "Dairy", "Dairy"
]

model = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("clf", LogisticRegression(max_iter=1000))
])

model.fit(X, y)

joblib.dump(model, "models/food_category_classifier.joblib")
print("✅ Category classifier trained")
