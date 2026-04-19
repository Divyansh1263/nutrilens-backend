"""
upload_unique_meals.py
----------------------
Uploads ONLY new, unique meals from `meal_dataset2.json` into the Firestore
`meals` collection.

Deduplication is done at three levels (fast -> slow):
  1. Against `meal_dataset.json`  -> pure in-memory set lookup
  2. Against Firestore DB          -> single bulk fetch (no per-doc queries)

Comparison is case-insensitive and whitespace-trimmed.
Uploads use Firestore batch writes (max 500 per batch) for efficiency.
"""

import io
import json
import sys
import os
import firebase_admin
from firebase_admin import credentials, firestore

# Force UTF-8 stdout so emoji / non-ASCII print correctly on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ──────────────────────────── configuration ──────────────────────────────────

SERVICE_ACCOUNT_KEY  = "serviceAccountKey.json"   # path relative to this script
OLD_DATASET_FILE     = "meal_dataset.json"         # already-uploaded reference
NEW_DATASET_FILE     = "meal_dataset2.json"        # new meals to evaluate
COLLECTION_NAME      = "meals"
FIRESTORE_BATCH_SIZE = 500                         # Firestore hard limit per batch

# ──────────────────────────── helpers ────────────────────────────────────────

def normalize(name: str) -> str:
    """Lowercase + strip whitespace for deduplication comparison."""
    return name.strip().lower()


def load_json(filepath: str) -> list:
    """Load a JSON file and return its contents as a list."""
    abs_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)
    if not os.path.exists(abs_path):
        print(f"[ERROR] File not found: {abs_path}")
        sys.exit(1)

    with open(abs_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if not isinstance(data, list):
        print(f"[ERROR] Expected a JSON array in '{filepath}', got {type(data).__name__}.")
        sys.exit(1)

    return data


def build_name_set(meals: list, source_label: str) -> set:
    """
    Extract normalised meal names from a list of meal dicts.
    Warns about entries missing 'mealName'.
    """
    names = set()
    missing = 0
    for m in meals:
        raw = m.get("mealName")
        if raw is None or str(raw).strip() == "":
            missing += 1
            continue
        names.add(normalize(str(raw)))

    if missing:
        print(f"  [WARN] {missing} record(s) in {source_label} had no 'mealName' — skipped.")

    return names


# ──────────────────────────── firebase ───────────────────────────────────────

def init_firebase() -> firestore.Client:
    """Initialise Firebase Admin SDK and return a Firestore client."""
    key_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), SERVICE_ACCOUNT_KEY)
    if not os.path.exists(key_path):
        print(f"[ERROR] Service account key not found: {key_path}")
        sys.exit(1)

    cred = credentials.Certificate(key_path)
    firebase_admin.initialize_app(cred)
    return firestore.client()


def fetch_firestore_meal_names(db: firestore.Client) -> set:
    """
    Fetch ALL documents from the `meals` collection and return a set of
    normalised meal names.
    Uses a single streaming read — no per-document queries.
    """
    print(f"\n[INFO] Fetching existing meal names from Firestore '{COLLECTION_NAME}' collection...")
    names = set()
    docs = db.collection(COLLECTION_NAME).stream()
    for doc in docs:
        data = doc.to_dict()
        raw = data.get("mealName")
        if raw and str(raw).strip():
            names.add(normalize(str(raw)))

    print(f"       Found {len(names):,} existing meal(s) in Firestore.")
    return names


# ──────────────────────────── upload ─────────────────────────────────────────

def batch_upload(db: firestore.Client, meals: list) -> int:
    """
    Upload a list of meal dicts to Firestore using batched writes.
    Returns the number of documents actually committed.
    """
    collection_ref  = db.collection(COLLECTION_NAME)
    total_uploaded  = 0
    batch           = db.batch()
    count_in_batch  = 0

    for meal in meals:
        doc_ref = collection_ref.document()   # auto-generated document ID
        batch.set(doc_ref, meal)
        count_in_batch += 1
        total_uploaded += 1

        if count_in_batch == FIRESTORE_BATCH_SIZE:
            batch.commit()
            print(f"  [OK] Committed batch of {count_in_batch} documents...")
            batch          = db.batch()
            count_in_batch = 0

    # commit the remaining docs in the last (partial) batch
    if count_in_batch > 0:
        batch.commit()
        print(f"  [OK] Committed final batch of {count_in_batch} document(s).")

    return total_uploaded


# ──────────────────────────── main ───────────────────────────────────────────

def main():
    sep = "=" * 60
    print(sep)
    print("  NutriLens -- Unique Meal Uploader")
    print(sep)

    # ── 1. Load both JSON files ───────────────────────────────────────────────
    print(f"\n[INFO] Loading '{OLD_DATASET_FILE}'...")
    old_meals = load_json(OLD_DATASET_FILE)
    print(f"       {len(old_meals):,} records found.")

    print(f"\n[INFO] Loading '{NEW_DATASET_FILE}'...")
    new_meals  = load_json(NEW_DATASET_FILE)
    total_new  = len(new_meals)
    print(f"       {total_new:,} records found.")

    if total_new == 0:
        print("\n[WARN] New dataset is empty — nothing to upload.")
        return

    # ── 2. Build in-memory deduplication set from old dataset ─────────────────
    print(f"\n[INFO] Indexing meal names from '{OLD_DATASET_FILE}'...")
    old_names: set = build_name_set(old_meals, OLD_DATASET_FILE)
    print(f"       {len(old_names):,} unique meal name(s) indexed.")

    # ── 3. Filter against local dataset ──────────────────────────────────────
    print(f"\n[INFO] Filtering new meals against local dataset...")
    candidates   = []
    local_dupes  = 0
    missing_name = 0

    for meal in new_meals:
        raw = meal.get("mealName")
        if raw is None or str(raw).strip() == "":
            missing_name += 1
            continue
        if normalize(str(raw)) in old_names:
            local_dupes += 1
        else:
            candidates.append(meal)

    print(f"       {local_dupes:,}  duplicate(s) matched in local dataset — skipped.")
    print(f"       {missing_name:,} record(s) missing 'mealName' — skipped.")
    print(f"       {len(candidates):,} candidate meal(s) remain after local filter.")

    if not candidates:
        print("\n[INFO] No new meals to upload — all already exist in the local dataset.")
        _print_summary(total_new, local_dupes + missing_name, 0, 0)
        return

    # ── 4. Init Firebase & fetch Firestore meal names ─────────────────────────
    db = init_firebase()
    firestore_names: set = fetch_firestore_meal_names(db)

    # ── 5. Filter candidates against Firestore ────────────────────────────────
    print(f"\n[INFO] Filtering candidates against Firestore...")
    to_upload       = []
    firestore_dupes = 0

    for meal in candidates:
        name = normalize(str(meal["mealName"]))
        if name in firestore_names:
            firestore_dupes += 1
        else:
            to_upload.append(meal)

    print(f"       {firestore_dupes:,} duplicate(s) already in Firestore — skipped.")
    print(f"       {len(to_upload):,} truly new meal(s) queued for upload.")

    total_skipped = local_dupes + missing_name + firestore_dupes

    if not to_upload:
        print("\n[INFO] Nothing new to upload — all meals already exist in Firestore.")
        _print_summary(total_new, total_skipped, 0, 0)
        return

    # ── 6. Batch upload ───────────────────────────────────────────────────────
    print(f"\n[INFO] Uploading {len(to_upload):,} unique meal(s) to Firestore...")
    uploaded = batch_upload(db, to_upload)

    # ── 7. Summary ────────────────────────────────────────────────────────────
    _print_summary(total_new, total_skipped, uploaded, firestore_dupes)


def _print_summary(total: int, skipped: int, uploaded: int, firestore_dupes: int):
    local_skipped = skipped - firestore_dupes
    sep = "=" * 60
    print(f"\n{sep}")
    print("  UPLOAD SUMMARY")
    print(sep)
    print(f"  Total meals in new dataset       : {total:,}")
    print(f"  Duplicates skipped (local JSON)  : {local_skipped:,}")
    print(f"  Duplicates skipped (Firestore)   : {firestore_dupes:,}")
    print(f"  Total skipped                    : {skipped:,}")
    print(f"  Meals successfully uploaded      : {uploaded:,}")
    print(sep)
    if uploaded > 0:
        print("  Done! All unique meals have been uploaded.")
    else:
        print("  No new uploads were needed.")
    print(sep)


if __name__ == "__main__":
    main()
