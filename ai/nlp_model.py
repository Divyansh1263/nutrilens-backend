# ai/nlp_model.py

import joblib
import re
import numpy as np

# Load trained NLP model ONCE
MODEL_PATH = "models/nlp_meal_classifier.joblib"
nlp_model = joblib.load(MODEL_PATH)

def extract_meals_from_text(text):
    """
    Extracts meal predictions + quantities from user text
    """
    text = text.lower()

    # Split sentence for multi-meal input
    parts = re.split(r"and|,", text)

    results = []

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # Quantity extraction
        qty_match = re.search(r"(\d+)", part)
        quantity = int(qty_match.group(1)) if qty_match else 1

        # Remove quantity from text
        clean_text = re.sub(r"\d+", "", part).strip()

        # Predict meal
        probs = nlp_model.predict_proba([clean_text])[0]
        pred_index = np.argmax(probs)
        confidence = float(probs[pred_index])

        meal_name = nlp_model.classes_[pred_index]

        results.append({
            "meal": meal_name,
            "quantity": quantity,
            "confidence": round(confidence, 3)
        })

    return results
