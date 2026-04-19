"""
Runs all NutriLens AI model accuracy tests and writes a clean
markdown report to ai_accuracy_report.md.
Run from: d:/NutriLens/backend/
    python run_accuracy_report.py
"""

import os, sys, json, time, warnings
import numpy as np
import joblib
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix
from sklearn.model_selection import cross_val_score

warnings.filterwarnings("ignore")
os.chdir(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

lines = []

def h1(t):  lines.append(f"\n# {t}\n")
def h2(t):  lines.append(f"\n## {t}\n")
def h3(t):  lines.append(f"\n### {t}\n")
def row(t): lines.append(t)
def blank(): lines.append("")

# ── 1. NLP Meal Classifier ────────────────────────────────────────────────────
h1("NutriLens AI Model Accuracy Report")
row(f"_Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}_")

h2("1. NLP Meal Classifier  (`nlp_meal_classifier.joblib`)")
row("> TF-IDF + Logistic Regression. Classifies raw user meal text into meal labels.")

MODEL_PATH   = "models/nlp_meal_classifier.joblib"
DATASET_PATH = "ai/nlp_training_dataset.csv"

try:
    model = joblib.load(MODEL_PATH)
    df    = pd.read_csv(DATASET_PATH)
    X     = df["text"].str.lower()
    y     = df["label"]

    row(f"\n- **Dataset size:** {len(df):,} samples")
    row(f"- **Classes:** {df['label'].nunique()}")
    row(f"- **Classes list:** {sorted(df['label'].unique())[:20]}")

    t0     = time.perf_counter()
    y_pred = model.predict(X)
    elapsed = time.perf_counter() - t0

    acc = accuracy_score(y, y_pred)
    row(f"- **Overall Accuracy:** {acc*100:.2f}%")
    row(f"- **Inference time:** {elapsed*1000:.1f} ms for {len(X):,} samples ({elapsed/len(X)*1e6:.2f} µs/sample)")

    # Per-class
    h3("Per-class Metrics (top 15 by support)")
    report = classification_report(y, y_pred, output_dict=True, zero_division=0)
    rows = [(lbl, v) for lbl, v in report.items()
            if isinstance(v, dict) and lbl not in ("macro avg","weighted avg","accuracy")]
    rows.sort(key=lambda r: r[1]["support"], reverse=True)

    row("| Label | Precision | Recall | F1-Score | Support |")
    row("|-------|-----------|--------|----------|---------|")
    for lbl, m in rows[:15]:
        row(f"| {lbl} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1-score']:.3f} | {int(m['support'])} |")

    macro    = report.get("macro avg", {})
    weighted = report.get("weighted avg", {})
    h3("Average Metrics")
    row("| Average | Precision | Recall | F1-Score |")
    row("|---------|-----------|--------|----------|")
    row(f"| Macro    | {macro.get('precision',0):.3f} | {macro.get('recall',0):.3f} | {macro.get('f1-score',0):.3f} |")
    row(f"| Weighted | {weighted.get('precision',0):.3f} | {weighted.get('recall',0):.3f} | {weighted.get('f1-score',0):.3f} |")

    # 5-fold CV
    h3("5-Fold Cross-Validation")
    try:
        cv = cross_val_score(model, X, y, cv=5, scoring="accuracy", n_jobs=-1)
        row(f"- **CV Scores:** {[f'{s:.4f}' for s in cv]}")
        row(f"- **Mean ± Std:** {cv.mean():.4f} ± {cv.std():.4f}")
        grade_cv = "EXCELLENT" if cv.mean() >= 0.90 else ("GOOD" if cv.mean() >= 0.75 else "NEEDS IMPROVEMENT")
        row(f"- **Grade:** {grade_cv}")
    except Exception as e:
        row(f"- CV failed: {e}")

    # Real-world samples
    h3("Real-World Sample Predictions")
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
    row("| Input Text | Predicted Label | Confidence |")
    row("|------------|-----------------|------------|")
    for text in samples:
        try:
            proba = model.predict_proba([text.lower()])[0]
            idx   = np.argmax(proba)
            label = model.classes_[idx]
            conf  = proba[idx]
            grade = "HIGH" if conf >= 0.60 else ("MED" if conf >= 0.40 else "LOW")
            row(f"| {text} | {label} | {conf*100:.1f}% [{grade}] |")
        except Exception as e:
            row(f"| {text} | ERROR | {e} |")

except Exception as e:
    row(f"\n**ERROR:** {e}")

# ── 2. Food Category Classifier ───────────────────────────────────────────────
h2("2. Food Category Classifier  (`food_category_classifier.joblib`)")
row("> Tiny TF-IDF + Logistic Regression. Predicts high-level food category from a single word.")

MODEL_PATH2 = "models/food_category_classifier.joblib"
try:
    model2 = joblib.load(MODEL_PATH2)
    row(f"\n- **Classes:** {list(model2.classes_)}")

    test_data = [
        ("roti","Bread"),("chapati","Bread"),("phulka","Bread"),
        ("naan","Bread"),("paratha","Bread"),("puri","Bread"),("bhatura","Bread"),
        ("dal","Dal"),("lentils","Dal"),("moong dal","Dal"),("masoor","Dal"),("toor dal","Dal"),
        ("rice","Rice"),("steamed rice","Rice"),("biryani","Rice"),("pulao","Rice"),("fried rice","Rice"),
        ("sabzi","Vegetable"),("aloo sabzi","Vegetable"),("mixed vegetable","Vegetable"),
        ("palak","Vegetable"),("bhindi","Vegetable"),
        ("chai","Beverage"),("tea","Beverage"),("coffee","Beverage"),("lassi","Beverage"),("juice","Beverage"),
        ("milk","Dairy"),("curd","Dairy"),("dahi","Dairy"),("paneer","Dairy"),("yogurt","Dairy"),
    ]
    X2 = [x for x, _ in test_data]
    y2 = [y for _, y in test_data]
    y2_pred = model2.predict(X2)
    acc2 = accuracy_score(y2, y2_pred)

    row(f"- **Test samples:** {len(X2)} (hand-labelled, 6 categories)")
    row(f"- **Accuracy:** {acc2*100:.2f}%")
    grade2 = "EXCELLENT" if acc2 >= 0.90 else ("GOOD" if acc2 >= 0.75 else "NEEDS IMPROVEMENT")
    row(f"- **Grade:** {grade2}")

    h3("Per-sample Results")
    row("| Input | Expected | Predicted | Match |")
    row("|-------|----------|-----------|-------|")
    for inp, exp, pred in zip(X2, y2, y2_pred):
        sym = "PASS" if exp == pred else "FAIL"
        row(f"| {inp} | {exp} | {pred} | {sym} |")

    h3("Classification Report")
    row("```")
    row(classification_report(y2, y2_pred, zero_division=0))
    row("```")

    h3("Confusion Matrix")
    labels = sorted(set(y2))
    cm = confusion_matrix(y2, y2_pred, labels=labels)
    header = "| (actual\\predicted) |" + "".join(f" {l} |" for l in labels)
    sep    = "|---|" + "".join("---|" for _ in labels)
    row(header); row(sep)
    for i, r in enumerate(cm):
        row(f"| **{labels[i]}** |" + "".join(f" {v} |" for v in r))

except Exception as e:
    row(f"\n**ERROR:** {e}")

# ── 3. SmartSwap KNN ──────────────────────────────────────────────────────────
h2("3. SmartSwap KNN  (`knn_meal_swap.joblib`)")
row("> K-Nearest Neighbours on [calories, protein, carbs, fat]. Finds nutritionally similar meal replacements.")

MODEL_PATH3 = "models/knn_meal_swap.joblib"
FEATURE_COLS = ["calories", "protein", "carbs", "fat"]
try:
    data3  = joblib.load(MODEL_PATH3)
    scaler = data3["scaler"]
    knn    = data3["knn"]
    meals3 = data3["meals"]

    row(f"\n- **Meals indexed:** {len(meals3)}")
    row(f"- **KNN params:** n_neighbors={knn.n_neighbors}, metric={knn.metric}")

    # Dataset stats
    feats = np.array([[m.get(c, 0) for c in FEATURE_COLS] for m in meals3], dtype=float)
    h3("Dataset Nutrient Statistics")
    row("| Stat | Calories | Protein | Carbs | Fat |")
    row("|------|----------|---------|-------|-----|")
    for name, fn in [("Mean", np.mean), ("Std", np.std), ("Min", np.min), ("Max", np.max)]:
        vals = [fn(feats[:, i]) for i in range(4)]
        row(f"| {name} | {vals[0]:.1f} | {vals[1]:.1f} | {vals[2]:.1f} | {vals[3]:.1f} |")

    # Replacement quality
    h3("Replacement Quality — Calorie Proximity (50 random samples)")
    deviations = []
    macro_dev  = {c: [] for c in FEATURE_COLS}
    rng        = np.random.default_rng(42)
    idxs_sample = rng.choice(len(meals3), size=min(50, len(meals3)), replace=False)

    for idx in idxs_sample:
        orig = meals3[idx]
        x = np.array([[orig.get(c, 0) for c in FEATURE_COLS]])
        xs = scaler.transform(x)
        _, nb_idxs = knn.kneighbors(xs, n_neighbors=6)
        swaps = [meals3[i] for i in nb_idxs[0] if meals3[i]["mealName"] != orig["mealName"]][:5]
        if not swaps: continue
        best = swaps[0]
        for col in FEATURE_COLS:
            ov = orig.get(col, 0)
            sv = best.get(col, 0)
            if ov > 0:
                dev = abs(ov - sv) / ov
                macro_dev[col].append(dev)
                if col == "calories":
                    deviations.append(dev)

    if deviations:
        mean_dev    = np.mean(deviations) * 100
        pct10       = np.mean(np.array(deviations) <= 0.10) * 100
        pct20       = np.mean(np.array(deviations) <= 0.20) * 100
        grade_knn   = "EXCELLENT" if pct20 >= 70 else ("GOOD" if pct20 >= 50 else "NEEDS IMPROVEMENT")
        row(f"| Metric | Value |")
        row("|--------|-------|")
        row(f"| Mean calorie deviation (best swap) | {mean_dev:.1f}% |")
        row(f"| Within 10% calorie range | {pct10:.1f}% |")
        row(f"| Within 20% calorie range | {pct20:.1f}% |")
        row(f"| Grade | {grade_knn} |")

        h3("Mean Relative Deviation Per Nutrient")
        row("| Nutrient | Mean Deviation | Grade |")
        row("|----------|---------------|-------|")
        for col in FEATURE_COLS:
            if macro_dev[col]:
                d = np.mean(macro_dev[col]) * 100
                g = "GOOD" if d <= 20 else ("OK" if d <= 40 else "HIGH")
                row(f"| {col} | {d:.1f}% | {g} |")

    # Spot check
    h3("Qualitative Spot Check — Top-3 Swaps")
    spot_names = ["Idli", "Chicken Biryani", "Paneer Butter Masala", "Oats Porridge", "Dosa"]
    row("| Original Meal | Calories | Swap #1 | Swap #2 | Swap #3 |")
    row("|---------------|----------|---------|---------|---------|")
    for tname in spot_names:
        found = next((m for m in meals3 if tname.lower() in m.get("mealName","").lower()), None)
        if not found: continue
        x = np.array([[found.get(c, 0) for c in FEATURE_COLS]])
        xs = scaler.transform(x)
        _, nb_idxs = knn.kneighbors(xs, n_neighbors=6)
        swaps = [meals3[i] for i in nb_idxs[0] if meals3[i]["mealName"] != found["mealName"]][:3]
        swap_cols = [f"{s['mealName']} ({s.get('calories',0)} kcal)" for s in swaps]
        while len(swap_cols) < 3: swap_cols.append("-")
        row(f"| {found['mealName']} | {found.get('calories',0)} kcal | {swap_cols[0]} | {swap_cols[1]} | {swap_cols[2]} |")

except Exception as e:
    row(f"\n**ERROR:** {e}")

# ── 4. TF-IDF Hybrid Matcher ─────────────────────────────────────────────────
h2("4. TF-IDF + Hybrid Matcher  (in-memory, `meal_dataset.json`)")
row("> Runtime TF-IDF + FuzzyWuzzy + Category + Context scoring. Powers the NLP meal logging pipeline.")

DATASET_PATH4 = "meal_dataset.json"
try:
    with open(DATASET_PATH4, encoding="utf-8") as f:
        meals4 = json.load(f)
    row(f"\n- **Meals in index:** {len(meals4)}")

    from ai.tfidf_matcher import init_tfidf_matcher, tfidf_match
    from ai.hybrid_matcher import hybrid_match
    init_tfidf_matcher(meals4)

    ground_truth = [
        ("idli","Idli"),("dosa","Dosa"),("poha","Poha"),("upma","Upma"),
        ("oats","Oats"),("biryani","Biryani"),
        ("paneer butter masala","Paneer Butter Masala"),
        ("dal tadka","Dal Tadka"),("aloo paratha","Aloo Paratha"),
        ("chicken curry","Chicken"),("chole bhature","Chole"),
        ("sambar","Sambar"),("masala chai","Chai"),("egg bhurji","Egg"),
        ("palak paneer","Palak"),("rajma","Rajma"),("khichdi","Khichdi"),
        ("vermicelli","Vermicelli"),("pongal","Pongal"),("rava dosa","Rava"),
    ]

    top1 = top3 = top5 = 0
    detail_rows = []
    for query, expected in ground_truth:
        results = tfidf_match(query, top_k=5)
        names = [r[0].get("mealName","") for r in results]
        h1_hit = any(expected.lower() in n.lower() for n in names[:1])
        h3_hit = any(expected.lower() in n.lower() for n in names[:3])
        h5_hit = any(expected.lower() in n.lower() for n in names)
        if h1_hit: top1 += 1
        if h3_hit: top3 += 1
        if h5_hit: top5 += 1
        hit_label = "Top-1" if h1_hit else ("Top-3" if h3_hit else ("Top-5" if h5_hit else "MISS"))
        top1_name = names[0] if names else "-"
        detail_rows.append((query, expected, top1_name, hit_label))

    n = len(ground_truth)
    acc_top1 = top1 / n
    acc_top3 = top3 / n
    acc_top5 = top5 / n
    g1 = "EXCELLENT" if acc_top1 >= 0.90 else ("GOOD" if acc_top1 >= 0.75 else "NEEDS IMPROVEMENT")
    g3 = "EXCELLENT" if acc_top3 >= 0.90 else ("GOOD" if acc_top3 >= 0.75 else "NEEDS IMPROVEMENT")
    g5 = "EXCELLENT" if acc_top5 >= 0.90 else ("GOOD" if acc_top5 >= 0.75 else "NEEDS IMPROVEMENT")

    row("| Metric | Score | Grade |")
    row("|--------|-------|-------|")
    row(f"| Top-1 Accuracy | {acc_top1*100:.1f}% ({top1}/{n}) | {g1} |")
    row(f"| Top-3 Accuracy | {acc_top3*100:.1f}% ({top3}/{n}) | {g3} |")
    row(f"| Top-5 Accuracy | {acc_top5*100:.1f}% ({top5}/{n}) | {g5} |")

    h3("Query-by-Query Results")
    row("| Query | Expected | Top-1 Result | Hit |")
    row("|-------|----------|--------------|-----|")
    for q, exp, t1, hit in detail_rows:
        row(f"| {q} | {exp} | {t1} | {hit} |")

    # Hybrid confidence
    h3("Hybrid Matcher Confidence Scores")
    row("| Query | Best Match | Hybrid Score | tfidf | fuzzy |")
    row("|-------|------------|--------------|-------|-------|")
    for query, _ in ground_truth[:12]:
        try:
            cands = hybrid_match(query, top_k=1)
            if cands:
                b = cands[0]
                row(f"| {query} | {b['meal'].get('mealName','-')} | {b['score']:.3f} | {b['tfidf_score']:.3f} | {b['fuzzy_score']:.3f} |")
            else:
                row(f"| {query} | - | - | - | - |")
        except Exception as e:
            row(f"| {query} | ERROR: {e} | | | |")

except Exception as e:
    row(f"\n**ERROR:** {e}")

# ── 5. Text Preprocessor ─────────────────────────────────────────────────────
h2("5. Text Preprocessor")
row("> Alias normalization, text cleaning, and spelling correction pipeline.")

try:
    from ai.text_preprocessor import clean_text, normalize_aliases, correct_spelling, init_preprocessor
    miniset = [
        {"mealName": "Idli",                 "searchKeywords": ["idli","steam cake"]},
        {"mealName": "Roti",                 "searchKeywords": ["roti","chapati","flatbread"]},
        {"mealName": "Paneer Butter Masala", "searchKeywords": ["paneer","butter","masala"]},
        {"mealName": "Dal Tadka",            "searchKeywords": ["dal","lentil","tadka"]},
        {"mealName": "Chicken Biryani",      "searchKeywords": ["chicken","biryani","rice"]},
    ]
    init_preprocessor(miniset)

    # Alias tests
    alias_tests = [
        (["dahi"],    ["curd"]),
        (["chawal"],  ["rice"]),
        (["murgh"],   ["chicken"]),
        (["palak"],   ["spinach"]),
        (["chapati"], ["roti"]),
        (["anda"],    ["egg"]),
        (["gosht"],   ["mutton"]),
        (["gobi"],    ["cauliflower"]),
        (["besan"],   ["gram","flour"]),
        (["panir"],   ["paneer"]),
    ]
    h3("Alias Normalization")
    row("| Input | Expected | Result | Pass |")
    row("|-------|----------|--------|------|")
    alias_pass = 0
    for tokens, expected in alias_tests:
        result = normalize_aliases(tokens)
        passed = result == expected
        if passed: alias_pass += 1
        row(f"| {tokens} | {expected} | {result} | {'PASS' if passed else 'FAIL'} |")
    row(f"\n**Alias Accuracy: {alias_pass}/{len(alias_tests)} ({alias_pass/len(alias_tests)*100:.0f}%)**")

    # Clean text tests
    clean_tests = [
        ("I had 2 roti for breakfast",   "2 roti"),
        ("had some dal tadka and rice",  "dal tadka rice"),
        ("Ate PANEER for lunch!",        "PANEER"),
        ("i ate idli with sambar today", "idli sambar"),
    ]
    h3("Text Cleaning")
    row("| Input | Expected | Result | Pass |")
    row("|-------|----------|--------|------|")
    clean_pass = 0
    for inp, exp in clean_tests:
        result = clean_text(inp)
        passed = result.lower() == exp.lower()
        if passed: clean_pass += 1
        row(f"| {inp} | {exp} | {result} | {'PASS' if passed else 'FAIL'} |")
    row(f"\n**Clean Text Accuracy: {clean_pass}/{len(clean_tests)} ({clean_pass/len(clean_tests)*100:.0f}%)**")

    # Spelling correction
    spell_tests = [
        (["rotii"],   "roti"),
        (["panneer"], "paneer"),
        (["daal"],    "dal"),
        (["biyrani"], "biryani"),
        (["chicen"],  "chicken"),
    ]
    h3("Spelling Correction")
    row("| Input | Expected | Result | Pass |")
    row("|-------|----------|--------|------|")
    spell_pass = 0
    for tokens, expected in spell_tests:
        result = correct_spelling(tokens)
        passed = expected.lower() in " ".join(result).lower()
        if passed: spell_pass += 1
        row(f"| {tokens} | {expected} | {result} | {'PASS' if passed else 'FAIL'} |")
    row(f"\n**Spelling Correction Rate: {spell_pass}/{len(spell_tests)} ({spell_pass/len(spell_tests)*100:.0f}%)**")

except Exception as e:
    row(f"\n**ERROR:** {e}")

# ── 6. Throughput Benchmark ───────────────────────────────────────────────────
h2("6. Throughput Benchmark  (Hybrid Matcher)")
try:
    from ai.tfidf_matcher import init_tfidf_matcher
    from ai.hybrid_matcher import hybrid_match
    with open("meal_dataset.json", encoding="utf-8") as f:
        bmeals = json.load(f)
    init_tfidf_matcher(bmeals)

    queries = ["idli","dosa","poha","upma","biryani","paneer butter masala","dal tadka","aloo paratha","chicken curry","sambar"]
    for q in queries: hybrid_match(q, top_k=3)   # warm-up

    RUNS = 100
    t0 = time.perf_counter()
    for _ in range(RUNS):
        for q in queries: hybrid_match(q, top_k=3)
    elapsed = time.perf_counter() - t0
    total_q = RUNS * len(queries)
    qps = total_q / elapsed
    per_q_ms = elapsed / total_q * 1000
    grade_thr = "EXCELLENT" if qps >= 200 else ("GOOD" if qps >= 50 else "LOW")

    row("| Metric | Value |")
    row("|--------|-------|")
    row(f"| Total queries | {total_q:,} |")
    row(f"| Total time | {elapsed*1000:.1f} ms |")
    row(f"| Per-query latency | {per_q_ms:.2f} ms |")
    row(f"| Throughput | {qps:.0f} queries/sec |")
    row(f"| Grade | {grade_thr} |")

except Exception as e:
    row(f"\n**ERROR:** {e}")

# ── Summary ───────────────────────────────────────────────────────────────────
h2("Summary")
row("| Model | Metric | Score | Grade |")
row("|-------|--------|-------|-------|")

try:
    _m = joblib.load("models/nlp_meal_classifier.joblib")
    _df = pd.read_csv("ai/nlp_training_dataset.csv")
    _y = _df["label"]; _X = _df["text"].str.lower()
    _acc = accuracy_score(_y, _m.predict(_X))
    _g = "EXCELLENT" if _acc>=0.90 else ("GOOD" if _acc>=0.75 else "NEEDS IMPROVEMENT")
    row(f"| NLP Meal Classifier | Full-dataset accuracy | {_acc*100:.2f}% | {_g} |")
except: pass

try:
    _m2 = joblib.load("models/food_category_classifier.joblib")
    _t2 = [("roti","Bread"),("dal","Dal"),("rice","Rice"),("chai","Beverage"),("milk","Dairy"),("sabzi","Vegetable")]
    _X2=[x for x,_ in _t2]; _y2=[y for _,y in _t2]
    _a2 = accuracy_score(_y2, _m2.predict(_X2))
    _g2 = "EXCELLENT" if _a2>=0.90 else ("GOOD" if _a2>=0.75 else "NEEDS IMPROVEMENT")
    row(f"| Food Category Classifier | 6-sample accuracy | {_a2*100:.2f}% | {_g2} |")
except: pass

if deviations:
    row(f"| SmartSwap KNN | Within-20%-calorie swaps | {pct20:.1f}% | {grade_knn} |")

row(f"| TF-IDF Hybrid | Top-1 retrieval accuracy | {acc_top1*100:.1f}% | {g1} |")
row(f"| TF-IDF Hybrid | Top-5 retrieval accuracy | {acc_top5*100:.1f}% | {g5} |")

total_time = time.perf_counter()

# Write file
out_path = "ai_accuracy_report.md"
with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print(f"Report written to: {out_path}")
print(f"Lines: {len(lines)}")
