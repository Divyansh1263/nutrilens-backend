"""
scripts/update_keywords_and_rebuild_tfidf.py
─────────────────────────────────────────────
Safely integrates improved searchKeywords from final_production_meals.json
into the NutriLens system and rebuilds ONLY the TF-IDF matcher.

Pipeline:
  Step 1 — Load final_production_meals.json
  Step 2 — Validate keyword quality (≥5 kws, no generic noise)
  Step 3 — Update Firestore (searchKeywords ONLY, batch writes)
  Step 4 — Reload all meals from Firestore
  Step 5 — Rebuild TF-IDF cache  →  models/tfidf_meal_matcher.joblib
  Step 6 — Validate matching with test queries

Safety:
  - NEVER overwrites calories / protein / carbs / fat / flags
  - NEVER creates or deletes Firestore documents
  - ONLY sends  update({searchKeywords: [...]})  calls
  - Does NOT retrain NLP classifier or KNN

Usage:
  python scripts/update_keywords_and_rebuild_tfidf.py [--dry-run]
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

# ── Force UTF-8 stdout on Windows (avoids cp1252 UnicodeEncodeError) ─────────
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import numpy as np
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

# ── Paths (relative to project root / backend/) ───────────────────────────────
BASE_DIR            = Path(__file__).resolve().parent.parent   # backend/
SOURCE_FILE         = BASE_DIR / "final_production_meals.json"
MODELS_DIR          = BASE_DIR / "models"
TFIDF_CACHE_PATH    = MODELS_DIR / "tfidf_meal_matcher.joblib"
SERVICE_ACCOUNT_KEY = BASE_DIR / "serviceAccountKey.json"
COLLECTION_NAME     = "meals"

# ── Quality gate ──────────────────────────────────────────────────────────────
MIN_KEYWORDS       = 5
GENERIC_BLACKLIST  = {"food", "meal", "nutrition", "calories", "indian food",
                      "healthy", "snack", "dish"}
FIRESTORE_BATCH_SIZE = 400   # Firestore hard cap is 500; use 400 for safety

# ── Validation queries ────────────────────────────────────────────────────────
TEST_QUERIES = [
    "2 roti dal",
    "ate makhana",
    "coffee pi",
    "jowar roti",
]

# ── Corpus-side stopwords (mirrors tfidf_matcher.CORPUS_STOPWORDS) ────────────
# Removed from document text before vectorization to fix query/doc asymmetry.
CORPUS_STOPWORDS = {
    "ate", "had", "have", "drank", "piya", "khaya", "kha", "li", "liya",
    "khayi", "khate", "consumed", "with", "and", "a", "an", "the", "of",
    "in", "for", "some", "my", "is", "it", "to", "i",
}

# Path to enriched keyword fallback (for Task 2 — meals with <5 keywords)
KEYWORDS_ENRICHMENT_FILE = BASE_DIR / "meals_keywords.json"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize(name: str) -> str:
    return str(name).strip().lower()


def load_source(path: Path) -> dict[str, list[str]]:
    """Load final_production_meals.json → {normalized_name: [keywords]}."""
    if not path.exists():
        print(f"[ERROR] Source file not found: {path}")
        sys.exit(1)

    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, list):
        print(f"[ERROR] Expected JSON array in {path.name}")
        sys.exit(1)

    kw_map: dict[str, list[str]] = {}
    for entry in data:
        name = entry.get("mealName", "")
        if not name:
            continue
        key = normalize(name)
        kws = [k.strip().lower() for k in (entry.get("searchKeywords") or []) if k.strip()]
        kw_map[key] = kws

    print(f"[load]    Loaded {len(kw_map):,} meals from {path.name}")
    return kw_map


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 — Keyword quality validation
# ─────────────────────────────────────────────────────────────────────────────

def validate_keywords(kw_map: dict[str, list[str]]) -> dict[str, list[str]]:
    """
    For every meal:
      • ensure mealName itself is in keywords
      • remove generic/blacklisted keywords
      • deduplicate
      • log meals with < MIN_KEYWORDS after cleaning
    Returns a cleaned kw_map.
    """
    print(f"\n[Step 2]  Validating keyword quality ...")
    clean_map: dict[str, list[str]] = {}
    below_min: list[str] = []

    for meal_name, kws in kw_map.items():
        # Remove generic / blacklisted tokens
        filtered = [kw for kw in kws if kw not in GENERIC_BLACKLIST and kw.strip()]

        # Deduplicate preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for kw in filtered:
            if kw not in seen:
                seen.add(kw)
                deduped.append(kw)

        # Ensure mealName is a keyword
        if meal_name not in seen:
            deduped.insert(0, meal_name)

        clean_map[meal_name] = deduped

        kw_count = len(deduped)
        print(f"[kw-update] mealName={meal_name!r:50s}  keywords_count={kw_count}")

        if kw_count < MIN_KEYWORDS:
            below_min.append(meal_name)

    if below_min:
        print(f"\n[kw-warn]  {len(below_min)} meals have < {MIN_KEYWORDS} keywords after cleaning:")
        for n in below_min[:10]:
            print(f"  [warn] {n!r} ({len(clean_map[n])} kws)")
        if len(below_min) > 10:
            print(f"  ... and {len(below_min) - 10} more")

    print(f"[Step 2]  ✓ Validation complete  "
          f"({len(clean_map)} meals,  {len(below_min)} below minimum threshold)")
    return clean_map


# ─────────────────────────────────────────────────────────────────────────────
# Firebase
# ─────────────────────────────────────────────────────────────────────────────

def init_firebase():
    import firebase_admin
    from firebase_admin import credentials, firestore as fs

    key_path = (
        os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        or str(SERVICE_ACCOUNT_KEY)
    )
    key_abs = os.path.abspath(key_path)
    if not os.path.exists(key_abs):
        print(f"[ERROR] Service account key not found: {key_abs}")
        sys.exit(1)

    try:
        firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(key_abs)
        firebase_admin.initialize_app(cred)

    db = fs.client()
    print(f"[firebase] Connected ✓")
    return db


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 — Firestore batch update (searchKeywords only)
# ─────────────────────────────────────────────────────────────────────────────

def update_firestore_keywords(db, kw_map: dict[str, list[str]], dry_run: bool) -> dict:
    """Batch-update ONLY the searchKeywords field for matching Firestore docs."""
    print(f"\n[Step 3]  Streaming Firestore '{COLLECTION_NAME}' collection ...")
    t0 = time.time()

    docs = []
    for doc in db.collection(COLLECTION_NAME).stream():
        data = doc.to_dict() or {}
        docs.append((doc.reference, data.get("mealName", ""),
                     len(data.get("searchKeywords") or [])))

    print(f"[Step 3]  Fetched {len(docs):,} documents in {time.time() - t0:.1f}s")

    stats = {"total": len(docs), "updated": 0, "skipped": 0, "no_match": 0}
    batch = db.batch() if not dry_run else None
    count_in_batch = 0
    batch_num = 1

    for doc_ref, raw_name, existing_kw_count in docs:
        key = normalize(raw_name)

        if key not in kw_map:
            stats["no_match"] += 1
            stats["skipped"]  += 1
            continue

        new_kws = kw_map[key]
        if not new_kws:
            stats["skipped"] += 1
            continue

        # ── SAFETY: update ONLY searchKeywords ────────────────────────────────
        if dry_run:
            print(f'  [DRY-RUN] "{raw_name}" → {len(new_kws)} keywords '
                  f'(was {existing_kw_count})')
        else:
            batch.update(doc_ref, {"searchKeywords": new_kws})
            count_in_batch += 1

        stats["updated"] += 1

        if not dry_run and count_in_batch >= FIRESTORE_BATCH_SIZE:
            print(f"  [batch]   Committing batch #{batch_num} ({count_in_batch} updates)...")
            batch.commit()
            batch_num += 1
            batch = db.batch()
            count_in_batch = 0

    if not dry_run and count_in_batch > 0:
        print(f"  [batch]   Committing final batch #{batch_num} ({count_in_batch} updates)...")
        batch.commit()

    mode = "DRY-RUN" if dry_run else "LIVE"
    print(f"\n[Step 3]  [{mode}]  "
          f"updated={stats['updated']}  "
          f"no_match={stats['no_match']}  "
          f"skipped={stats['skipped']}")
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 — Reload all meals from Firestore
# ─────────────────────────────────────────────────────────────────────────────

def reload_meals_from_firestore(db) -> list[dict]:
    print(f"\n[Step 4]  Reloading all meals from Firestore ...")
    t0 = time.time()
    meals = []
    for doc in db.collection(COLLECTION_NAME).stream():
        meal = doc.to_dict() or {}
        meal["_doc_id"] = doc.id
        meals.append(meal)
    print(f"[Step 4]  Reloaded {len(meals):,} meals in {time.time() - t0:.1f}s")
    return meals


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 — Rebuild TF-IDF cache (ONLY)
# ─────────────────────────────────────────────────────────────────────────────

def meal_text(meal: dict) -> str:
    """Build clean TF-IDF document text, stripping corpus stopwords."""
    name     = str(meal.get("mealName", "")).lower().strip()
    keywords = meal.get("searchKeywords") or []
    raw      = name + " " + " ".join(str(k).lower() for k in keywords if k)
    # FIX (Task 3): remove corpus stopwords from document side
    return " ".join(tok for tok in raw.split() if tok not in CORPUS_STOPWORDS)


def rebuild_tfidf(meals: list[dict]) -> dict:
    """
    Enrich weak meals (< MIN_KEYWORDS) from meals_keywords.json, then build
    TF-IDF vectorizer + matrix and save cache.
    Does NOT touch nlp_meal_classifier.joblib or knn_meal_swap.joblib.
    """
    print(f"\n[Step 5]  Rebuilding TF-IDF matcher ...")

    # ── Task 2: Load enrichment map from meals_keywords.json ──────────────────
    enrichment_map: dict[str, list[str]] = {}
    if KEYWORDS_ENRICHMENT_FILE.exists():
        with KEYWORDS_ENRICHMENT_FILE.open(encoding="utf-8") as fh:
            enrichment_data = json.load(fh)
        for entry in enrichment_data:
            en = entry.get("mealName", "").strip().lower()
            ek = [k.strip().lower() for k in (entry.get("searchKeywords") or []) if k.strip()]
            if en:
                enrichment_map[en] = ek
        print(f"[enrich]   Loaded {len(enrichment_map):,} entries from {KEYWORDS_ENRICHMENT_FILE.name}")
    else:
        print(f"[enrich]   meals_keywords.json not found — skipping enrichment")

    # ── Task 2: Enrich meals with < MIN_KEYWORDS keywords ─────────────────────
    enriched_count = 0
    for meal in meals:
        kws = meal.get("searchKeywords") or []
        if len(kws) >= MIN_KEYWORDS:
            continue
        key = (meal.get("mealName") or "").strip().lower()
        extra = enrichment_map.get(key, [])
        if extra:
            # Merge: existing keywords first, then extra, deduped
            merged = list(kws)
            seen   = set(k.lower() for k in merged)
            for kw in extra:
                if kw not in seen:
                    merged.append(kw)
                    seen.add(kw)
            # Ensure mealName itself is a keyword
            if key not in seen:
                merged.insert(0, key)
            meal["searchKeywords"] = merged
            enriched_count += 1

    if enriched_count:
        print(f"[enrich]   Enriched {enriched_count} meals to meet MIN_KEYWORDS={MIN_KEYWORDS}")

    # ── Filter: keep meals with >= MIN_KEYWORDS after enrichment ──────────────
    strong = [m for m in meals if len(m.get("searchKeywords") or []) >= MIN_KEYWORDS]
    weak   = [m for m in meals if len(m.get("searchKeywords") or []) <  MIN_KEYWORDS]
    print(f"[kw-filter] Retained {len(strong)} / {len(meals)} meals  "
          f"({len(weak)} still below {MIN_KEYWORDS} keywords after enrichment)")
    if weak:
        for m in weak[:5]:
            print(f"  [kw-filter] skipped '{m.get('mealName')}' "
                  f"({len(m.get('searchKeywords') or [])} kws)")

    texts = [meal_text(m) for m in strong]

    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        max_features=3000,
        lowercase=True,
        sublinear_tf=True,
        min_df=2,
    )
    tfidf_matrix = vectorizer.fit_transform(texts)

    # Build category index
    category_index: dict[str, list[int]] = {}
    for idx, meal in enumerate(strong):
        cat = str(meal.get("category", "")).strip().lower()
        if cat:
            category_index.setdefault(cat, []).append(idx)

    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    cache_data = {
        "vectorizer":     vectorizer,
        "tfidf_matrix":   tfidf_matrix,
        "meals":          strong,
        "category_index": category_index,
    }
    joblib.dump(cache_data, TFIDF_CACHE_PATH, compress=3)
    size_mb = TFIDF_CACHE_PATH.stat().st_size / (1024 * 1024)

    print(f"[Step 5]  TF-IDF rebuilt: {tfidf_matrix.shape[0]} meals x "
          f"{tfidf_matrix.shape[1]} features  ->  {TFIDF_CACHE_PATH.name} ({size_mb:.2f} MB)")
    return cache_data


# ─────────────────────────────────────────────────────────────────────────────
# Step 6 — Validate matching with test queries
# ─────────────────────────────────────────────────────────────────────────────

def validate_matching(cache: dict) -> None:
    print(f"\n[Step 6]  Validating TF-IDF matching ...")
    vectorizer   = cache["vectorizer"]
    tfidf_matrix = cache["tfidf_matrix"]
    meals        = cache["meals"]

    for query in TEST_QUERIES:
        q_vec  = vectorizer.transform([query.lower()])
        sims   = cosine_similarity(q_vec, tfidf_matrix).flatten()
        top_k  = int(np.argsort(sims)[::-1][0])
        score  = float(sims[top_k])

        best_meal = meals[top_k]
        name      = best_meal.get("mealName", "<unknown>")
        kws       = best_meal.get("searchKeywords") or []

        # Keyword overlap
        query_tokens = set(query.lower().split())
        kw_tokens    = set(" ".join(kws).lower().split())
        overlap      = query_tokens & kw_tokens

        print(f"  Query: {query!r}")
        print(f"    → Match  : {name!r}")
        print(f"    → Score  : {score:.4f}")
        print(f"    → KW overlap: {sorted(overlap) or '(none)'}")

        # Top-3
        top3 = np.argsort(sims)[::-1][:3]
        for rank, idx in enumerate(top3, 1):
            print(f"    [{rank}] {meals[idx].get('mealName')!r}  (score={sims[idx]:.4f})")
        print()


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Update Firestore keywords & rebuild TF-IDF (no NLP/KNN retrain)."
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Simulate Firestore writes without actually committing.")
    return p.parse_args()


def main() -> None:
    sep = "=" * 70
    print(sep)
    print("  NutriLens — Keyword Update + TF-IDF Rebuild")
    print(sep)

    args    = parse_args()
    dry_run = args.dry_run
    if dry_run:
        print("\n[MODE]  DRY-RUN — Firestore will NOT be modified.\n")

    # Step 1: Load source
    print(f"\n[Step 1]  Loading {SOURCE_FILE.name} ...")
    kw_map = load_source(SOURCE_FILE)

    # Step 2: Validate keywords
    kw_map = validate_keywords(kw_map)

    # Steps 3-4: Firestore (skipped in dry-run mode for TF-IDF rebuild)
    db    = init_firebase()
    stats = update_firestore_keywords(db, kw_map, dry_run)
    meals = reload_meals_from_firestore(db)

    # Step 5: Rebuild TF-IDF only
    cache = rebuild_tfidf(meals)

    # Step 6: Validate
    validate_matching(cache)

    # ── Summary ───────────────────────────────────────────────────────────────
    print(sep)
    print("  SUMMARY")
    print(sep)
    mode = "DRY-RUN (no Firestore writes)" if dry_run else "LIVE"
    print(f"  Mode                      : {mode}")
    print(f"  Source meals              : {len(kw_map):>6,}")
    print(f"  Firestore total docs      : {stats['total']:>6,}")
    print(f"  Keywords updated          : {stats['updated']:>6,}")
    print(f"  Not matched (no update)   : {stats['no_match']:>6,}")
    print(f"  TF-IDF meals indexed      : {cache['tfidf_matrix'].shape[0]:>6,}")
    print(f"  TF-IDF features           : {cache['tfidf_matrix'].shape[1]:>6,}")
    print(f"  Model saved               : {TFIDF_CACHE_PATH}")
    print(sep)
    print("  [OK] TF-IDF rebuilt. NLP classifier and KNN were NOT retrained.")
    print(sep)


if __name__ == "__main__":
    main()
