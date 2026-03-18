# ai/food_entity_extractor.py

import re

FOOD_VOCAB = {
    "roti": ["roti", "rotis", "chapati", "phulka"],
    "dal": ["dal", "lentil", "lentils"],
    "rice": ["rice", "chawal"],
    "curd": ["curd", "yogurt", "dahi"],
    "milk": ["milk"],
    "chai": ["chai", "tea"],
    "sabzi": ["sabzi", "vegetable", "bhaji"],
}

def extract_food_entities(text):
    text = text.lower()
    found = []

    for canonical, variants in FOOD_VOCAB.items():
        for v in variants:
            if re.search(rf"\b{v}\b", text):
                found.append(canonical)
                break

    return list(set(found))
