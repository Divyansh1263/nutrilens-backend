"""
=============================================================
  NutriLens AI Model Accuracy Test Suite
  Tests ALL three AI models independently (no Firebase/Flask required):

    1. NLP Meal Classifier         (models/nlp_meal_classifier.joblib)
    2. Food Category Classifier    (models/food_category_classifier.joblib)
    3. SmartSwap KNN               (models/knn_meal_swap.joblib)
    4. TF-IDF + Hybrid Matcher     (runtime in-memory, uses meal_dataset.json)
    5. Text Preprocessor           (alias normalization + spelling correction)

  Run from backend/ directory:
      python test_model_accuracy.py

  No environment variables or external services needed.
=============================================================
"""

import os
import sys
import json
import time
import warnings
import numpy as np
import joblib
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
)
from sklearn.model_selection import cross_val_score

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def section(title):
    print("\n" + "=" * 64)
    print("  " + title)
    print("=" * 64)

def ok(msg):   print(f"  {GREEN}[PASS]  {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}[WARN]  {msg}{RESET}")
def fail(msg): print(f"  {RED}[FAIL]  {msg}{RESET}")
def info(msg): print(f"     {msg}")

def grade(acc):
    """Return colour-coded grade string."""
    if acc >= 0.90: return f"{GREEN}{acc*100:.2f}%  [EXCELLENT]{RESET}"
    if acc >= 0.75: return f"{YELLOW}{acc*100:.2f}%  [GOOD]{RESET}"
    return f"{RED}{acc*100:.2f}%  [NEEDS IMPROVEMENT]{RESET}"

# ─────────────────────────────────────────────────────────────
# 1. NLP Meal Classifier
# ─────────────────────────────────────────────────────────────

def test_nlp_meal_classifier():
    section("1. NLP Meal Classifier  (nlp_meal_classifier.joblib)")

    MODEL_PATH   = "models/nlp_meal_classifier.joblib"
    DATASET_PATH = "ai/nlp_training_dataset.csv"

    if not os.path.exists(MODEL_PATH):
        fail(f"Model not found: {MODEL_PATH}"); return
    if not os.path.exists(DATASET_PATH):
        fail(f"Dataset not found: {DATASET_PATH}"); return

    model = joblib.load(MODEL_PATH)
    ok(f"Loaded model from {MODEL_PATH}")

    df = pd.read_csv(DATASET_PATH)
    ok(f"Loaded dataset: {len(df):,} samples, {df['label'].nunique()} classes")
    info(f"Classes: {sorted(df['label'].unique())[:10]}{'...' if df['label'].nunique()>10 else ''}")

    X = df["text"].str.lower()
    y = df["label"]

    # ── Predictions ──────────────────────────────────────────
    t0 = time.perf_counter()
    y_pred = model.predict(X)
    elapsed = time.perf_counter() - t0
    acc = accuracy_score(y, y_pred)

    print()
    ok(f"Overall accuracy : {grade(acc)}")
    ok(f"Inference time   : {elapsed*1000:.1f} ms for {len(X):,} samples  "
       f"({elapsed/len(X)*1e6:.2f} µs/sample)")

    # ── Per-class report ──────────────────────────────────────
    print(f"\n  {BOLD}Per-class metrics (top 15 by support):{RESET}")
    report = classification_report(y, y_pred, output_dict=True, zero_division=0)
    rows = [(lbl, v) for lbl, v in report.items()
            if isinstance(v, dict) and lbl not in ("macro avg","weighted avg","accuracy")]
    rows.sort(key=lambda r: r[1]["support"], reverse=True)

    print(f"  {'Label':<35} {'Prec':>6} {'Rec':>6} {'F1':>6} {'Supp':>6}")
    print(f"  {'-'*63}")
    for lbl, m in rows[:15]:
        p, r, f1, s = m['precision'], m['recall'], m['f1-score'], int(m['support'])
        bar = "|" * int(f1 * 20)
        print(f"  {lbl:<35} {p:>6.3f} {r:>6.3f} {f1:>6.3f} {s:>6}  {bar}")

    macro = report.get("macro avg", {})
    weighted = report.get("weighted avg", {})
    print(f"\n  {BOLD}Summary averages:{RESET}")
    info(f"  Macro    Prec={macro.get('precision',0):.3f}  "
         f"Rec={macro.get('recall',0):.3f}  F1={macro.get('f1-score',0):.3f}")
    info(f"  Weighted Prec={weighted.get('precision',0):.3f}  "
         f"Rec={weighted.get('recall',0):.3f}  F1={weighted.get('f1-score',0):.3f}")

    # ── 5-fold cross-validation ───────────────────────────────
    print(f"\n  {BOLD}5-fold cross-validation:{RESET}")
    try:
        cv_scores = cross_val_score(model, X, y, cv=5, scoring="accuracy", n_jobs=-1)
        ok(f"CV scores: {[f'{s:.3f}' for s in cv_scores]}")
        ok(f"CV mean ± std: {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")
    except Exception as e:
        warn(f"CV failed: {e}")

    # ── Quick real-world test samples ────────────────────────
    print(f"\n  {BOLD}Real-world sample predictions:{RESET}")
    samples = [
        "2 roti with dal",
        "poha and chai",
        "idli sambar",
        "chicken biryani",
        "paneer butter masala with naan",
        "oats porridge with banana",
        "dosa with coconut chutney",
        "green salad",
        "aloo paratha with curd",
        "egg bhurji and toast",
    ]
    print(f"  {'Input Text':<40} {'Predicted Label':<25} {'Confidence':>10}")
    print(f"  {'-'*78}")
    for text in samples:
        try:
            proba = model.predict_proba([text.lower()])[0]
            idx = np.argmax(proba)
            label = model.classes_[idx]
            conf  = proba[idx]
            flag  = GREEN if conf >= 0.60 else (YELLOW if conf >= 0.40 else RED)
            print(f"  {text:<40} {label:<25} {flag}{conf*100:>9.1f}%{RESET}")
        except Exception as e:
            print(f"  {text:<40} ERROR: {e}")


# ─────────────────────────────────────────────────────────────
# 2. Food Category Classifier
# ─────────────────────────────────────────────────────────────

def test_food_category_classifier():
    section("2. Food Category Classifier  (food_category_classifier.joblib)")

    MODEL_PATH = "models/food_category_classifier.joblib"
    if not os.path.exists(MODEL_PATH):
        fail(f"Model not found: {MODEL_PATH}"); return

    model = joblib.load(MODEL_PATH)
    ok(f"Loaded model from {MODEL_PATH}")
    info(f"Classes: {list(model.classes_)}")

    # Ground-truth test set (hand-labelled)
    test_data = [
        # (input_word,  expected_category)
        # Bread
        ("roti",         "Bread"),
        ("chapati",      "Bread"),
        ("phulka",       "Bread"),
        ("naan",         "Bread"),
        ("paratha",      "Bread"),
        ("puri",         "Bread"),
        ("bhatura",      "Bread"),
        # Dal
        ("dal",          "Dal"),
        ("lentils",      "Dal"),
        ("moong dal",    "Dal"),
        ("masoor",       "Dal"),
        ("toor dal",     "Dal"),
        # Rice
        ("rice",         "Rice"),
        ("steamed rice", "Rice"),
        ("biryani",      "Rice"),
        ("pulao",        "Rice"),
        ("fried rice",   "Rice"),
        # Vegetable
        ("sabzi",        "Vegetable"),
        ("aloo sabzi",   "Vegetable"),
        ("mixed vegetable", "Vegetable"),
        ("palak",        "Vegetable"),
        ("bhindi",       "Vegetable"),
        # Beverage
        ("chai",         "Beverage"),
        ("tea",          "Beverage"),
        ("coffee",       "Beverage"),
        ("lassi",        "Beverage"),
        ("juice",        "Beverage"),
        # Dairy
        ("milk",         "Dairy"),
        ("curd",         "Dairy"),
        ("dahi",         "Dairy"),
        ("paneer",       "Dairy"),
        ("yogurt",       "Dairy"),
    ]

    X_test = [x for x, _ in test_data]
    y_test = [y for _, y in test_data]

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    ok(f"Accuracy on hand-labelled test set: {grade(acc)}")
    info(f"  {len(X_test)} test samples, {len(set(y_test))} categories")

    print(f"\n  {BOLD}Per-sample results:{RESET}")
    print(f"  {'Input':<22} {'Expected':<14} {'Predicted':<14} {'Match':>5}")
    print(f"  {'-'*58}")
    for inp, exp, pred in zip(X_test, y_test, y_pred):
        sym = f"{GREEN}OK{RESET}" if exp == pred else f"{RED}XX{RESET}"
        print(f"  {inp:<22} {exp:<14} {pred:<14}  {sym}")

    print(f"\n  {BOLD}Classification report:{RESET}")
    print(classification_report(y_test, y_pred, zero_division=0))

    # Confusion matrix
    labels = sorted(set(y_test))
    cm = confusion_matrix(y_test, y_pred, labels=labels)
    print(f"  {BOLD}Confusion matrix (rows=actual, cols=predicted):{RESET}")
    header = f"  {'':>14}" + "".join(f"{l:>14}" for l in labels)
    print(header)
    for i, row in enumerate(cm):
        print(f"  {labels[i]:>14}" + "".join(f"{v:>14}" for v in row))


# ─────────────────────────────────────────────────────────────
# 3. SmartSwap KNN
# ─────────────────────────────────────────────────────────────

def test_smart_swap_knn():
    section("3. SmartSwap KNN  (knn_meal_swap.joblib)")

    MODEL_PATH = "models/knn_meal_swap.joblib"
    if not os.path.exists(MODEL_PATH):
        fail(f"Model not found: {MODEL_PATH}"); return

    data = joblib.load(MODEL_PATH)
    scaler = data["scaler"]
    knn    = data["knn"]
    meals  = data["meals"]

    ok(f"Loaded KNN model: {len(meals)} meals indexed")
    info(f"  KNN params: n_neighbors={knn.n_neighbors}, metric={knn.metric}")

    FEATURE_COLS = ["calories", "protein", "carbs", "fat"]

    # ── Dataset statistics ────────────────────────────────────
    feature_vals = np.array([[m.get(c, 0) for c in FEATURE_COLS] for m in meals], dtype=float)
    print(f"\n  {BOLD}Meal dataset nutrient statistics:{RESET}")
    print(f"  {'Feature':<12}" + "".join(f"{c:>12}" for c in FEATURE_COLS))
    print(f"  {'-'*60}")
    for name, fn in [("Mean", np.mean), ("Std", np.std), ("Min", np.min), ("Max", np.max)]:
        vals = [fn(feature_vals[:, i]) for i in range(len(FEATURE_COLS))]
        print(f"  {name:<12}" + "".join(f"{v:>12.1f}" for v in vals))

    # ── Replacement quality evaluation ────────────────────────
    # Metric: "Calorie-proximity" — how close is the recommended swap's
    # calorie count to the original? Industry benchmark < 20% deviation.
    print(f"\n  {BOLD}Replacement quality evaluation (calorie proximity):{RESET}")

    deviations = []
    macro_deviations = {c: [] for c in FEATURE_COLS}
    n_samples = min(50, len(meals))
    sample_indices = np.random.default_rng(42).choice(len(meals), size=n_samples, replace=False)

    for idx in sample_indices:
        original = meals[idx]
        x = np.array([[original.get(c, 0) for c in FEATURE_COLS]])
        x_scaled = scaler.transform(x)
        _, idxs = knn.kneighbors(x_scaled, n_neighbors=6)

        swaps = []
        for i in idxs[0]:
            if meals[i]["mealName"] != original["mealName"]:
                swaps.append(meals[i])
            if len(swaps) >= 5:
                break

        if not swaps:
            continue

        best_swap = swaps[0]
        for col in FEATURE_COLS:
            orig_val = original.get(col, 0)
            swap_val = best_swap.get(col, 0)
            if orig_val > 0:
                dev = abs(orig_val - swap_val) / orig_val
                macro_deviations[col].append(dev)
            if col == "calories" and orig_val > 0:
                deviations.append(abs(orig_val - swap_val) / orig_val)

    if deviations:
        mean_cal_dev = np.mean(deviations)
        pct_within_20 = np.mean(np.array(deviations) <= 0.20) * 100
        pct_within_10 = np.mean(np.array(deviations) <= 0.10) * 100
        ok(f"Mean calorie deviation (best swap): {mean_cal_dev*100:.1f}%")
        ok(f"Within 10% calorie range: {pct_within_10:.1f}%")
        ok(f"Within 20% calorie range: {pct_within_20:.1f}%")

        if pct_within_20 >= 70:
            ok(f"Replacement quality: {GREEN}GOOD — ≥70% swaps within 20% calorie target{RESET}")
        elif pct_within_20 >= 50:
            warn(f"Replacement quality: MODERATE — only {pct_within_20:.0f}% within 20% calorie target")
        else:
            fail(f"Replacement quality: LOW — only {pct_within_20:.0f}% within 20% calorie target")

        print(f"\n  {BOLD}Mean relative deviation per nutrient (best swap):{RESET}")
        for col in FEATURE_COLS:
            if macro_deviations[col]:
                dev = np.mean(macro_deviations[col]) * 100
                flag = GREEN if dev <= 20 else (YELLOW if dev <= 40 else RED)
                print(f"  {col:<12}: {flag}{dev:.1f}%{RESET}")

    # ── Qualitative spot check ────────────────────────────────
    print(f"\n  {BOLD}Qualitative spot check — top-3 swaps per sample:{RESET}")
    spot_names = ["Idli", "Chicken Biryani", "Paneer Butter Masala", "Oats Porridge", "Dosa"]
    for target_name in spot_names:
        found = next((m for m in meals if target_name.lower() in m.get("mealName","").lower()), None)
        if not found:
            continue
        x = np.array([[found.get(c, 0) for c in FEATURE_COLS]])
        x_scaled = scaler.transform(x)
        _, idxs = knn.kneighbors(x_scaled, n_neighbors=6)

        swaps = [meals[i] for i in idxs[0] if meals[i]["mealName"] != found["mealName"]][:3]
        orig_cal = found.get("calories", 0)
        print(f"\n  Original: {found['mealName']}  ({orig_cal} kcal)")
        for sw in swaps:
            diff = abs(sw.get("calories", 0) - orig_cal)
            print(f"    → {sw['mealName']:<35}  {sw.get('calories',0):>5} kcal  Δ{diff:>4} kcal")


# ─────────────────────────────────────────────────────────────
# 4. TF-IDF Hybrid Matcher  (using meal_dataset.json)
# ─────────────────────────────────────────────────────────────

def test_tfidf_hybrid_matcher():
    section("4. TF-IDF + Hybrid Matcher  (in-memory)")

    DATASET_PATH = "meal_dataset.json"
    if not os.path.exists(DATASET_PATH):
        warn(f"{DATASET_PATH} not found — skipping TF-IDF test"); return

    with open(DATASET_PATH, encoding="utf-8") as f:
        meals = json.load(f)

    ok(f"Loaded {len(meals)} meals from {DATASET_PATH}")

    # Bootstrap the TF-IDF module
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ai.tfidf_matcher import init_tfidf_matcher, tfidf_match
    from ai.hybrid_matcher import hybrid_match, resolve_best_meal

    init_tfidf_matcher(meals)
    ok("TF-IDF matrix built successfully")

    # Ground-truth: (query, expected_meal_name_substring)
    # We test whether the expected meal appears in top-5 results
    ground_truth = [
        ("idli",                 "Idli"),
        ("dosa",                 "Dosa"),
        ("poha",                 "Poha"),
        ("upma",                 "Upma"),
        ("oats",                 "Oats"),
        ("biryani",              "Biryani"),
        ("paneer butter masala", "Paneer Butter Masala"),
        ("dal tadka",            "Dal Tadka"),
        ("aloo paratha",         "Aloo Paratha"),
        ("chicken curry",        "Chicken"),
        ("chole bhature",        "Chole"),
        ("sambar",               "Sambar"),
        ("masala chai",          "Chai"),
        ("egg bhurji",           "Egg"),
        ("palak paneer",         "Palak"),
        ("rajma",                "Rajma"),
        ("khichdi",              "Khichdi"),
        ("vermicelli",           "Vermicelli"),
        ("pongal",               "Pongal"),
        ("rava dosa",            "Rava"),
    ]

    print(f"\n  {BOLD}TF-IDF top-5 retrieval accuracy:{RESET}")
    top1_hits = top3_hits = top5_hits = 0
    print(f"  {'Query':<30} {'Expected':<30} {'Top-1 Match':<30} {'Hit':>4}")
    print(f"  {'-'*100}")

    for query, expected in ground_truth:
        results = tfidf_match(query, top_k=5)
        names = [r[0].get("mealName","") for r in results]

        hit1 = any(expected.lower() in n.lower() for n in names[:1])
        hit3 = any(expected.lower() in n.lower() for n in names[:3])
        hit5 = any(expected.lower() in n.lower() for n in names)

        if hit1: top1_hits += 1
        if hit3: top3_hits += 1
        if hit5: top5_hits += 1

        top1_name = names[0] if names else "-"
        sym = f"{GREEN}HIT{RESET}" if hit1 else (f"{YELLOW}~{RESET}" if hit3 else f"{RED}MISS{RESET}")
        print(f"  {query:<30} {expected:<30} {top1_name:<30}  {sym}")

    n = len(ground_truth)
    print()
    ok(f"Top-1 accuracy: {grade(top1_hits/n)}  ({top1_hits}/{n})")
    ok(f"Top-3 accuracy: {grade(top3_hits/n)}  ({top3_hits}/{n})")
    ok(f"Top-5 accuracy: {grade(top5_hits/n)}  ({top5_hits}/{n})")

    # ── Hybrid matcher confidence calibration ─────────────────
    print(f"\n  {BOLD}Hybrid matcher — confidence calibration:{RESET}")
    print(f"  {'Query':<30} {'Best Match':<35} {'Score':>7}")
    print(f"  {'-'*75}")
    for query, expected in ground_truth[:12]:
        try:
            candidates = hybrid_match(query, top_k=1)
            if candidates:
                best = candidates[0]
                name = best["meal"].get("mealName", "—")
                score = best["score"]
                flag = GREEN if score >= 0.45 else (YELLOW if score >= 0.20 else RED)
                print(f"  {query:<30} {name:<35} {flag}{score:>7.3f}{RESET}")
            else:
                print(f"  {query:<30} {'No match':<35} {'—':>7}")
        except Exception as e:
            print(f"  {query:<30} ERROR: {e}")


# ─────────────────────────────────────────────────────────────
# 5. Text Preprocessor
# ─────────────────────────────────────────────────────────────

def test_text_preprocessor():
    section("5. Text Preprocessor  (alias normalization + spelling correction)")

    from ai.text_preprocessor import (
        clean_text, normalize_aliases, correct_spelling, init_preprocessor
    )

    # Minimal vocab for spelling correction
    miniset = [
        {"mealName": "Idli", "searchKeywords": ["idli", "steam cake"]},
        {"mealName": "Roti", "searchKeywords": ["roti", "chapati", "flatbread"]},
        {"mealName": "Paneer Butter Masala", "searchKeywords": ["paneer", "butter", "masala"]},
        {"mealName": "Dal Tadka", "searchKeywords": ["dal", "lentil", "tadka"]},
        {"mealName": "Chicken Biryani", "searchKeywords": ["chicken", "biryani", "rice"]},
    ]
    init_preprocessor(miniset)
    ok("Initialized pre-processor with mini vocabulary")

    # ── Alias normalization ───────────────────────────────────
    print(f"\n  {BOLD}Alias normalization tests:{RESET}")
    alias_tests = [
        (["dahi"],    ["curd"]),
        (["chawal"],  ["rice"]),
        (["murgh"],   ["chicken"]),
        (["palak"],   ["spinach"]),
        (["chapati"], ["roti"]),
        (["anda"],    ["egg"]),
        (["gosht"],   ["mutton"]),
        (["gobi"],    ["cauliflower"]),
        (["besan"],   ["gram", "flour"]),
        (["panir"],   ["paneer"]),
    ]
    alias_pass = 0
    for tokens, expected in alias_tests:
        result = normalize_aliases(tokens)
        passed = result == expected
        if passed: alias_pass += 1
        sym = f"{GREEN}OK{RESET}" if passed else f"{RED}XX{RESET}"
        print(f"  {sym}  normalize_aliases({tokens}) -> {result}  (expected {expected})")
    ok(f"Alias accuracy: {alias_pass}/{len(alias_tests)}  ({alias_pass/len(alias_tests)*100:.0f}%)")

    # ── Clean text ────────────────────────────────────────────
    print(f"\n  {BOLD}Text cleaning tests:{RESET}")
    clean_tests = [
        ("I had 2 roti for breakfast",  "2 roti"),
        ("had some dal tadka and rice", "dal tadka rice"),
        ("Ate PANEER for lunch!",       "PANEER"),
        ("i ate idli with sambar today","idli sambar"),
    ]
    clean_pass = 0
    for inp, exp in clean_tests:
        result = clean_text(inp)
        passed = result.lower() == exp.lower()
        if passed: clean_pass += 1
        sym = f"{GREEN}OK{RESET}" if passed else f"{YELLOW}~{RESET}"
        print(f"  {sym}  clean_text('{inp}')")
        print(f"       -> '{result}'  (expected '{exp}')")
    ok(f"Clean text accuracy: {clean_pass}/{len(clean_tests)}  ({clean_pass/len(clean_tests)*100:.0f}%)")

    # ── Spelling correction ───────────────────────────────────
    print(f"\n  {BOLD}Spelling correction tests:{RESET}")
    spell_tests = [
        (["rotii"],   "roti"),
        (["panneer"], "paneer"),
        (["daal"],    "dal"),
        (["biyrani"], "biryani"),
        (["chicen"],  "chicken"),
    ]
    spell_pass = 0
    for tokens, expected in spell_tests:
        result = correct_spelling(tokens)
        passed = expected.lower() in " ".join(result).lower()
        if passed: spell_pass += 1
        sym = f"{GREEN}OK{RESET}" if passed else f"{YELLOW}~{RESET}"
        print(f"  {sym}  correct_spelling({tokens}) -> {result}  (expected '{expected}')")
    ok(f"Spelling correction rate: {spell_pass}/{len(spell_tests)}  ({spell_pass/len(spell_tests)*100:.0f}%)")


# ─────────────────────────────────────────────────────────────
# 6. End-to-end pipeline throughput benchmark
# ─────────────────────────────────────────────────────────────

def test_pipeline_throughput():
    section("6. Pipeline Throughput Benchmark")

    DATASET_PATH = "meal_dataset.json"
    if not os.path.exists(DATASET_PATH):
        warn(f"{DATASET_PATH} not found — skipping benchmark"); return

    with open(DATASET_PATH, encoding="utf-8") as f:
        meals = json.load(f)

    from ai.tfidf_matcher import init_tfidf_matcher, tfidf_match
    from ai.hybrid_matcher import hybrid_match

    init_tfidf_matcher(meals)

    queries = [
        "idli", "dosa", "poha", "upma", "biryani",
        "paneer butter masala", "dal tadka", "aloo paratha",
        "chicken curry", "sambar",
    ]

    # Warm-up
    for q in queries:
        hybrid_match(q, top_k=3)

    # Benchmark
    RUNS = 100
    t0 = time.perf_counter()
    for _ in range(RUNS):
        for q in queries:
            hybrid_match(q, top_k=3)
    elapsed = time.perf_counter() - t0
    total_queries = RUNS * len(queries)
    qps = total_queries / elapsed

    ok(f"Total queries : {total_queries:,}")
    ok(f"Total time    : {elapsed*1000:.1f} ms")
    ok(f"Per-query     : {elapsed/total_queries*1000:.2f} ms")
    ok(f"Throughput    : {qps:.0f} queries/sec")

    if qps >= 200:
        ok(f"Performance: {GREEN}EXCELLENT (≥200 qps){RESET}")
    elif qps >= 50:
        ok(f"Performance: {YELLOW}GOOD (≥50 qps){RESET}")
    else:
        warn(f"Performance: LOW ({qps:.0f} qps) — consider caching")


# ─────────────────────────────────────────────────────────────
# Summary dashboard
# ─────────────────────────────────────────────────────────────

def print_summary():
    section("SUMMARY DASHBOARD")
    print(f"""
  Model                         Path / Status
  ─────────────────────────────────────────────────────────────
  NLP Meal Classifier           models/nlp_meal_classifier.joblib
  Food Category Classifier      models/food_category_classifier.joblib
  SmartSwap KNN                 models/knn_meal_swap.joblib
  TF-IDF Hybrid Matcher         in-memory (meal_dataset.json)
  Text Preprocessor             ai/text_preprocessor.py

  Metrics measured:
    • Classification accuracy, precision, recall, F1 per class
    • 5-fold cross-validation (NLP model)
    • Calorie proximity deviation (KNN)
    • Top-1 / Top-3 / Top-5 retrieval accuracy (TF-IDF)
    • Alias normalization correctness (Preprocessor)
    • Throughput (queries / second)
""")


# ─────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Ensure working dir is backend/ regardless of where script is run
    script_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in dir() else os.getcwd()
    os.chdir(script_dir)
    # Fix Windows console encoding
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    overall_start = time.perf_counter()

    try:
        test_nlp_meal_classifier()
    except Exception as e:
        fail(f"NLP Classifier test crashed: {e}")

    try:
        test_food_category_classifier()
    except Exception as e:
        fail(f"Food Category test crashed: {e}")

    try:
        test_smart_swap_knn()
    except Exception as e:
        fail(f"KNN test crashed: {e}")

    try:
        test_tfidf_hybrid_matcher()
    except Exception as e:
        fail(f"TF-IDF test crashed: {e}")

    try:
        test_text_preprocessor()
    except Exception as e:
        fail(f"Preprocessor test crashed: {e}")

    try:
        test_pipeline_throughput()
    except Exception as e:
        fail(f"Throughput benchmark crashed: {e}")

    overall_elapsed = time.perf_counter() - overall_start
    print_summary()
    print(f"\n{BOLD}{GREEN}  All tests completed in {overall_elapsed:.2f}s{RESET}\n")
