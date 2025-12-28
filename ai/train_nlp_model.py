# ai/train_nlp_model.py

import pandas as pd
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

print("🔥 Training NLP Meal Classification Model 🔥")

# ---------------------------------------
# Load dataset
# ---------------------------------------
df = pd.read_csv("ai/nlp_training_dataset.csv")

X = df["text"].str.lower()
y = df["label"]

print(f"✅ Loaded {len(df)} training samples")

# ---------------------------------------
# Train / Validation split
# ---------------------------------------
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# ---------------------------------------
# NLP Pipeline
# ---------------------------------------
model = Pipeline([
    ("tfidf", TfidfVectorizer(
        ngram_range=(1, 2),
        stop_words="english",
        min_df=2
    )),
    ("clf", LogisticRegression(
    max_iter=2000
))

])

# ---------------------------------------
# Train model
# ---------------------------------------
model.fit(X_train, y_train)

# ---------------------------------------
# Evaluate
# ---------------------------------------
y_pred = model.predict(X_test)
accuracy = accuracy_score(y_test, y_pred)

print(f"✅ Validation Accuracy: {accuracy * 100:.2f}%")

# ---------------------------------------
# Save trained model
# ---------------------------------------
joblib.dump(model, "models/nlp_meal_classifier.joblib")

print("🎉 NLP Model trained and saved successfully")
