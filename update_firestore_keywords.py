"""
update_firestore_keywords.py
────────────────────────────
Updates ONLY the `searchKeywords` field for meals in the Firestore `meals`
collection, using the locally enriched `.cache/meals_cache.json` as the source.

Safety rules
  - NEVER overwrites calories, protein, carbs, fat or any other field.
  - NEVER creates new documents.
  - NEVER deletes documents.
  - ONLY sends Firestore `update({searchKeywords: [...]})` calls.

Usage
  python update_firestore_keywords.py [--dry-run] [--batch-size 400]

Flags
  --dry-run      Print what would be updated without writing to Firestore.
  --batch-size N Override commits-per-batch (default 400, Firestore max 500).
  --priority     Process meals with < 3 existing keywords first (bonus task).
"""

import argparse
import io
import json
import os
import sys
import time

# ── Force UTF-8 stdout on Windows ────────────────────────────────────────────
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Configuration ─────────────────────────────────────────────────────────────
SERVICE_ACCOUNT_KEY  = "serviceAccountKey.json"
LOCAL_CACHE_PATH     = os.path.join(".cache", "meals_cache.json")
COLLECTION_NAME = "meals_v3"
FIRESTORE_BATCH_SIZE = 400       # Firestore hard limit is 500; we use 400 for safety
LOG_SAMPLE_LIMIT     = 5         # How many [update]/[skip] lines to print inline


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def normalize(name: str) -> str:
    """Lowercase + strip whitespace for comparison."""
    return str(name).strip().lower()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Update Firestore meal keywords.")
    p.add_argument("--dry-run",    action="store_true",
                   help="Simulate without writing to Firestore.")
    p.add_argument("--batch-size", type=int, default=FIRESTORE_BATCH_SIZE,
                   help=f"Documents per Firestore batch commit (default {FIRESTORE_BATCH_SIZE}).")
    p.add_argument("--priority",   action="store_true",
                   help="Process meals with < 3 existing keywords first (bonus).")
    return p.parse_args()


def load_local_cache(path: str) -> dict:
    """
    Load meals_cache.json and build:
        { normalized_meal_name: [keyword, ...] }
    """
    abs_path = os.path.abspath(path)
    if not os.path.exists(abs_path):
        print(f"[ERROR] Local cache not found: {abs_path}")
        sys.exit(1)

    with open(abs_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, list):
        print(f"[ERROR] Expected a JSON array in '{path}', got {type(data).__name__}.")
        sys.exit(1)

    kw_map: dict = {}
    missing, duplicate = 0, 0

    for meal in data:
        name = meal.get("mealName")
        if not name or not str(name).strip():
            missing += 1
            continue
        key  = normalize(name)
        kws  = meal.get("searchKeywords") or []
        if key in kw_map:
            duplicate += 1        # keep the richer one
            if len(kws) > len(kw_map[key]):
                kw_map[key] = kws
        else:
            kw_map[key] = kws

    print(f"[INFO] Local cache  : {len(data):,} records  │  "
          f"indexed {len(kw_map):,}  │  missing name {missing}  │  dupes {duplicate}")
    return kw_map


def init_firebase():
    """Initialise Firebase Admin SDK and return a Firestore client."""
    import firebase_admin
    from firebase_admin import credentials, firestore as fs

    # Respect FIREBASE_SERVICE_ACCOUNT_PATH env var (same as app.py)
    key_path = (
        os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        or SERVICE_ACCOUNT_KEY
    )
    key_abs = os.path.abspath(key_path)
    if not os.path.exists(key_abs):
        print(f"[ERROR] Service account key not found: {key_abs}")
        sys.exit(1)

    # Avoid re-initialising if called multiple times
    try:
        app = firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(key_abs)
        app  = firebase_admin.initialize_app(cred)

    project = app.project_id
    print(f"[INFO] Firebase     : project_id={project}")
    return fs.client()


def fetch_firestore_docs(db, priority_mode: bool) -> list:
    """
    Stream all documents from the `meals` collection.
    Returns a list of (document_ref, doc_data, existing_kw_count) tuples,
    optionally sorted so low-keyword meals come first.
    """
    print(f"\n[INFO] Streaming Firestore '{COLLECTION_NAME}' collection ...")
    t0    = time.time()
    docs  = []
    total = 0

    for doc in db.collection(COLLECTION_NAME).stream():
        data  = doc.to_dict() or {}
        name  = data.get("mealName", "")
        kws   = data.get("searchKeywords") or []
        docs.append((doc.reference, data, name, len(kws)))
        total += 1

    elapsed = time.time() - t0
    print(f"[INFO] Fetched {total:,} document(s) in {elapsed:.1f}s")

    if priority_mode:
        # Low-keyword meals first (bonus task)
        docs.sort(key=lambda x: x[3])
        print("[INFO] Priority mode: meals with < 3 keywords will be processed first.")

    return docs


# ─────────────────────────────────────────────────────────────────────────────
# Core update logic
# ─────────────────────────────────────────────────────────────────────────────

def run_update(db, docs: list, kw_map: dict, batch_size: int, dry_run: bool):
    """
    Match each Firestore document against the local keyword map and batch-update.

    Returns stats dict.
    """
    stats = {
        "total":    len(docs),
        "updated":  0,
        "skipped":  0,
        "no_match": 0,
    }

    # Per-decision samples (capped to LOG_SAMPLE_LIMIT each)
    update_samples  = []
    skip_samples    = []

    # Batch state
    batch          = db.batch() if not dry_run else None
    count_in_batch = 0
    batch_num      = 1

    for doc_ref, data, raw_name, existing_kw_count in docs:
        key = normalize(raw_name)

        if key not in kw_map:
            stats["no_match"] += 1
            stats["skipped"]  += 1
            if len(skip_samples) < LOG_SAMPLE_LIMIT:
                skip_samples.append(f'  [skip]   "{raw_name}" — not in local cache')
            continue

        new_kws = kw_map[key]
        if not new_kws:
            stats["skipped"] += 1
            if len(skip_samples) < LOG_SAMPLE_LIMIT:
                skip_samples.append(f'  [skip]   "{raw_name}" — local cache has empty keyword list')
            continue

        # Safety: do NOT touch any field except searchKeywords
        update_payload = {"searchKeywords": new_kws}

        if dry_run:
            print(f'  [DRY-RUN] "{raw_name}" → {len(new_kws)} keywords')
        else:
            batch.update(doc_ref, update_payload)
            count_in_batch += 1

        stats["updated"] += 1

        if len(update_samples) < LOG_SAMPLE_LIMIT:
            update_samples.append(
                f'  [update] "{raw_name}" → {len(new_kws)} keywords '
                f'(was {existing_kw_count})'
            )

        # Commit batch when it reaches the size limit
        if not dry_run and count_in_batch >= batch_size:
            print(f"  [...] Committing batch #{batch_num} ({count_in_batch} updates)...")
            batch.commit()
            batch_num      += 1
            batch           = db.batch()
            count_in_batch  = 0

    # Commit any remaining ops
    if not dry_run and count_in_batch > 0:
        print(f"  [...] Committing final batch #{batch_num} ({count_in_batch} updates)...")
        batch.commit()

    # Print samples
    print()
    print("── Sample updates ──────────────────────────────────────")
    for s in update_samples:
        print(s)

    print()
    print("── Sample skips ────────────────────────────────────────")
    for s in skip_samples:
        print(s)

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(stats: dict, dry_run: bool, elapsed: float):
    sep = "=" * 65
    mode = "DRY-RUN  (no writes performed)" if dry_run else "LIVE"
    print(f"\n{sep}")
    print(f"  KEYWORD UPDATE SUMMARY  [{mode}]")
    print(sep)
    print(f"  Total Firestore documents  : {stats['total']:>6,}")
    print(f"  Documents updated          : {stats['updated']:>6,}")
    print(f"    ↳ skipped (no local match)  : {stats['no_match']:>6,}")
    print(f"    ↳ skipped (other)           : {stats['skipped'] - stats['no_match']:>6,}")
    print(f"  Total skipped              : {stats['skipped']:>6,}")
    print(f"  Elapsed time               : {elapsed:>6.1f}s")
    print(sep)
    if dry_run:
        print("  Re-run WITHOUT --dry-run to apply changes.")
    else:
        print("  Done! Firestore keyword fields are now up to date.")
    print(sep)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    sep = "=" * 65
    print(sep)
    print("  NutriLens — Firestore Keyword Updater")
    print(sep)

    args      = parse_args()
    dry_run   = args.dry_run
    batch_sz  = min(args.batch_size, 500)   # always respect Firestore hard cap

    if dry_run:
        print("\n[MODE] DRY-RUN enabled — Firestore will NOT be modified.\n")

    # ── Step 1: Load local enriched dataset ───────────────────────────────────
    print(f"\n[STEP 1] Loading local keyword cache from '{LOCAL_CACHE_PATH}' ...")
    kw_map = load_local_cache(LOCAL_CACHE_PATH)

    # ── Step 2: Connect to Firestore ──────────────────────────────────────────
    if not dry_run:
        print(f"\n[STEP 2] Connecting to Firestore ...")
        db = init_firebase()
    else:
        # In dry-run we still need a mock to avoid Firebase init overhead
        print(f"\n[STEP 2] Dry-run mode — skipping Firebase init.")
        db = None

    # ── Step 3: Fetch Firestore documents ─────────────────────────────────────
    if not dry_run:
        print(f"\n[STEP 3] Fetching all documents from '{COLLECTION_NAME}' ...")
        docs = fetch_firestore_docs(db, priority_mode=args.priority)
    else:
        # Simulate using local cache entries as mock "Firestore docs"
        print(f"\n[STEP 3] Dry-run: simulating Firestore fetch from local cache ...")
        import json as _json
        with open(LOCAL_CACHE_PATH, encoding="utf-8") as fh:
            raw = _json.load(fh)
        # Build list mimicking (ref, data, name, kw_count)
        docs = [(None, m, m.get("mealName", ""), len(m.get("searchKeywords") or [])) for m in raw]
        if args.priority:
            docs.sort(key=lambda x: x[3])

    # ── Step 4 + 5: Match, batch-update, log ──────────────────────────────────
    print(f"\n[STEP 4/5] Matching and {'simulating' if dry_run else 'writing'} updates "
          f"(batch size={batch_sz}) ...")

    t0    = time.time()
    stats = run_update(db, docs, kw_map, batch_sz, dry_run)
    elapsed = time.time() - t0

    # ── Summary ───────────────────────────────────────────────────────────────
    print_summary(stats, dry_run, elapsed)


if __name__ == "__main__":
    main()
