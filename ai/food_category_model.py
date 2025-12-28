# ai/food_category_model.py
import joblib

model = joblib.load("models/food_category_classifier.joblib")

def predict_category(food_word):
    return model.predict([food_word])[0]
