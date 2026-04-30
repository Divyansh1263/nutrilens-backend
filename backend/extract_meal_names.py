"""
extract_meal_names.py
---------------------
Extracts all unique meal names from meal_dataset2.json,
cleans them (lowercase + strip), removes duplicates,
saves results to meal_names.txt, and prints a summary.
"""

import json
import os

# ── Config ──────────────────────────────────────────────────────────────────
INPUT_FILE  = os.path.join(os.path.dirname(__file__), "meal_dataset2.json")
OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "meal_names.txt")


def load_dataset(path: str) -> list:
    """Load and return the JSON array from *path*. Returns [] on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print(f"[ERROR] Expected a JSON array in '{path}', got {type(data).__name__}.")
            return []
        return data
    except FileNotFoundError:
        print(f"[ERROR] File not found: '{path}'")
        return []
    except json.JSONDecodeError as e:
        print(f"[ERROR] Invalid JSON in '{path}': {e}")
        return []


def extract_unique_meal_names(dataset: list) -> tuple[list, int, int]:
    """
    Iterate through meal objects, clean each mealName, and deduplicate.

    Returns:
        unique_names  - sorted list of unique lowercased meal names
        total         - total entries processed (inc. skipped)
        skipped       - entries where mealName was missing / empty
    """
    seen:    set  = set()
    skipped: int  = 0

    for entry in dataset:
        raw_name = entry.get("mealName", "")

        # Skip missing or empty values
        if not raw_name or not str(raw_name).strip():
            skipped += 1
            continue

        cleaned = str(raw_name).strip().lower()
        seen.add(cleaned)

    unique_names = sorted(seen)
    total        = len(dataset)
    return unique_names, total, skipped


def save_meal_names(names: list, path: str) -> None:
    """Write one meal name per line to *path*."""
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(names))
    print(f"[OK]  Saved {len(names)} unique meal names -> '{path}'")


def main() -> None:
    print("=" * 55)
    print("  NutriLens -- Meal Name Extractor")
    print("=" * 55)

    # 1. Load
    dataset = load_dataset(INPUT_FILE)
    if not dataset:
        print("[ABORT] No data to process.")
        return

    # 2. Extract & deduplicate
    unique_names, total, skipped = extract_unique_meal_names(dataset)

    # 3. Save
    save_meal_names(unique_names, OUTPUT_FILE)

    # 4. Summary
    print()
    print("-- Summary ------------------------------------------")
    print(f"  Total meal entries processed : {total}")
    print(f"  Entries skipped (no name)    : {skipped}")
    print(f"  Total unique meal names      : {len(unique_names)}")
    print("-" * 55)


if __name__ == "__main__":
    main()
