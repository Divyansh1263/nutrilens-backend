"""
scripts/validate_generic.py
Quick offline validation of TF-IDF match quality for generic queries.
Runs entirely from the cached .joblib — no Firestore, no server needed.
"""
import io, sys, os, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
os.chdir(r"d:\NutriLens\backend")

import joblib
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

# --------------------------------------------------------------------------
# Load cache
# --------------------------------------------------------------------------
cache = joblib.load("models/tfidf_meal_matcher.joblib")
vec   = cache["vectorizer"]
mat   = cache["tfidf_matrix"]
meals = cache["meals"]

STOPWORDS = {
    "i","ate","had","have","with","some","a","an","the","for","my","of","and",
    "in","today","yesterday","morning","afternoon","evening","night","breakfast",
    "lunch","dinner","snack","just","also","then","after","before","about",
    "around","like","want","log","consumed","eating","meal","food","serving",
    "servings","to","was","is","it","maine","mene","khaya","kha","li","liya",
    "hai","tha","thi","hun","aur","wala","wali","kiya","khate","khayi","raha",
    "rahi","aaj","kal","subah","dopahar","raat","shaam","sirf","bas","bhi",
    "nahi","nai","thoda",
}
ALIAS = {
    "makhana": "makhana", "chawal": "rice", "chaawal": "rice",
    "chapati": "roti", "chapatis": "roti", "chapatti": "roti",
    "dahi": "curd", "doodh": "milk",
}

def preprocess(q):
    q = q.lower().strip()
    q = re.sub(r"[^\w\s\-]", " ", q)
    tokens = [t for t in q.split() if t not in STOPWORDS]
    out = []
    for t in tokens:
        out.append(ALIAS.get(t, t))
    return " ".join(out)

# --------------------------------------------------------------------------
# Test queries (Task 5 set)
# --------------------------------------------------------------------------
TEST = [
    ("roti",        "Roti"),
    ("dal",         "Dal"),
    ("rice",        "Rice"),
    ("2 roti dal",  "Roti / Dal"),
    ("ate makhana", "Makhana"),
    ("coffee pi",   "Coffee"),
]

PASS = FAIL = 0
print("\n" + "="*68)
print("  GENERIC QUERY VALIDATION")
print("="*68)

for raw_q, expected_hint in TEST:
    pq   = preprocess(raw_q)
    v    = vec.transform([pq])
    sims = cosine_similarity(v, mat).flatten()
    top3 = np.argsort(sims)[::-1][:3]

    top1_name  = meals[top3[0]]["mealName"]
    top1_score = float(sims[top3[0]])

    # Very loose pass: expected hint substring in any top-3 name
    top3_names = [meals[idx]["mealName"].lower() for idx in top3]
    passed = any(expected_hint.split("/")[0].strip().lower() in n for n in top3_names)

    flag = "PASS" if passed else "FAIL"
    if passed:
        PASS += 1
    else:
        FAIL += 1

    print(f"\n  [{flag}] Query: {raw_q!r}  (preprocessed: {pq!r})")
    print(f"         Expected hint : {expected_hint!r}")
    for rank, idx in enumerate(top3, 1):
        name  = meals[idx]["mealName"]
        score = float(sims[idx])
        print(f"         [{rank}] {name!r}  score={score:.4f}")

print("\n" + "="*68)
print(f"  Result: {PASS} PASS  /  {FAIL} FAIL  out of {len(TEST)} queries")
print("="*68 + "\n")
