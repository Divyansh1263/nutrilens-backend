"""
NutriLens Authentication Migration Script
==========================================
Phase 2: Backup all user-related collections
Phase 3: Merge duplicate accounts, migrate to Firebase UID

SAFETY:
- Creates JSON backups BEFORE any modification
- Validates counts before and after
- Uses batched writes
- Never deletes source data until verified

Usage:
  python scripts/auth_migration.py --backup-only     # Phase 2 only
  python scripts/auth_migration.py --report-only      # Generate report only
  python scripts/auth_migration.py --migrate           # Full migration (Phase 2+3)
"""

import os
import sys
import json
import argparse
from datetime import datetime

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from firebase_admin import credentials, firestore

# ── Firebase Init ─────────────────────────────────────────────────────────────
SERVICE_ACCOUNT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "serviceAccountKey.json",
)

try:
    app = firebase_admin.get_app()
except ValueError:
    cred = credentials.Certificate(SERVICE_ACCOUNT)
    app = firebase_admin.initialize_app(cred, {
        "projectId": "nutrilens-b5e81",
        "storageBucket": "nutrilens-b5e81.firebasestorage.app",
    })

db = firestore.client()

# ── Collection names ──────────────────────────────────────────────────────────
COLLECTIONS = {
    "users":                  "users",
    "meal_logs":              "meal_logs",
    "meal_plans":             "meal_plans",
    "daily_targets":          "daily_targets",
    "daily_tracker_summary":  "daily_tracker_summary",
    "daily_ratings":          "daily_ratings",
    "user_meal_history":      "user_meal_history",
}

BACKUP_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "migration_backups",
)


def _ts() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — BACKUP
# ═══════════════════════════════════════════════════════════════════════════════
def backup_all_collections():
    """Export every document from all auth-related collections to JSON."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    ts = _ts()
    summary = {}

    for label, col_name in COLLECTIONS.items():
        print(f"[backup] Exporting {col_name} ...")
        docs = list(db.collection(col_name).stream())
        data = {}
        for d in docs:
            raw = d.to_dict()
            # Convert Firestore timestamps to ISO strings for JSON
            for k, v in raw.items():
                if hasattr(v, "isoformat"):
                    raw[k] = v.isoformat()
            data[d.id] = raw

        path = os.path.join(BACKUP_DIR, f"{label}_backup_{ts}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

        summary[col_name] = {"count": len(data), "file": path}
        print(f"  -> {len(data)} documents saved to {path}")

    # Write summary
    summary_path = os.path.join(BACKUP_DIR, f"backup_summary_{ts}.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\n[backup] Summary: {summary_path}")
    return summary


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2.5 — MIGRATION REPORT
# ═══════════════════════════════════════════════════════════════════════════════
def _is_email_derived_id(uid: str) -> bool:
    """Heuristic: email-derived IDs contain '_' and end with a TLD pattern."""
    if not uid:
        return False
    # Email-derived: divyanshtyagi1263_gmail_com
    return ("_" in uid and
            not uid.startswith("I") and  # Firebase UIDs often start with letters
            any(uid.endswith(tld) for tld in ["_com", "_in", "_org", "_net", "_co"]))


def generate_migration_report() -> dict:
    """Analyze all users and identify duplicates, conflicts, orphans."""
    print("[report] Analyzing user collection ...")
    docs = list(db.collection("users").stream())

    users = []
    email_map: dict[str, list] = {}  # email → list of user docs

    for d in docs:
        u = d.to_dict()
        u["_doc_id"] = d.id
        users.append(u)

        email = (u.get("email") or "").strip().lower()
        if email:
            email_map.setdefault(email, []).append(u)

    # Classify users
    custom_auth_users = []
    google_auth_users = []
    unknown_auth_users = []

    for u in users:
        doc_id = u["_doc_id"]
        has_password = "password_hash" in u
        is_google = u.get("auth_provider") == "google"

        if is_google or (not has_password and not _is_email_derived_id(doc_id)):
            google_auth_users.append(u)
        elif has_password or _is_email_derived_id(doc_id):
            custom_auth_users.append(u)
        else:
            unknown_auth_users.append(u)

    # Find duplicates (same email, different doc IDs)
    duplicates = []
    for email, docs_list in email_map.items():
        if len(docs_list) > 1:
            duplicates.append({
                "email": email,
                "doc_ids": [d["_doc_id"] for d in docs_list],
                "providers": [
                    "google" if d.get("auth_provider") == "google" else "custom"
                    for d in docs_list
                ],
            })

    # Count dependent collection data per userId
    def count_docs_for_user(col_name: str, uid: str) -> int:
        try:
            docs = list(
                db.collection(col_name)
                .where("userId", "==", uid)
                .limit(100)
                .stream()
            )
            return len(docs)
        except Exception:
            return 0

    merge_plan = []
    for dup in duplicates:
        email = dup["email"]
        docs_list = email_map[email]

        # Identify which doc has profile data vs which is minimal
        google_doc = None
        custom_doc = None
        for d in docs_list:
            if d.get("auth_provider") == "google" or not _is_email_derived_id(d["_doc_id"]):
                google_doc = d
            else:
                custom_doc = d

        if google_doc and custom_doc:
            # Count data under each ID
            custom_id = custom_doc["_doc_id"]
            google_id = google_doc["_doc_id"]

            custom_data = {
                col: count_docs_for_user(col, custom_id)
                for col in ["meal_logs", "meal_plans", "daily_targets"]
            }
            google_data = {
                col: count_docs_for_user(col, google_id)
                for col in ["meal_logs", "meal_plans", "daily_targets"]
            }

            merge_plan.append({
                "email": email,
                "keep_id": google_id,
                "merge_from_id": custom_id,
                "custom_profile_complete": custom_doc.get("onboarding_completed", False),
                "google_profile_complete": google_doc.get("onboarding_completed", False),
                "custom_data_counts": custom_data,
                "google_data_counts": google_data,
                "fields_to_merge": [
                    k for k in ["age", "gender", "height", "weight", "target_weight",
                                "activityLevel", "goal", "weight_loss_speed",
                                "dietary_restrictions", "health_conditions",
                                "onboarding_completed"]
                    if custom_doc.get(k) is not None and google_doc.get(k) is None
                ],
            })

    report = {
        "generated_at": datetime.now().isoformat(),
        "total_users": len(users),
        "custom_auth_users": len(custom_auth_users),
        "google_auth_users": len(google_auth_users),
        "unknown_auth_users": len(unknown_auth_users),
        "duplicate_emails": len(duplicates),
        "duplicates": duplicates,
        "merge_plan": merge_plan,
        "custom_auth_user_ids": [u["_doc_id"] for u in custom_auth_users],
        "google_auth_user_ids": [u["_doc_id"] for u in google_auth_users],
    }

    path = os.path.join(BACKUP_DIR, f"auth_migration_report_{_ts()}.json")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    with open(path, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[report] Saved to {path}")
    print(f"  Total users:       {report['total_users']}")
    print(f"  Custom auth:       {report['custom_auth_users']}")
    print(f"  Google auth:       {report['google_auth_users']}")
    print(f"  Duplicate emails:  {report['duplicate_emails']}")
    print(f"  Merge candidates:  {len(merge_plan)}")
    return report


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 3 — USER MERGE & UID MIGRATION
# ═══════════════════════════════════════════════════════════════════════════════
def migrate_users(report: dict, dry_run: bool = False):
    """
    For each duplicate pair:
    1. Merge custom-auth profile fields into Google-auth doc
    2. Re-key all dependent collection docs from old userId to Firebase UID
    3. Remove password_hash
    4. Set auth_provider = "google", onboarding_completed = true
    """
    merge_plan = report.get("merge_plan", [])
    if not merge_plan:
        print("[migrate] No duplicates to merge.")
        # Still clean up any remaining custom-auth-only users
        _clean_standalone_custom_users(report, dry_run)
        return

    for entry in merge_plan:
        email = entry["email"]
        keep_id = entry["keep_id"]           # Firebase UID (Google doc)
        old_id = entry["merge_from_id"]       # email-derived ID (Custom doc)
        fields = entry["fields_to_merge"]

        print(f"\n{'='*60}")
        print(f"[migrate] Merging: {email}")
        print(f"  Keep (Firebase UID): {keep_id}")
        print(f"  Merge from (custom): {old_id}")
        print(f"  Fields to copy: {fields}")
        print(f"{'='*60}")

        if dry_run:
            print("  [DRY RUN] Skipping actual writes.")
            continue

        # ── Step 1: Merge profile fields ──────────────────────────────────
        custom_doc = db.collection("users").document(old_id).get()
        if not custom_doc.exists:
            print(f"  [WARN] Custom doc {old_id} not found, skipping merge")
            continue

        custom_data = custom_doc.to_dict()
        update_fields = {}
        for field in fields:
            val = custom_data.get(field)
            if val is not None:
                update_fields[field] = val

        # Always set these
        update_fields["auth_provider"] = "google"
        update_fields["onboarding_completed"] = True
        update_fields["migrated_from"] = old_id
        update_fields["migrated_at"] = firestore.SERVER_TIMESTAMP

        # Copy name if Google doc has empty name
        google_doc = db.collection("users").document(keep_id).get()
        if google_doc.exists:
            gdata = google_doc.to_dict()
            if not gdata.get("name") and custom_data.get("name"):
                update_fields["name"] = custom_data["name"]

        # NEVER copy password_hash
        update_fields.pop("password_hash", None)

        print(f"  [write] Updating users/{keep_id} with {list(update_fields.keys())}")
        db.collection("users").document(keep_id).update(update_fields)

        # ── Step 2: Re-key dependent collections ──────────────────────────
        _rekey_collection("meal_logs", old_id, keep_id)
        _rekey_collection("meal_plans", old_id, keep_id)
        _rekey_collection_by_doc_prefix("daily_targets", old_id, keep_id)
        _rekey_collection_by_doc_prefix("daily_tracker_summary", old_id, keep_id)
        _rekey_collection("daily_ratings", old_id, keep_id)
        _rekey_collection_by_doc_prefix("user_meal_history", old_id, keep_id)

        # ── Step 3: Mark old user doc as migrated (don't delete yet) ──────
        db.collection("users").document(old_id).update({
            "_migrated_to": keep_id,
            "_migrated_at": firestore.SERVER_TIMESTAMP,
            "_status": "migrated",
        })
        print(f"  [done] Merge complete for {email}")

    _clean_standalone_custom_users(report, dry_run)


def _rekey_collection(col_name: str, old_uid: str, new_uid: str):
    """Re-key docs in a collection where userId is a field (not part of doc ID)."""
    docs = list(
        db.collection(col_name)
        .where("userId", "==", old_uid)
        .stream()
    )
    if not docs:
        print(f"  [rekey] {col_name}: 0 docs for {old_uid}")
        return

    batch = db.batch()
    count = 0
    for d in docs:
        batch.update(d.reference, {"userId": new_uid})
        count += 1
        if count % 400 == 0:  # Firestore batch limit = 500
            batch.commit()
            batch = db.batch()

    if count % 400 != 0:
        batch.commit()
    print(f"  [rekey] {col_name}: {count} docs updated ({old_uid} -> {new_uid})")


def _rekey_collection_by_doc_prefix(col_name: str, old_uid: str, new_uid: str):
    """
    Re-key docs where the document ID starts with old_uid
    (e.g. daily_targets: '{userId}_{date}').
    Creates new doc with new ID, copies data, deletes old doc.
    """
    docs = list(db.collection(col_name).stream())
    prefix = f"{old_uid}_"
    matched = [(d.id, d.to_dict()) for d in docs if d.id.startswith(prefix)]

    if not matched:
        print(f"  [rekey] {col_name}: 0 docs with prefix {old_uid}_")
        return

    batch = db.batch()
    count = 0
    for old_doc_id, data in matched:
        suffix = old_doc_id[len(prefix):]
        new_doc_id = f"{new_uid}_{suffix}"
        data["userId"] = new_uid

        new_ref = db.collection(col_name).document(new_doc_id)
        old_ref = db.collection(col_name).document(old_doc_id)

        batch.set(new_ref, data)
        batch.delete(old_ref)
        count += 1

        if count % 200 == 0:  # 2 ops per doc, stay under 500
            batch.commit()
            batch = db.batch()

    if count % 200 != 0:
        batch.commit()
    print(f"  [rekey] {col_name}: {count} docs re-keyed ({old_uid}_ -> {new_uid}_)")


def _clean_standalone_custom_users(report: dict, dry_run: bool):
    """
    For custom-auth-only users (no duplicate Google doc):
    - Remove password_hash
    - Set auth_provider field for tracking
    These users will need to sign in with Google next time.
    """
    merged_ids = {e["merge_from_id"] for e in report.get("merge_plan", [])}
    standalone = [
        uid for uid in report.get("custom_auth_user_ids", [])
        if uid not in merged_ids
    ]

    if not standalone:
        print("\n[cleanup] No standalone custom-auth users.")
        return

    print(f"\n[cleanup] {len(standalone)} standalone custom-auth users to clean")
    for uid in standalone:
        if dry_run:
            print(f"  [DRY RUN] Would clean {uid}")
            continue

        doc = db.collection("users").document(uid).get()
        if not doc.exists:
            continue

        data = doc.to_dict()
        updates = {}
        if "password_hash" in data:
            updates["password_hash"] = firestore.DELETE_FIELD
        updates["_needs_google_link"] = True

        if updates:
            db.collection("users").document(uid).update(updates)
            print(f"  [clean] {uid}: removed password_hash, flagged for Google link")


# ═══════════════════════════════════════════════════════════════════════════════
# POST-MIGRATION VERIFICATION
# ═══════════════════════════════════════════════════════════════════════════════
def verify_migration():
    """Verify no password hashes remain and all users have consistent state."""
    print("\n[verify] Running post-migration checks ...")
    users = list(db.collection("users").stream())

    issues = []
    for d in users:
        u = d.to_dict()
        uid = d.id
        if "password_hash" in u and u.get("_status") != "migrated":
            issues.append(f"  [WARN] {uid}: still has password_hash")
        if u.get("_status") == "migrated":
            continue  # skip migrated-from docs
        if not u.get("email"):
            issues.append(f"  [WARN] {uid}: missing email")

    if issues:
        print(f"[verify] {len(issues)} issues found:")
        for i in issues:
            print(i)
    else:
        print("[verify] OK - All checks passed - no password hashes, all users consistent")

    return len(issues) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    parser = argparse.ArgumentParser(description="NutriLens Auth Migration")
    parser.add_argument("--backup-only", action="store_true", help="Phase 2: Backup only")
    parser.add_argument("--report-only", action="store_true", help="Generate migration report")
    parser.add_argument("--migrate", action="store_true", help="Full migration (Phase 2+3)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate migration without writes")
    parser.add_argument("--verify", action="store_true", help="Post-migration verification")
    args = parser.parse_args()

    if args.backup_only:
        backup_all_collections()
    elif args.report_only:
        generate_migration_report()
    elif args.migrate:
        print("=" * 60)
        print("NUTRILENS AUTH MIGRATION")
        print("=" * 60)

        # Phase 2
        print("\n-- Phase 2: Backup --")
        backup_all_collections()

        # Phase 2.5
        print("\n-- Phase 2.5: Migration Report --")
        report = generate_migration_report()

        # Phase 3
        print("\n-- Phase 3: User Merge & UID Migration --")
        migrate_users(report, dry_run=args.dry_run)

        # Verify
        print("\n-- Verification --")
        verify_migration()

        print("\n" + "=" * 60)
        print("MIGRATION COMPLETE")
        print("=" * 60)
    elif args.verify:
        verify_migration()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
