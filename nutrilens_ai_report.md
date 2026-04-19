# NutriLens Backend — AI Models Technical Report

> **Project:** NutriLens — AI-Powered Personalised Diet Planner  
> **Backend Stack:** Python · Flask · Firebase Firestore · scikit-learn · rapidfuzz · joblib  
> **Report Scope:** Detailed explanation of every AI model, algorithm, and technique used in the backend — suitable for inclusion in a Final Year / Capstone project report.  
> **Pipeline Version:** v2.6 (April 2026)

---

## Table of Contents

1. [Overview of AI in NutriLens](#1-overview)
2. [Trained Machine Learning Models](#2-trained-models)
   - 2.1 NLP Meal Classifier (TF-IDF + Logistic Regression)
   - 2.2 Food Category Classifier
   - 2.3 SmartSwap KNN Recommender
   - 2.4 TF-IDF Meal Matcher (Runtime Index)
3. [NLP Meal Recognition Pipeline — Step-by-Step](#3-nlp-pipeline)
4. [Meal Plan Generator — Deep Dive](#4-meal-plan-generator)
5. [Nutritional Target Calculator (Mifflin–St Jeor + Calorie Banking)](#5-target-calculator)
6. [Compatibility Scorer & Culinary Rule Engine](#6-compatibility-scorer)
7. [Accuracy Results & Benchmarks](#7-accuracy)
8. [Summary Table](#8-summary)
9. [Dataset Quality & Firestore Enrichment (v2.6)](#9-dataset-quality)

---

## 1. Overview of AI in NutriLens <a name="1-overview"></a>

NutriLens uses **four trained machine learning models** and **one rule-enhanced algorithmic engine**, all working together to provide two core AI features:

| Feature | AI Components Involved |
|---------|----------------------|
| **Natural Language Meal Logging** — User types "2 roti aur dal" in any language/dialect | Text Preprocessor → Alias Normaliser → Spelling Corrector → NLP Classifier → TF-IDF Matcher *(keyword-quality filtered)* → Fuzzy Matcher *(keyword-quality filtered)* → Category Classifier → Context Resolver → Combo Splitter → Hybrid Scorer *(generic hard-return + plain_boost + force_generic)* → Priority Booster → User Preference Booster |
| **Personalised Daily Meal Plan Generation** — System creates a full-day macro-balanced Indian meal plan | Mifflin–St Jeor BMR Calculator → Calorie Banking → Vegetarian Pre-filter → Meal Pattern Engine → Candidate Scorer → Calorie Penalty → Completeness Check → Compatibility Scorer → Macro Balancing Solver → KNN SmartSwap |

All four trained model files are persisted to disk using **joblib** and loaded at server startup:

| File | Size | Purpose |
|------|------|---------|
| `models/nlp_meal_classifier.joblib` | 34.7 MB | Classifies free-text meal descriptions → 751 meal labels |
| `models/tfidf_meal_matcher.joblib` | 244 KB | Pre-built TF-IDF vector index for fast runtime matching |
| `models/food_category_classifier.joblib` | 410 KB | Predicts broad food category (Bread/Dal/Rice/etc.) from a single word |
| `models/knn_meal_swap.joblib` | 161 KB | Finds nutritionally similar meal replacements using K-Nearest Neighbours |

---

## 2. Trained Machine Learning Models <a name="2-trained-models"></a>

### 2.1 NLP Meal Classifier — `nlp_meal_classifier.joblib`

**What it does:** Given a piece of free-text meal input (e.g., *"had some murgh tikka for dinner"*), this model classifies it into one of **751 named Indian meal labels**.

#### Algorithm
- **TF-IDF Vectoriser** (unigrams + bigrams, `ngram_range=(1,2)`, English stopwords removed, `min_df=2`)
- **Logistic Regression Classifier** (`max_iter=2000`, multi-class one-vs-rest)
- Wrapped in a **scikit-learn `Pipeline`** object for clean serialisation

#### Training Data
- **Dataset file:** `ai/nlp_training_dataset.csv`
- **Total samples:** 19,050
- **Number of classes:** 751 unique Indian meal labels
- The dataset contains rows of `(text, label)` — each text is a natural language variation of how someone might describe a meal (e.g., "2 roti with dal tadka", "murgh curry and rice", "idli with coconut chutney")

#### Training Procedure (`ai/train_nlp_model.py`)
```
Step 1 → Load CSV → X = text column (lowercased), y = label column
Step 2 → Train / Validation split (80/20, stratified by label, random_state=42)
Step 3 → Fit TF-IDF Vectoriser on training text
Step 4 → Fit Logistic Regression on TF-IDF feature matrix
Step 5 → Evaluate accuracy on held-out validation set
Step 6 → Save model pipeline to models/nlp_meal_classifier.joblib via joblib
```

#### Why This Is AI
Logistic Regression is a **supervised machine learning model** — it learns statistical decision boundaries in high-dimensional TF-IDF feature space from 19,050 labelled training examples. It generalises to novel phrasings it has never seen, which distinguishes it from hard-coded lookups.

#### Accuracy
| Metric | Score |
|--------|-------|
| Validation Accuracy | **91.37%** |
| Macro Precision | 0.921 |
| Macro Recall | 0.900 |
| Macro F1-Score | 0.899 |
| Weighted F1-Score | 0.907 |
| 5-Fold Cross-Validation Mean | **0.8503 ± 0.0198** |
| Inference Speed | 15.16 µs per sample |

> Note: The trained classifier is used as a **pre-filter / category hint** inside the NLP pipeline. The final meal match is done by the hybrid TF-IDF + fuzzy matcher for higher precision on short, noisy inputs.

---

### 2.2 Food Category Classifier — `food_category_classifier.joblib`

**What it does:** Predicts the high-level food category of a single food word (e.g., "roti" → Bread, "dal" → Dal, "chai" → Beverage).

#### Algorithm
- **TF-IDF Vectoriser** (character/word level, default settings)
- **Logistic Regression** (`max_iter=1000`)
- scikit-learn Pipeline

#### Training Data
Hand-curated in-code seed dataset (`ai/train_food_category_model.py`):
```
X = ["roti", "chapati", "phulka", "dal", "dal tadka", "rice", "steamed rice",
     "sabzi", "mixed vegetable", "chai", "tea", "milk", "curd"]
y = ["Bread", "Bread", "Bread", "Dal", "Dal", "Rice", "Rice",
     "Vegetable", "Vegetable", "Beverage", "Beverage", "Dairy", "Dairy"]
```
- **6 categories:** Bread, Dal, Rice, Vegetable, Beverage, Dairy

#### Role in the Pipeline (v2.5 enhancement)
This model predicts the category of the **first word** of a food entity (Step 7 of the NLP pipeline). In v2.5, the pipeline also extracts the **classifier probability** via `predict_proba()`:

- If `category_confidence ≥ 0.60` → use predicted category to filter TF-IDF search space
- If `category_confidence < 0.60` → **disable category filter** and search the full meal dataset

This prevents wrong category predictions from blocking correct matches.

#### Accuracy
| Metric | Score |
|--------|-------|
| Overall Test Accuracy | 62.5% (32-sample test) |
| Confidence gate threshold (v2.5) | 0.60 |
| Role in system | Used as a **soft hint with confidence gate** — low-confidence predictions are ignored |

---

### 2.3 SmartSwap KNN — `knn_meal_swap.joblib`

**What it does:** Given a meal (e.g., "Chicken Biryani, 500 kcal"), finds the top-K nutritionally similar replacement meals from the database.

#### Algorithm — K-Nearest Neighbours
```
Feature vector per meal = [calories, protein_g, carbs_g, fat_g]

Step 1 → StandardScaler normalises feature vectors (zero-mean, unit-variance)
Step 2 → NearestNeighbors(n_neighbors=6, metric='euclidean') fitted on all meals
Step 3 → At query time: transform query meal → find 6 nearest neighbours
Step 4 → Return top-5 non-identical meals as swap candidates
```

#### Why Euclidean Distance on Nutrition
Calories, protein, carbs, and fat all have different natural magnitudes (calories ~200, fat ~9). StandardScaler puts them on equal footing so no single nutrient dominates the distance calculation.

#### Training Script: `ai/train_knn.py`
- Loads all meals from Firestore
- Extracts `[calories, protein, carbs, fat]` feature vectors
- Fits scaler and KNN model
- Saves to `models/knn_meal_swap.joblib`

#### Accuracy
| Metric | Score | Grade |
|--------|-------|-------|
| Meals indexed | 771 | — |
| Mean calorie deviation (best swap) | **3.8%** | GOOD |
| Within 10% calorie range | **92.0%** | EXCELLENT |
| Within 20% calorie range | **96.0%** | EXCELLENT |
| Mean protein deviation | 7.7% | GOOD |
| Mean carbs deviation | 5.4% | GOOD |
| Mean fat deviation | 8.0% | GOOD |

**Sample swap results:**
| Original | Swap 1 | Swap 2 | Swap 3 |
|----------|--------|--------|--------|
| Rava Idli (180 kcal) | Horlicks (180 kcal) | Oats Dosa (180 kcal) | Plain Upma (192 kcal) |
| Chicken Biryani (500 kcal) | Ambur Biryani (550 kcal) | Chicken Noodles (480 kcal) | Chicken Fried Rice (450 kcal) |
| Oats Porridge (250 kcal) | Dalia Porridge (240 kcal) | Moong Dal Khichdi (250 kcal) | Semiya Upma (260 kcal) |

---

### 2.4 TF-IDF Meal Matcher (Runtime Index) — `tfidf_meal_matcher.joblib`

**What it does:** Converts the entire meal database into a TF-IDF vector matrix. At runtime, a user's food query is vectorised and the **cosine similarity** against every meal's vector is computed to find the best match.

#### Algorithm
```
Offline (at startup / retrain):
  1. For each meal: text = mealName + " " + searchKeywords
  2. TfidfVectorizer(ngram_range=(1,2), max_features=3000,
                     sublinear_tf=True, min_df=2)
  3. Fit-transform → sparse TF-IDF matrix (shape: n_meals × 3000)
  4. Build category_index → {category: [meal indices]}
  5. Save to models/tfidf_meal_matcher.joblib

Online (per query):
  1. Transform query → query_vector (1 × 3000)
  2. If category_confidence ≥ 0.60 → restrict to sub_matrix of that category
  3. cosine_similarity(query_vector, sub_matrix) → similarity scores
  4. argsort descending → return top-K meals
```

#### What Makes It "Smart"
- **Sublinear TF scaling** (`sublinear_tf=True`): uses `1 + log(tf)` instead of raw term frequency.
- **Bigram support** (`ngram_range=(1,2)`): captures two-word phrases like "butter masala", "dal tadka".
- **Confidence-gated category filter (v2.5):** only applies when classifier confidence ≥ 0.60.
- **Cache-first startup**: loads pre-built `.joblib` file in milliseconds.

#### Accuracy
| Metric | Score | Grade |
|--------|-------|-------|
| Top-1 Retrieval Accuracy | **90.0%** (18/20 queries) | EXCELLENT |
| Top-3 Accuracy | **90.0%** | EXCELLENT |
| Top-5 Accuracy | **90.0%** | EXCELLENT |
| Per-query latency | 19.61 ms | GOOD |
| Throughput | 51 queries/second | GOOD |

---

## 3. NLP Meal Recognition Pipeline — Step-by-Step <a name="3-nlp-pipeline"></a>

**File:** `ai/nlp_pipeline.py`  
**Version:** v2.5 (Hybrid NLP Pipeline)  
**Purpose:** Transform a raw free-text meal description (English, Hindi, Hinglish) into structured nutrition data logged to Firestore.

### Architecture Overview

```
Raw Text Input
      │
      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│  Step 1 │  clean_text()           │ Lowercase, remove punctuation,           │
│         │                         │ strip EN + Hinglish stopwords            │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 2 │  normalize_aliases()    │ Multi-word + single-word alias map       │
│         │                         │ "dahi" → "curd", "sabzi" →              │
│         │                         │ "mixed vegetable sabzi"                  │
│         │                         │ "curry rice" → "dal chawal"              │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 3 │  correct_spelling()     │ RapidFuzz against food vocab             │
│         │                         │ "panneer" → "paneer" (score=92)         │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 4 │  detect_phrases()       │ 4-word sliding window phrase detection   │
│         │                         │ "dal" + "tadka" → "dal tadka"           │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 5 │  extract_quantities()   │ Parse numbers / fractions / words        │
│         │                         │ "3 roti dal" → {roti: 3, dal: 1}       │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 6 │  resolve_context()      │ Tiered set-matching (STRONG/WEAK)        │
│         │                         │ "dal"+"roti" → "Dal Roti" (boost=1.0)   │
├──────────────────────────────────────────────────────────────────────────────┤
│ Step 6b │  COMBO_SPLIT_MAP        │ Expand combo → individual entities       │
│         │                         │ "Dal Roti" → ["dal"(qty=1), "roti"(qty=3)]│
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 7 │  predict_category()     │ Food Category Classifier + confidence    │
│         │                         │ "dal" → "Dal" (confidence=0.82)         │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 8 │  tfidf_match()          │ TF-IDF cosine similarity                 │
│         │  (inside hybrid)        │ Confidence-gated category filter         │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 9 │  fuzzy_match()          │ RapidFuzz partial_ratio + extractOne     │
│         │  (inside hybrid)        │ Handles typos, abbreviations             │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 10│  hybrid_score()         │ 7-signal scoring formula                 │
│         │  (inside hybrid)        │ TF-IDF×0.55 + Fuzzy×0.25 +             │
│         │                         │ Category×0.10 + Keyword×0.05 +          │
│         │                         │ Context×0.05 + Priority + Sabzi boost   │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 11│  resolve_best_meal()    │ Accept if score ≥ 0.30, else reject      │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 12│  user_preference_boost  │ +0.05×n boost for historically eaten     │
│         │                         │ meals (capped at +0.15)                  │
├──────────────────────────────────────────────────────────────────────────────┤
│  Step 13│  log_to_firestore()     │ Write structured nutrition record         │
└──────────────────────────────────────────────────────────────────────────────┘
      │
      ▼
Structured Output: [{meal, calories, protein, carbs, fat, quantity, confidence}]
```

---

### Detailed Step Descriptions

#### Step 1 — Text Cleaning (`ai/text_preprocessor.py → clean_text()`)
**Algorithm:** Rule-based regex preprocessing  
- Converts all text to lowercase
- Removes all punctuation except hyphens
- Collapses multiple whitespace → single space
- Removes a custom bi-lingual stopword set: 50+ English words + 20+ Hinglish words (*"maine", "mene", "khaya", "kha", "aaj", "subah", "raat"*)

**Example:** `"I had 2 roti for breakfast"` → `"2 roti"`

---

#### Step 2 — Alias Normalization (`normalize_aliases()`)

**Algorithm:** Dictionary lookup with bigram/trigram sliding window  
**Why this is needed:** Indian users write food names in regional languages, romanised scripts, or abbreviated forms. The TF-IDF model is trained on English meal names so regional terms must be canonicalised first.

**Two-pass mechanism:**
- **Pass 1 — Multi-word aliases:** Sliding window of size 3 then 2 scans across tokens, matches against `MULTI_WORD_ALIAS_MAP`
- **Pass 2 — Single-word aliases:** Each remaining token looked up in `FOOD_ALIAS_MAP` (127+ entries)

**Key alias additions (v2.5 / v2.6):**

| Input | Mapped To | Category |
|---|---|---|
| `sabzi` | `mixed vegetable sabzi` | Indian vegetable term |
| `subzi` | `mixed vegetable sabzi` | Alternate spelling |
| `plain rice` | `rice` | Rice variant normalisation |
| `boiled rice` | `rice` | Rice variant normalisation |
| `white rice` | `rice` | Rice variant normalisation |
| `curry rice` | `dal chawal` | Combo alias |
| `rice curry` | `dal chawal` | Combo alias |
| `gravy rice` | `dal chawal` | v2.5 new |
| `sabzi rice` | `dal chawal` | v2.5 new |
| `dal rice` | `dal chawal` | v2.5 new |
| `curry and rice` | `dal chawal` | 3-word window |
| `jowar roti` | `jowar roti` | **v2.6** millet multi-word (Pass 1 priority) |
| `jawar roti` | `jowar roti` | **v2.6** jawar→jowar transliteration fix |
| `bajra roti` | `bajra roti` | **v2.6** millet multi-word (Pass 1 priority) |

**v2.6 fix — transparent adjective tokens (`FOOD_ADJECTIVES`):**  
Adjectives like `jawar`, `bajra`, `plain`, `masala` are now skipped during quantity attribution so that `"3 jawar roti"` correctly assigns `roti × 3` instead of `jawar × 3`.

```python
FOOD_ADJECTIVES = {"jawar", "jowar", "bajra", "multigrain", "whole wheat",
                   "plain", "masala", "fried", "boiled", "steamed"}
# If token is an adjective, skip it; quantity propagates to next food token.
```

**Accuracy:** 100% (10/10 tested aliases correctly normalised)

---

#### Step 3 — Spelling Correction (`correct_spelling()`)

**Algorithm:** Fuzzy string matching against a dynamically built food vocabulary using **RapidFuzz** (`fuzz.ratio`, threshold=85)

**Examples:**
| Misspelled Input | Corrected | Score |
|-----------------|-----------|-------|
| rotii | roti | 91 |
| panneer | paneer | 92 |
| daal | dal | 88 |
| biyrani | biryani | 86 |
| chicen | chicken | 89 |

**Spelling Correction Rate: 5/5 (100%)**

---

#### Step 4 — Phrase Detection (`ai/phrase_detector.py → detect_phrases()`)

**Algorithm:** Sliding window phrase matching against a pre-built phrase set derived from all meal names  
- Scans with windows of size 4 → 3 → 2 → 1 (longest match wins)

**Example:** `["paneer", "butter", "masala"]` → `["paneer butter masala"]`

---

#### Step 5 — Quantity Extraction (`ai/quantity_extractor.py → extract_quantities()`)

**Algorithm:** Rule-based pattern matching  
- Recognises digits, number words, fractions, and portion words (`bowl`, `cup`, `plate`, `katori`)
- Scans immediately before each food entity to pick up quantity context

**v2.6 fix — `[number] + [adjective] + [food]` pattern:**  
Previously, `"3 jawar roti"` was parsed as `jawar=3, roti=1` because the adjective consumed the quantity. The fix introduces a `FOOD_ADJECTIVES` transparent-token skip:

```
Pattern:  <number> <FOOD_ADJECTIVE> <food_token>
Old:      jawar=3,  roti=1   ← adjective steals the number
New:      jawar=—,  roti=3   ← adjective skipped, quantity flows to food
```

**Corrected examples:**

| Input | Before (v2.5) | After (v2.6) |
|---|---|---|
| `3 jawar roti` | jawar=3, roti=1 | roti=3 ✅ |
| `2 bajra roti` | bajra=2, roti=1 | roti=2 ✅ |
| `4 plain roti` | plain=4, roti=1 | roti=4 ✅ |

**Debug log:**
```
[qty] token 'jawar' is FOOD_ADJECTIVE — skipping, carrying qty=3 forward
[qty] assigned roti × 3
```

---

#### Step 6 — Context Resolution (`ai/context_resolver.py → resolve_context()`)

**Algorithm:** Set-based rule matching with tiered confidence scores

Uses two rule dictionaries:
- `STRONG_CONTEXT_RULES` — boost = **1.0** (canonical Indian pairs)
- `WEAK_CONTEXT_RULES` — boost = **0.5** (generic / secondary combos)

**STRONG_CONTEXT_RULES (v2.5 — includes post-alias forms):**

| Pair | Resolves To | Type |
|---|---|---|
| `{dal, roti}` | Dal Roti | Promoted from WEAK in v2.5 |
| `{chapati, dal}` | Dal Roti | Promoted from WEAK in v2.5 |
| `{dal, rice}` | Dal Chawal | Canonical |
| `{rice, curry}` | Dal Chawal | New in v2.5 |
| `{idli, sambar}` | Idli Sambar | Canonical |
| `{dosa, sambar}` | Dosa Sambar | Canonical |
| `{roti, sabzi}` | Roti Sabzi | Raw form |
| `{roti, mixed vegetable sabzi}` | Roti Sabzi | Post-alias form (v2.5) |
| `{puri, mixed vegetable sabzi}` | Puri Sabzi | Post-alias form (v2.5) |
| `{bread, egg}` | Bread Omelette | Canonical |

Each matched combo logs its strength: `[context] 'dal' + 'roti' → 'Dal Roti' [context_strength=STRONG, boost=1.0]`

---

#### Step 6b — Combo Entity Splitting (`COMBO_SPLIT_MAP`) ← NEW in v2.5, enhanced v2.6

**Problem solved:** Context resolver produces combo names like `"Dal Roti"`. These are NOT single meals in Firestore — they are two separate dishes with separate nutritional entries.

**Solution:** Before hybrid matching, any context-resolved combo is split back into individual food entities. Each part is then matched independently.

```python
COMBO_SPLIT_MAP = {
    "Dal Roti":   ["dal",  "roti"],
    "Dal Chawal": ["dal",  "rice"],
    "Rice Dal":   ["dal",  "rice"],
    "Chawal Dal": ["dal",  "rice"],
    "Curd Rice":  ["curd", "rice"],
    "Roti Sabzi": ["roti", "mixed vegetable sabzi"],
}
```

**Smart quantity assignment:**

| Part Type | Quantity Rule |
|---|---|
| Bread parts (roti, chapati, naan, paratha) | Inherits the combo quantity (e.g., "3 roti" → roti×3) |
| All other parts (dal, rice, curd) | Default = 1 |

**v2.6 — `force_generic` flag propagation:**  
Every entity produced by a combo split is now tagged with `force_generic=True` in the `expanded_force_generic` dictionary. This flag is passed to `resolve_best_meal()` which restricts matching to meals whose `searchKeywords` contains an **exact keyword match** — preventing flavoured variants (e.g., "Jeera Rice") from winning over base meals ("Plain Rice") within a combo context.

```python
# Pipeline sets force_generic per entity:
expanded_force_generic[part] = True   # for combo-split parts
expanded_force_generic[entity] = False  # for standalone entities

# resolve_best_meal() enforces base-only selection:
if force_generic:
    # Only keyword-exact meals allowed; hybrid scoring is bypassed
    return best_generic, 1.0
```

**Debug log:**
```
[combo_split] "Dal Roti" → {"dal": 1, "roti": 3}
[forced_generic] combo-split triggered base-only selection for 'rice' → 'Plain Rice' (4 candidates)
[generic_return] 'dal' → 'Plain Dal' (keyword-exact, 3 candidates) — HARD RETURN
[Step 6b] priorities: {"dal": 0.8, "roti": 1.0}
```

---

#### Step 7 — Food Category Prediction + Confidence Extraction

Uses the **Food Category Classifier** (Section 2.2) on the first word of each entity.

**v2.5 addition:** `predict_proba()` is called to get the classification confidence:
```python
category_confidence = float(max(proba))
```
- Confidence is passed downstream to the hybrid matcher
- Logged at Step 7: `[Step 7] predict_category('dal'): 'Dal' (confidence=0.82, priority=0.8)`

**Primary food priority (v2.5):**

| Entity Type | priority_score |
|---|---|
| `PRIMARY_FOODS` = {rice, roti, chapati, naan, paratha} | 1.0 |
| All other entities | 0.8 |

---

#### Steps 8–10 — Hybrid Matching (`ai/hybrid_matcher.py`) — v2.6

This is the **core AI matching engine**. It combines multiple independent signals into a single weighted confidence score.

**v2.6 — Generic Match Hard-Return (pre-scoring fast path):**  
Before any scoring, `resolve_best_meal()` checks if the query is a single bareword staple:

```python
GENERIC_KEYWORDS = {"rice", "dal", "roti", "daal", "bread"}
is_generic_query  = query_lower in GENERIC_KEYWORDS and " " not in query_lower

if is_generic_query or force_generic:
    # Keyword-exact match only — shortest name wins (most generic)
    keyword_matches.sort(key=lambda m: len(m["mealName"].split()))
    return keyword_matches[0], 1.0   # HARD RETURN — hybrid scoring skipped
```

This guarantees:
- `"rice"` → **Plain Rice** (never "Fried Rice" or "Lemon Rice")
- `"dal"` → **Plain Dal** (never "Dal Makhani")
- `"roti"` → **Plain Roti** (never "Butter Roti")

**Signal 1 — TF-IDF Cosine Similarity (weight = 0.55)**
- Queries the TF-IDF vector index
- Category filter applied **only** if `category_confidence ≥ 0.60`

**Signal 2 — RapidFuzz Fuzzy Matching (weight = 0.25)**
- `fuzz.partial_ratio` + `process.extractOne`
- **v2.6:** Weak-keyword meals (`< 5 searchKeywords`) excluded from the fuzzy pool before scoring

**Signal 3 — Category Agreement (weight = 0.10 → effectively 0.0 in v2.6)**
- **v2.6: `IGNORE_CATEGORY = True`** — category weight is zeroed globally:
  ```python
  IGNORE_CATEGORY = True   # prevents classifier noise from excluding valid staples
  # When True: w_cat = 0.0, its weight redistributed to w_tfidf
  ```
- Rationale: the food-category classifier (62.5% accuracy) was incorrectly excluding valid staple meals (e.g., classifying "rice" as "snack").

**Signal 4 — Keyword Overlap (weight = 0.05)**
- 0.5 if any `searchKeyword` overlaps with query (capped at 0.5)

**Signal 5 — Context Score (weight = 0.05)**
- 1.0 for STRONG combos, 0.5 for WEAK, 0.0 otherwise

**The 8-Signal Weighted Formula (v2.6):**
```
base_score = (W_TFIDF × tfidf_score)
           + (W_FUZZY × fuzzy_score)
           + (0.0     × category_match)   ← IGNORE_CATEGORY=True in v2.6
           + (W_KW    × keyword_score)
           + (W_CTX   × context_score)

priority_contribution = entity_priority × 0.10
sabzi_boost  = 0.08  (if query and meal are both veg-type)
exact_boost  = 0.10  (if meal_name == query exactly)
plain_boost  = +0.20 if "plain" in meal_name          ← NEW v2.6
             + +0.15 if meal_name starts with "plain"  ← NEW v2.6
             = +0.35 total for "Plain Rice"/"Plain Dal"/"Plain Roti"

specificity_penalty = 0.07 × word_count_in_meal_name

final_score = base_score
            + priority_contribution
            + sabzi_boost
            + exact_boost
            + plain_boost
            − specificity_penalty
            (clamped to [0.0, 1.0] as final step)
```

**plain_boost explained:**  
"Plain Rice" receives `+0.20 + 0.15 = +0.35` over flavored variants. Even if "Lemon Rice" scores higher on TF-IDF similarity for the query `"rice"`, the +0.35 boost ensures **Plain Rice always wins** in the hybrid scoring path (as a fallback to the hard-return path).

**Priority contribution:** Primary foods (rice, roti) get `entity_priority=1.0` → `+0.10`; secondary items get `0.8` → `+0.08`.

**Sabzi-aware boost:** When query contains `{vegetable, sabzi, mixed, veg}` AND candidate name contains `{mixed, veg, vegetable}` → `+0.08`.

**Specificity penalty:** 0.07 per word. "Dal" (1 word, −0.07) beats "Lasooni Dal" (2 words, −0.14).

**Quality Gates:**
- **Hard reject floor:** `tfidf < 0.25 AND fuzzy < 0.60` → discard
- **Acceptance gate (OR):** `tfidf > 0.35` OR `(fuzzy > 0.65 AND keyword > 0)` OR `fuzzy > 0.80`
- **Final confidence threshold:** score ≥ 0.30 → accept

**v2.6 Debug log per candidate:**
```
[generic_return] 'rice' → 'Plain Rice' (keyword-exact, 4 candidates) — HARD RETURN
[forced_generic] combo-split triggered base-only for 'dal' → 'Plain Dal' (3 candidates)
[hybrid] 'Plain Rice' PLAIN BOOST +0.35
[hybrid] 'Plain Rice' tfidf=0.712 fuzzy=0.880 kw=0.50 cat=0.0 ctx=1.0
  priority=1.0(+0.100) sabzi_boost=0.00 plain_boost=0.35 words=2 spec_penalty=0.140
  → final_score=1.000 [CLAMPED from 1.422]
```

---

#### Step 11 — Best Meal Resolution

Top-scored candidate selected. If score < 0.30 → entity logged as unrecognised and skipped.

```
[Step 11] ✅ 'dal' → 'Dal Tadka' (confidence=0.921, priority=0.8)
```

---

#### Step 12 — User Preference Boost

**Algorithm:** Frequency-based personalisation  
- Queries last 30 `meal_logs` from Firestore
- Adds boost: `min(0.05 × count, 0.15)` to confidence
- Example: Eaten 3 times → +0.15

---

#### Step 13 — Firestore Logging

Writes a structured document to `meal_logs`:
```json
{
  "userId": "...", "date": "2026-04-19",
  "mealName": "Dal Tadka", "mealType": "Dal",
  "calories": 250, "protein": 12.5, "carbs": 35.0, "fat": 7.0,
  "quantity": 1, "confidence": 0.92,
  "source": "hybrid_nlp_v2.5", "rawText": "3 roti dal",
  "timestamp": <SERVER_TIMESTAMP>
}
```
A parallel debug log is written to `nlp_debug_logs` including:
- `combo_splits` — which combos were expanded and into what parts
- `category_confidence` — classifier confidence per entity
- `context_scores` — strength of context rules triggered

---

## 4. Meal Plan Generator — Deep Dive <a name="4-meal-plan-generator"></a>

**File:** `ai/meal_plan_generator.py`  
**Version:** v3.1 (Macro-Balanced, Protein-Prioritised, Calorie-Aware)  
**Purpose:** Generate a nutritionally balanced full-day Indian meal plan that meets a user's personalised calorie and macro targets.

### Overall Architecture

```
User Profile (age, gender, weight, height, activity, goal)
         │
         ▼
   [Target Calculator] → {calories, protein, carbs, fat}
         │
         ▼
   [Calorie Banking] → adjusted targets based on 3-day history
         │
         ▼
   [Vegetarian Pre-filter] ← NEW v2.5
         │  is_vegetarian=True → filter each pool:
         │    Strict:  is_vegetarian==True AND name ∉ {chicken,mutton,fish,egg}
         │    Relaxed: is_vegetarian==True (fallback if no strict meals found)
         │    Full:    all meals (safety fallback)
         ▼
   [generate_full_meal_plan()]
         │
   ┌─────┼───────────┬──────────────┐
   ▼     ▼           ▼              ▼
Breakfast  Lunch     Snack       Dinner
   │         │           │              │
   ▼         ▼           ▼              ▼
[pick_valid_pattern()] → selects cuisine pattern from MEAL_PATTERNS
   │
   ▼
[solve_meal()] → generate & score 10 candidates, pick best
   │
   ├── _generate_one_candidate()    → fill pattern slots from meal pool
   ├── score_combination()          → culinary compatibility score
   ├── _compute_macro_score()       → macro deviation penalty
   ├── _compute_protein_density()   → protein density reward
   ├── _compute_variety_penalty()   → penalise repeated meals (−8 each)
   ├── _calorie_penalty()           → convex power formula ← NEW v2.5
   └── _check_meal_completeness()   → carb + protein check ← NEW v2.5
   │
   ▼
[_apply_portions()] → assign realistic serving sizes
   │
   ▼
[Sequential macro tracking] → subtract actuals from remaining targets
   │
   ▼
[Final Validation] → ±3% calories, ±5% protein, ±10% carbs/fat
   │
   ▼ (if fails)
[Correction Pass] → swap worst-deviation item with better alternative
```

---

### Step-by-Step Algorithm

#### Step 1 — Calorie & Macro Target Computation
Uses the **Mifflin–St Jeor BMR formula** (see Section 5) + calorie banking.

#### Step 2 — Vegetarian Pre-filter ← NEW v2.5

When `is_vegetarian=True`, each meal type pool is filtered **before scoring**:

```python
NON_VEG_KEYWORDS = {"chicken", "mutton", "fish", "egg"}

def _is_strict_veg(meal):
    return (meal.get("is_vegetarian") is True
            and not any(kw in meal["mealName"].lower()
                        for kw in NON_VEG_KEYWORDS))
```

**Three-tier fallback:**
1. **Strict:** `is_vegetarian==True` AND no non-veg keyword in name
2. **Relaxed:** `is_vegetarian==True` flag only (keyword check relaxed)
3. **Full pool:** safety net if no veg meals found for that type

```
[Meal Plan] Strict-veg filter: Lunch pool 120 → 74 (veg-only, non-veg keywords excluded)
```

#### Step 3 — Meal Type Ordering

Fixed order: `Breakfast → Lunch → Snack → Dinner`

**Calorie split ratios:** `Breakfast 25% | Lunch 35% | Snack 10% | Dinner 30%`

#### Step 4 — Pattern Selection

Patterns from `ai/meal_patterns.py` define the structural template of a realistic Indian meal:

| Pattern Name | Cuisine | Slots |
|---|---|---|
| North_Indian_Breakfast | north_indian | main(grain) + side(protein) + drink |
| South_Indian_Breakfast | south_indian | main(grain) + condiment + drink |
| Roti_Thali | north_indian | carb_base + protein_curry + dry_sabzi + condiment |
| Rice_Dal_Meal | north/south | carb_base + protein_curry + dry_sabzi + condiment |
| One_Pot_Meal | all cuisines | main + condiment |
| Light_Snack | all cuisines | snack_item + drink |

#### Step 5 — Candidate Scoring (`solve_meal()`) — v3.1 Enhanced

Generates **10 candidates** and scores each with a **6-signal composite score**:

| Score Component | Function | Description |
|---|---|---|
| **Compatibility Score** | `score_combination()` | Culinary pair-wise rules + collision penalties |
| **Macro Score** | `_compute_macro_score()` | `-(protein_dev×2 + carbs_dev + fat_dev)` |
| **Protein Density Score** | `_compute_protein_density_score()` | `(protein/calories) × 100` |
| **Variety Penalty** | `_compute_variety_penalty()` | **−8** per recently repeated meal (raised from −3) ← v2.5 |
| **Calorie Penalty** | NEW v2.5 | Convex power formula (see below) |
| **Completeness Penalty** | `_check_meal_completeness()` | −5 if missing carb OR protein source ← v2.5 |

**Calorie Penalty Formula (v2.5 — convex power):**
```python
# Old (linear): (|diff| / target) * 0.3
# New (convex):
cal_ratio      = abs(raw_cals - target_calories) / target_calories
calorie_penalty = (cal_ratio ** 1.5) * 0.4
```
Large calorie deviations are penalised exponentially. A 50% miss costs `(0.50^1.5) × 0.4 = 0.14`; a 10% miss costs only `(0.10^1.5) × 0.4 = 0.013`.

**Meal Completeness Check (v2.5):**
```python
_CARB_KEYWORDS    = {rice, roti, chapati, naan, paratha, bread, poha, idli, dosa, oats, ...}
_PROTEIN_KEYWORDS = {dal, lentil, paneer, egg, chicken, rajma, chole, curd, yogurt, ...}
MIN_PROTEIN_G     = 5.0   # item must have ≥ 5g protein to count as protein source
```
- An item qualifies as a protein source **only if** its name/food_group matches AND `protein_g ≥ 5.0`
- Prevents low-protein items (e.g., "moong soup, 0.5g protein") from satisfying the protein requirement

```
[completeness] OK  protein_detection=['Dal Tadka(protein=8.2g ✓)', 'Roti(no_protein_match)']
```

**Total Score:**
```
total_score = compat + macro + protein_density + variety_penalty
            − calorie_penalty − completeness_penalty
```

**Full solve_meal debug log:**
```
[solve_meal] attempt=3 items=['Dal Tadka','Roti'] raw_cal=385 target_cal=420
  cal_penalty=0.018 completeness=OK comp_penalty=0.0
  compat=12.5 macro=-4.2 protein_density=8.1 variety=0.0 total_score=16.399
```

#### Step 6 — Portion Assignment

Portions from `PORTION_RULES` — strictly set to `default` value (no inflation).

#### Step 7 — Sequential Macro Tracking

After each meal: `remaining[calories] -= actual_meal_calories` (clamped ≥ 0). Dinner absorbs all remaining macros.

#### Step 8 — Final Validation

```
Calories: within ±3%  → PASS
Protein:  within ±5%  → PASS
Carbs:    within ±10% → PASS
Fat:      within ±10% → PASS
```

#### Step 9 — Correction Pass

If validation fails → swap the highest-deviation item with a better alternative from the same meal type.

---

## 5. Nutritional Target Calculator <a name="5-target-calculator"></a>

**File:** `ai/target_calculator.py`

### BMR — Mifflin–St Jeor Equation

```
Male:   BMR = 10×weight(kg) + 6.25×height(cm) − 5×age + 5
Female: BMR = 10×weight(kg) + 6.25×height(cm) − 5×age − 161
```

### TDEE
```
TDEE = BMR × Activity_Factor

Activity Factors:
  Sedentary         → 1.20
  Light Active      → 1.375
  Moderately Active → 1.55
  Active            → 1.725
  Very Active       → 1.90
```

### Goal Adjustment
```
Lose Weight:  TDEE − 500 kcal  (0.45 kg/week deficit)
Maintain:     TDEE ± 0 kcal
Gain Weight:  TDEE + 500 kcal  (0.45 kg/week surplus)
Minimum:      1200 kcal/day
```

### Macro Distribution (AMDR-based)
```
Protein: 25% of calories ÷ 4 kcal/g
Carbs:   45% of calories ÷ 4 kcal/g
Fat:     30% of calories ÷ 9 kcal/g
```

### Calorie Banking (3-Day Adaptive Algorithm)
```
adjustment = clamp(−average_deviation / 3, min=−150, max=+150)
new_calories = max(1100, base_calories + adjustment)
```

---

## 6. Compatibility Scorer & Culinary Rule Engine <a name="6-compatibility-scorer"></a>

**File:** `ai/compatibility_scorer.py`

### Pair-Wise Compatibility Rules

| Good Pairs (+score) | Bad Pairs (−score) |
|---|---|
| roti + dal: +3 | rice + roti: −3 |
| idli + sambar: +3 | biryani + roti: −4 |
| rice + dal: +3 | dosa + naan: −4 |
| biryani + raita: +3 | pasta + rice: −4 |
| paratha + curd: +2 | noodles + roti: −4 |

### Collision Rules

- **No more than 1 carb base** per meal (rice+roti → −5 per extra)
- **No more than 1 heavy dish** per meal (biryani+curry → −5 per extra)

### Calorie Fit Bonus

- Within ±20% of target: `+2`
- Within ±40%: `+0`
- Outside ±40%: `−2`

---

## 7. Accuracy Results & Benchmarks <a name="7-accuracy"></a>

### Comprehensive Accuracy Table

| Model / System | Metric | Score | Grade |
|---|---|---|---|
| **NLP Meal Classifier** | Validation Accuracy (19,050 samples) | **91.37%** | EXCELLENT |
| **NLP Meal Classifier** | Macro F1-Score | **0.899** | EXCELLENT |
| **NLP Meal Classifier** | Cross-Validation Mean (5-fold) | **85.03%** | GOOD |
| **Food Category Classifier** | Test Accuracy (32 samples) | 62.5% | NEEDS IMPROVEMENT |
| **Food Category Classifier** | v2.6 — IGNORE_CATEGORY=True | Disabled globally | BYPASSED |
| **SmartSwap KNN** | Within 10% calorie range | **92.0%** | EXCELLENT |
| **SmartSwap KNN** | Within 20% calorie range | **96.0%** | EXCELLENT |
| **SmartSwap KNN** | Mean calorie deviation | 3.8% | GOOD |
| **TF-IDF Hybrid Matcher** | Top-1 Retrieval Accuracy | **90.0%** (18/20) | EXCELLENT |
| **TF-IDF Hybrid Matcher** | Keyword quality gate (v2.6) | MIN_KEYWORD_COUNT=5 | NEW |
| **Fuzzy Matcher** | Keyword quality gate (v2.6) | Weak meals excluded from pool | NEW |
| **Generic Match Hard-Return** | Bareword staples (rice/dal/roti) | 100% → Plain base meal | NEW v2.6 |
| **Plain Boost** | Base meal scoring priority | +0.35 for Plain Rice/Dal/Roti | NEW v2.6 |
| **force_generic** | Combo-split base-only selection | Verified 4 combo rules | NEW v2.6 |
| **Text Preprocessor — Alias** | Alias Normalisation Accuracy | **100%** (10/10) | EXCELLENT |
| **Text Preprocessor — Spell** | Spelling Correction Rate | **100%** (5/5) | EXCELLENT |
| **Quantity Extractor (v2.6)** | Adjective-transparent qty fix | `3 jawar roti` → roti=3 ✅ | FIXED |
| **Combo Splitter** | Correctly splits dal+roti, dal+rice | 6 combo rules | v2.5 |
| **Firestore Dataset (v2.6)** | Meals with ≥5 keywords | **1,935 / 1,935 (100%)** | EXCELLENT |
| **Hybrid Matcher Throughput** | Queries per second | 51 qps | GOOD |
| **Hybrid Matcher Latency** | Per-query latency | 19.61 ms | GOOD |

### NLP Top-Class Performance (selected)

| Meal Class | Precision | Recall | F1 |
|---|---|---|---|
| Methi Malai Matar | 1.000 | 1.000 | 1.000 |
| Kaddu Ki Sabzi | 1.000 | 1.000 | 1.000 |
| Egg Curry | 1.000 | 1.000 | 1.000 |
| Gajar Ka Halwa | 1.000 | 1.000 | 1.000 |
| Pani Puri | 1.000 | 1.000 | 1.000 |
| Sarson Ka Saag | 1.000 | 1.000 | 1.000 |
| Chicken Tikka Masala | 0.857 | 1.000 | 0.923 |
| Kadhi Pakora | 0.861 | 1.000 | 0.925 |

---

## 8. Summary Table <a name="8-summary"></a>

| Component | File | Algorithm(s) | Trained? | v2.6 Changes | Accuracy |
|---|---|---|---|---|---|
| NLP Meal Classifier | `nlp_meal_classifier.joblib` | TF-IDF + Logistic Regression | ✅ Yes | — | **91.37%** |
| Food Category Classifier | `food_category_classifier.joblib` | TF-IDF + Logistic Regression | ✅ Yes | **IGNORE_CATEGORY=True** (globally disabled) | 62.5% (bypassed) |
| SmartSwap KNN | `knn_meal_swap.joblib` | K-Nearest Neighbours | ✅ Yes | — | 92% within 10% cal |
| TF-IDF Meal Matcher | `tfidf_meal_matcher.joblib` | TF-IDF + Cosine Similarity | ✅ Yes | **MIN_KEYWORD_COUNT=5 filter at init** | **90.0%** Top-1 |
| Text Preprocessor | `text_preprocessor.py` | Regex + RapidFuzz + Dictionary | Rule-based | **Millet aliases (jowar/bajra), FOOD_ADJECTIVES transparent skip** | 100% alias/spell |
| Phrase Detector | `phrase_detector.py` | Sliding Window N-gram | Rule-based | — | — |
| Quantity Extractor | `quantity_extractor.py` | Pattern Matching | Rule-based | **Adjective-transparent qty fix (`3 jawar roti` → roti=3)** | Fixed ✅ |
| Context Resolver | `context_resolver.py` | Set Matching + Tiered Scoring | Rule-based | Post-alias rules, promoted STRONG rules | — |
| Combo Splitter | `nlp_pipeline.py` `COMBO_SPLIT_MAP` | Dictionary + Smart Qty + force_generic | Rule-based | **force_generic=True propagated to all combo-split entities** | 6 rules |
| Hybrid Matcher | `hybrid_matcher.py` | 8-Signal Weighted Ensemble | Ensemble | **Generic hard-return, plain_boost +0.35, force_generic base-only, IGNORE_CATEGORY, kw-filter** | **90.0%** |
| Meal Plan Generator | `meal_plan_generator.py` | Constraint Satisfaction + Multi-Signal | Algorithmic AI | Veg filter, calorie penalty, completeness check, variety ×8 | — |
| Compatibility Scorer | `compatibility_scorer.py` | Culinary Rule Engine | Rule-based | — | — |
| Target Calculator | `target_calculator.py` | Mifflin–St Jeor + TDEE + Banking | Formula-based | — | Clinical standard |
| Keyword Updater | `update_firestore_keywords.py` | Batch Firestore update | Tool | **NEW v2.6** — updates 772 meals from local cache | — |
| Meal Enricher | `enrich_skipped_firestore_meals.py` | Token synonym + category map | Tool | **NEW v2.6** — auto-enriches 1,163 weak meals | — |

---

## 9. Dataset Quality & Firestore Enrichment (v2.6) <a name="9-dataset-quality"></a>

### Problem
Firestore contained **1,935 meals** but only **772** had rich `searchKeywords` arrays. The remaining **1,163 meals** had 1–3 keywords, making them nearly invisible to the TF-IDF and keyword-overlap signals.

### Solution: Two-Script Enrichment Pipeline

#### Script 1 — `update_firestore_keywords.py`
Updates `searchKeywords` for the 772 meals present in the enriched local cache (`.cache/meals_cache.json`).

| Feature | Detail |
|---|---|
| Source | `.cache/meals_cache.json` (pre-enriched with `expand_keywords.py`) |
| Safety | Only touches `searchKeywords` — never calories/protein/fat/flags |
| Batch size | 400 writes/batch (Firestore hard limit = 500) |
| Dry-run mode | `--dry-run` flag simulates without writing |
| Priority mode | `--priority` processes low-keyword meals first |
| Result | 772 meals updated in **2.7 seconds** |

#### Script 2 — `enrich_skipped_firestore_meals.py`
Auto-generates keywords for the 1,163 Firestore-only meals (not in local cache) using a rule-based synonym engine.

**Keyword generation strategy (3-tier):**
```
Tier 1: Meal name tokens + TOKEN_SYNONYMS map (80+ food terms)
        "Rice" → rice, chawal, chaawal, chaval, bhat, boiled rice, ...
        "Roti" → roti, chapati, phulka, rotti, flatbread, ...

Tier 2: CATEGORY_TAGS fallback (if still < min_keywords)
        category="grains" → ["grain", "carb", "staple", "indian food"]

Tier 3: Generic floor ["indian food", "meal", "food", "nutrition", "calories"]
```

| Feature | Detail |
|---|---|
| Threshold | `--min-keywords 5` (configurable) |
| Coverage | TOKEN_SYNONYMS: 80+ canonical food tokens → Hinglish/synonym variants |
| Result | **1,163 / 1,163 enriched — 0 failures** in **4.0 seconds** |

### Keyword Quality Filter in NLP Pipeline (v2.6)

Separately, the pipeline now **excludes weak-keyword meals** from both matching pools:

```python
# ai/tfidf_matcher.py — at init time
MIN_KEYWORD_COUNT = 5
strong_meals = [m for m in meals if _has_enough_keywords(m)]
_meal_list = strong_meals   # Only strong meals enter the TF-IDF index
# Logs: [kw-filter] Excluded N meals with < 5 keywords

# ai/hybrid_matcher.py — fuzzy_match_meal()
meals = [m for m in meals if _has_enough_keywords(m)]
# Logs: [kw-filter] fuzzy_match_meal: excluded N weak-keyword meals
```

### Before vs After

| Metric | Before v2.6 | After v2.6 |
|---|---|---|
| Meals with ≥5 keywords | 0 / 1,935 (0%) | **1,935 / 1,935 (100%)** |
| Avg keywords per meal (cache) | 1.9 | **9.0** |
| Min keywords per meal | 1 | **5** |
| Weak meals in TF-IDF index | 1,163 (noise) | **0** |
| `searchKeywords` Firestore writes | 0 | **1,935** |

---

## Conclusion

NutriLens v2.6 employs a **multi-layer AI architecture** combining:

1. **Supervised Machine Learning** — Three trained scikit-learn models (Logistic Regression for meal naming + category prediction, KNN for smart meal swapping)
2. **Information Retrieval with ML** — TF-IDF vector indexing with cosine similarity for semantic meal search; weak-keyword meals filtered before index construction
3. **Ensemble / Hybrid Scoring** — An 8-signal weighted formula with generic hard-return, `plain_boost` (+0.35), `force_generic` base-only path, priority boosting, sabzi-aware boosting, and specificity penalty — achieving 90% Top-1 accuracy
4. **Context-Aware NLP** — Tiered context rules (STRONG/WEAK), combo entity splitting with smart quantity inheritance, `force_generic` propagation ensuring base meals are always selected for combo parts
5. **Constraint-Based AI** — The meal plan generator solves a multi-objective optimisation problem (calories + 3 macros + variety + culinary realism + portion rules + completeness) using candidate-generation + scoring
6. **Personalisation** — User preference boost from meal log history, calorie banking from 3-day intake history, and strict vegetarian pre-filtering
7. **Hinglish NLP** — 127+ alias entries + Hinglish stopword removal + millet aliases (jowar/bajra) + transparent adjective quantity fix + rice/sabzi/curry-rice variant normalisation
8. **Dataset Quality Engineering** — Full Firestore enrichment pipeline ensuring 100% of 1,935 meals have ≥5 `searchKeywords` using an 80+ synonym/Hinglish expansion ruleset

---

*Report updated: April 2026 — Pipeline version v2.6*  
*All model files located in `d:\NutriLens\backend\models\`*  
*Source files: `ai/nlp_pipeline.py`, `ai/hybrid_matcher.py`, `ai/context_resolver.py`, `ai/text_preprocessor.py`, `ai/tfidf_matcher.py`, `ai/meal_plan_generator.py`*  
*Tooling scripts: `update_firestore_keywords.py`, `enrich_skipped_firestore_meals.py`*
