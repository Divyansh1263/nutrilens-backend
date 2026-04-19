"""
enrich_skipped_firestore_meals.py
──────────────────────────────────
Auto-enriches Firestore `meals` documents that have < MIN_KEYWORD_COUNT
searchKeywords by generating keywords from the meal name itself (tokens,
synonyms, Hinglish variations) and writing them back with a batch update.

Safety rules (same as update_firestore_keywords.py):
  ✓  Only updates  searchKeywords
  ✗  Never touches calories, protein, carbs, fat, flags
  ✗  Never creates or deletes documents

Usage
  python enrich_skipped_firestore_meals.py [--dry-run] [--min-keywords N]

Flags
  --dry-run         Print what would change without writing to Firestore.
  --min-keywords N  Threshold below which a meal is considered weak (default 5).
  --batch-size N    Ops per Firestore batch commit (default 400, max 500).
"""

import argparse
import io
import os
import re
import sys
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Configuration ─────────────────────────────────────────────────────────────
SERVICE_ACCOUNT_KEY  = "serviceAccountKey.json"
COLLECTION_NAME      = "meals"
DEFAULT_MIN_KW       = 5
DEFAULT_BATCH_SIZE   = 400


# ─────────────────────────────────────────────────────────────────────────────
# Keyword generation helpers
# ─────────────────────────────────────────────────────────────────────────────

# Single-token synonym / Hinglish map
# key   = English/canonical word found in a meal name
# value = list of synonyms/variations to add
TOKEN_SYNONYMS: dict = {
    # Staple grains
    "rice":        ["rice", "chawal", "chaawal", "chaval", "bhat", "anna",
                    "boiled rice", "white rice", "cooked rice"],
    "roti":        ["roti", "chapati", "chapatti", "phulka", "fulka", "rotti",
                    "flatbread", "indian bread", "wheat roti"],
    "chapati":     ["chapati", "chapatti", "chapatis", "roti", "phulka", "fulka",
                    "flatbread"],
    "paratha":     ["paratha", "parathe", "parantha", "stuffed bread",
                    "pan fried bread"],
    "naan":        ["naan", "nan", "leavened bread", "tandoor bread"],
    "puri":        ["puri", "poori", "fried bread", "deep fried bread"],
    "bhakri":      ["bhakri", "millet flatbread", "jowar bhakri", "bajra bhakri"],
    "biryani":     ["biryani", "biriyani", "biryaani", "dum biryani",
                    "spiced rice", "rice dish"],
    "pulao":       ["pulao", "pulav", "pilaf", "rice pulao"],
    "khichdi":     ["khichdi", "khichri", "kitchari", "comfort food", "dal rice"],
    "idli":        ["idli", "idly", "steamed rice cake", "rice cake"],
    "dosa":        ["dosa", "dosai", "crispy dosa", "south indian dosa"],
    "upma":        ["upma", "uppma", "rava upma", "sooji upma", "suji upma"],
    "poha":        ["poha", "pohe", "flattened rice", "beaten rice", "aval"],
    "uttapam":     ["uttapam", "utthapam", "thick dosa", "vegetable pancake"],
    "appam":       ["appam", "aappam", "rice pancake", "kerala appam"],

    # Dals & legumes
    "dal":         ["dal", "daal", "lentil", "lentils", "yellow dal"],
    "moong":       ["moong", "mung", "green gram", "moong dal"],
    "masoor":      ["masoor", "red lentil", "masoor dal"],
    "toor":        ["toor", "toor dal", "arhar", "arhar dal", "pigeon pea"],
    "chana":       ["chana", "chickpeas", "garbanzo", "gram"],
    "rajma":       ["rajma", "kidney beans", "red kidney beans"],
    "chole":       ["chole", "chhole", "chickpeas", "garbanzo", "chole masala"],
    "urad":        ["urad", "black gram", "urad dal", "split black gram"],
    "dhokla":      ["dhokla", "steamed snack", "fermented snack", "gujarati snack"],
    "sambar":      ["sambar", "sambhar", "south indian curry", "vegetable stew"],

    # Vegetables
    "aloo":        ["aloo", "alu", "potato", "potatoes"],
    "gobi":        ["gobi", "gobhi", "cauliflower"],
    "palak":       ["palak", "spinach", "spinach dish"],
    "methi":       ["methi", "fenugreek", "fenugreek leaves"],
    "bhindi":      ["bhindi", "okra", "lady finger"],
    "lauki":       ["lauki", "bottle gourd", "dudhi"],
    "baingan":     ["baingan", "eggplant", "brinjal", "aubergine"],
    "karela":      ["karela", "bitter gourd", "bitter melon"],
    "tinda":       ["tinda", "round gourd", "apple gourd"],
    "gajar":       ["gajar", "carrot", "carrots"],
    "shimla":      ["shimla mirch", "capsicum", "bell pepper"],
    "matar":       ["matar", "peas", "green peas", "mutter"],
    "kaddu":       ["kaddu", "pumpkin", "pumpkin dish"],

    # Dairy
    "paneer":      ["paneer", "paner", "cottage cheese", "panir", "fresh cheese"],
    "dahi":        ["dahi", "curd", "yogurt", "yoghurt"],
    "curd":        ["curd", "dahi", "yogurt", "yoghurt", "plain curd"],
    "milk":        ["milk", "doodh", "dudh", "dairy"],
    "ghee":        ["ghee", "clarified butter", "desi ghee"],
    "butter":      ["butter", "makhan", "white butter"],
    "cheese":      ["cheese", "paneer", "cheddar"],
    "kheer":       ["kheer", "payasam", "payesh", "rice pudding", "milk dessert"],
    "rabdi":       ["rabdi", "rabri", "condensed milk dessert"],
    "lassi":       ["lassi", "yogurt drink", "sweet lassi", "salted lassi"],
    "chaas":       ["chaas", "buttermilk", "mattha", "diluted curd"],

    # Proteins
    "egg":         ["egg", "anda", "anday", "eggs", "boiled egg"],
    "chicken":     ["chicken", "murgh", "murg", "poultry"],
    "mutton":      ["mutton", "gosht", "lamb", "goat meat"],
    "fish":        ["fish", "machli", "machchi", "seafood"],
    "prawn":       ["prawn", "shrimp", "jhinga", "seafood"],

    # Snacks / street food
    "samosa":      ["samosa", "fried snack", "potato snack", "chaat"],
    "pakoda":      ["pakoda", "pakora", "bhajiya", "fritter", "fried snack"],
    "vada":        ["vada", "wada", "medu vada", "fried lentil cake"],
    "chaat":       ["chaat", "chat", "street food", "indian snack"],
    "bhel":        ["bhel", "bhel puri", "puffed rice snack", "street food"],
    "pav":         ["pav", "bread roll", "ladi pav"],
    "bhaji":       ["bhaji", "bhajji", "fritter", "fried vegetable"],
    "sandwich":    ["sandwich", "toast", "bread sandwich", "snack"],
    "bread":       ["bread", "double roti", "toast", "white bread"],
    "maggi":       ["maggi", "instant noodles", "2 minute noodles", "noodles"],
    "noodles":     ["noodles", "pasta", "instant noodles"],
    "pasta":       ["pasta", "macaroni", "noodles", "italian"],

    # Sweets / desserts
    "halwa":       ["halwa", "halva", "sweet dish", "dessert"],
    "gulab":       ["gulab jamun", "milk sweet", "fried milk balls", "mithai"],
    "jalebi":      ["jalebi", "fried sweet", "mithai"],
    "barfi":       ["barfi", "burfi", "milk sweet", "mithai"],
    "ladoo":       ["ladoo", "laddoo", "round sweet", "mithai"],
    "mithai":      ["mithai", "sweet", "indian sweet", "dessert"],
    "ice":         ["ice cream", "frozen dessert", "gelato"],
    "kulfi":       ["kulfi", "indian ice cream", "frozen milk"],
    "rasgulla":    ["rasgulla", "rasgulla", "cottage cheese sweet", "mithai"],
    "payasam":     ["payasam", "kheer", "payesh", "rice pudding"],
    "burfi":       ["burfi", "barfi", "milk fudge", "mithai"],

    # Beverages
    "chai":        ["chai", "tea", "indian tea", "masala chai", "milk tea"],
    "tea":         ["tea", "chai", "indian tea"],
    "coffee":      ["coffee", "kaapi", "filter coffee", "black coffee"],
    "juice":       ["juice", "fresh juice", "fruit juice"],
    "lassi":       ["lassi", "yogurt drink", "dahi drink"],
    "sharbat":     ["sharbat", "sherbet", "sweet drink", "cooler"],
    "nimbu":       ["nimbu pani", "lemonade", "lime water"],

    # Fruits
    "banana":      ["banana", "kela", "kele", "plantain"],
    "apple":       ["apple", "seb", "fresh fruit"],
    "mango":       ["mango", "aam", "alphonso"],
    "orange":      ["orange", "narangi", "citrus"],
    "papaya":      ["papaya", "papita", "fresh fruit"],
    "watermelon":  ["watermelon", "tarbooz", "summer fruit"],
    "grapes":      ["grapes", "angoor", "fresh fruit"],
    "pomegranate": ["pomegranate", "anar", "seeds"],

    # Nuts / seeds
    "almond":      ["almond", "badam", "almonds", "soaked badam"],
    "cashew":      ["cashew", "kaju", "cashews"],
    "walnut":      ["walnut", "akhrot", "walnuts"],
    "peanut":      ["peanut", "mungfali", "groundnut", "peanuts"],
    "nuts":        ["nuts", "dry fruits", "mixed nuts", "mewa"],

    # Branded / packaged
    "lays":        ["lays", "chips", "potato chips", "crisps", "packaged chips"],
    "kurkure":     ["kurkure", "corn puffs", "masala snack", "fried snack"],
    "pepsi":       ["pepsi", "cold drink", "soda", "cola", "soft drink"],
    "coke":        ["coke", "cola", "cold drink", "aerated drink"],
    "sprite":      ["sprite", "lemon soda", "cold drink"],
    "biscuit":     ["biscuit", "cookie", "cracker", "snack"],
    "chocolate":   ["chocolate", "choco", "dark chocolate", "milk chocolate"],
    "oats":        ["oats", "oatmeal", "rolled oats"],
    "muesli":      ["muesli", "granola", "breakfast cereal"],
    "cornflakes":  ["cornflakes", "cereal", "breakfast cereal"],
    "whey":        ["whey", "protein shake", "whey protein"],

    # Cooking methods / descriptors → add context tags
    "fried":       ["fried", "deep fried", "pan fried", "tawa fried"],
    "grilled":     ["grilled", "tandoori", "barbecued"],
    "steamed":     ["steamed", "healthy", "low calorie"],
    "roasted":     ["roasted", "baked", "tandoori"],
    "mashed":      ["mashed", "puree"],
    "boiled":      ["boiled", "steamed", "cooked"],
    "stuffed":     ["stuffed", "filled", "paratha"],
    "masala":      ["masala", "spiced", "curry"],
    "tadka":       ["tadka", "tempering", "vaghar"],
    "tandoori":    ["tandoori", "clay oven", "grilled"],
    "curry":       ["curry", "gravy", "sauce", "sabzi"],
    "soup":        ["soup", "broth", "shorba"],
    "salad":       ["salad", "tossed", "kachumber", "fresh"],
    "raita":       ["raita", "yogurt dip", "curd dip", "side dish"],
    "chutney":     ["chutney", "dip", "sauce", "condiment"],
    "pickle":      ["pickle", "achar", "condiment"],

    # Regions → add cuisine tags
    "punjabi":     ["punjabi", "north indian", "indian"],
    "south":       ["south indian", "indian"],
    "gujarati":    ["gujarati", "western indian", "indian"],
    "bengali":     ["bengali", "east indian", "indian"],
    "maharashtrian": ["maharashtrian", "marathi", "indian"],
    "kerala":      ["kerala", "south indian", "indian"],
    "hyderabadi":  ["hyderabadi", "telangana", "south indian"],
}

# Category fallback tags added when the meal still doesn't reach the threshold
CATEGORY_TAGS = {
    "grains":     ["indian food", "carb", "staple", "grain"],
    "legumes":    ["protein", "lentil", "pulse", "legume", "dal"],
    "dairy":      ["dairy", "milk product", "calcium", "protein"],
    "snacks":     ["snack", "munchies", "quick bite", "packaged"],
    "sweets":     ["sweet", "dessert", "mithai", "indian sweet"],
    "beverages":  ["drink", "beverage", "liquid"],
    "fruits":     ["fruit", "fresh fruit", "healthy", "vitamin"],
    "vegetables": ["vegetable", "veg", "sabzi", "healthy"],
    "meat":       ["non veg", "protein", "meat", "non-vegetarian"],
    "seafood":    ["seafood", "fish", "non veg", "protein"],
    "breakfast":  ["breakfast", "morning meal", "healthy start"],
    "street food":["street food", "chaat", "snack", "roadside"],
}

GENERIC_FLOOR = ["indian food", "meal", "food", "nutrition", "calories"]


def generate_keywords(meal: dict, min_kw: int) -> list:
    """
    Build an enriched, deduplicated keyword list for a single meal.

    Strategy (in order):
      1. Start with existing keywords.
      2. Add lowercased meal name + each name token.
      3. For each token found in TOKEN_SYNONYMS, merge synonym variants.
      4. Add category floor tags if still below threshold.
      5. Add generic floor words as last resort.
    """
    name      = (meal.get("mealName") or "").strip()
    existing  = list(meal.get("searchKeywords") or [])
    category  = (meal.get("category") or "").lower()

    seen   = set()
    result = []

    def add(kw: str):
        """Add a keyword, deduplicated, lowercased."""
        kw = str(kw).strip().lower()
        if kw and kw not in seen:
            seen.add(kw)
            result.append(kw)

    # 1. Existing keywords
    for kw in existing:
        add(kw)

    # 2. Meal name + tokens
    add(name.lower())
    tokens = re.split(r"[\s\-/()\[\]]+", name.lower())
    for tok in tokens:
        if len(tok) > 2:
            add(tok)

    # 3. Token synonyms
    for tok in list(seen):   # snapshot — iterate over what's already there
        if tok in TOKEN_SYNONYMS:
            for v in TOKEN_SYNONYMS[tok]:
                add(v)

    # 4. Category floor
    if len(result) < min_kw:
        for tag in CATEGORY_TAGS.get(category, []):
            add(tag)

    # 5. Generic floor
    for tag in GENERIC_FLOOR:
        if len(result) >= min_kw:
            break
        add(tag)

    return result


# ─────────────────────────────────────────────────────────────────────────────
# Firebase helpers
# ─────────────────────────────────────────────────────────────────────────────

def init_firebase():
    import firebase_admin
    from firebase_admin import credentials, firestore as fs

    key_path = (
        os.environ.get("FIREBASE_SERVICE_ACCOUNT_PATH")
        or os.environ.get("FIREBASE_SERVICE_ACCOUNT")
        or SERVICE_ACCOUNT_KEY
    )
    key_abs = os.path.abspath(key_path)
    if not os.path.exists(key_abs):
        print(f"[ERROR] Service account key not found: {key_abs}")
        sys.exit(1)

    try:
        app = firebase_admin.get_app()
    except ValueError:
        cred = credentials.Certificate(key_abs)
        app  = firebase_admin.initialize_app(cred)

    print(f"[INFO] Firebase: project_id={app.project_id}")
    return fs.client()


def fetch_weak_docs(db, min_kw: int) -> list:
    """Return (doc_ref, data) for all meals with < min_kw keywords."""
    print(f"\n[INFO] Streaming '{COLLECTION_NAME}' collection ...")
    t0 = time.time()
    weak, total = [], 0
    for doc in db.collection(COLLECTION_NAME).stream():
        data = doc.to_dict() or {}
        total += 1
        kws = data.get("searchKeywords") or []
        if len(kws) < min_kw:
            weak.append((doc.reference, data))
    elapsed = time.time() - t0
    print(
        f"[INFO] Fetched {total:,} docs in {elapsed:.1f}s  |  "
        f"weak (< {min_kw} kws): {len(weak):,}  |  "
        f"strong: {total - len(weak):,}"
    )
    return weak


def run_enrichment(db, weak_docs: list, min_kw: int,
                   batch_size: int, dry_run: bool) -> dict:
    """Enrich weak meals and batch-commit updates."""
    stats = {
        "total_weak":  len(weak_docs),
        "enriched":    0,
        "already_ok":  0,   # shouldn't happen but guard anyway
    }

    sample_enriched = []
    sample_skipped  = []

    batch          = db.batch() if not dry_run else None
    count_in_batch = 0
    batch_num      = 1

    for doc_ref, data in weak_docs:
        name     = data.get("mealName", "?")
        old_kws  = data.get("searchKeywords") or []

        new_kws = generate_keywords(data, min_kw)

        if len(new_kws) < min_kw:
            # Should not happen given GENERIC_FLOOR, but log just in case
            sample_skipped.append(
                f'  [skip]     "{name}" — only {len(new_kws)} kws generated'
            )
            stats["already_ok"] += 1
            continue

        if not dry_run:
            batch.update(doc_ref, {"searchKeywords": new_kws})
            count_in_batch += 1

        stats["enriched"] += 1

        if len(sample_enriched) < 8:
            sample_enriched.append(
                f'  [enriched] "{name}"  {len(old_kws)} → {len(new_kws)} kws'
            )

        if not dry_run and count_in_batch >= batch_size:
            print(f"  [...] Committing batch #{batch_num} ({count_in_batch} updates)...")
            batch.commit()
            batch_num      += 1
            batch           = db.batch()
            count_in_batch  = 0

    if not dry_run and count_in_batch > 0:
        print(f"  [...] Committing final batch #{batch_num} ({count_in_batch} updates)...")
        batch.commit()

    # ── Sample output ─────────────────────────────────────────────────────
    print()
    print("── Sample enriched meals ───────────────────────────────────")
    for s in sample_enriched:
        print(s)
    if sample_skipped:
        print()
        print("── Skipped ─────────────────────────────────────────────────")
        for s in sample_skipped:
            print(s)

    return stats


# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(stats: dict, dry_run: bool, elapsed: float, min_kw: int):
    sep  = "=" * 65
    mode = "DRY-RUN (no writes)" if dry_run else "LIVE"
    print(f"\n{sep}")
    print(f"  ENRICHMENT SUMMARY  [{mode}]  (min_keywords={min_kw})")
    print(sep)
    print(f"  Weak meals processed : {stats['total_weak']:>6,}")
    print(f"  Successfully enriched: {stats['enriched']:>6,}")
    print(f"  Could not enrich     : {stats['already_ok']:>6,}")
    print(f"  Elapsed time         : {elapsed:>6.1f}s")
    print(sep)
    if dry_run:
        print("  Re-run WITHOUT --dry-run to apply changes.")
    else:
        print("  Done! Weak meals have been enriched in Firestore.")
    print(sep)


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Enrich weak Firestore meal keywords.")
    p.add_argument("--dry-run",        action="store_true")
    p.add_argument("--min-keywords",   type=int, default=DEFAULT_MIN_KW)
    p.add_argument("--batch-size",     type=int, default=DEFAULT_BATCH_SIZE)
    return p.parse_args()


def main():
    sep = "=" * 65
    print(sep)
    print("  NutriLens — Skipped Meal Keyword Enricher")
    print(sep)

    args     = parse_args()
    dry_run  = args.dry_run
    min_kw   = args.min_keywords
    batch_sz = min(args.batch_size, 500)

    if dry_run:
        print("\n[MODE] DRY-RUN — Firestore will NOT be modified.\n")

    # ── Connect ───────────────────────────────────────────────────────────────
    if not dry_run:
        print("\n[STEP 1] Connecting to Firestore ...")
        db = init_firebase()
    else:
        print("\n[STEP 1] Dry-run: skipping Firebase init.")
        db = None

    # ── Fetch weak docs ───────────────────────────────────────────────────────
    print(f"\n[STEP 2] Fetching meals with < {min_kw} keywords ...")
    if not dry_run:
        weak_docs = fetch_weak_docs(db, min_kw)
    else:
        # Dry-run: simulate from local cache
        import json
        cache_path = os.path.join(".cache", "meals_cache.json")
        if os.path.exists(cache_path):
            with open(cache_path, encoding="utf-8") as fh:
                raw = json.load(fh)
            weak_docs = [(None, m) for m in raw if len(m.get("searchKeywords") or []) < min_kw]
            print(f"[INFO] Dry-run mode: {len(weak_docs)} weak meals found in local cache.")
        else:
            print("[WARN] No local cache found. Run with live Firestore or generate cache first.")
            weak_docs = []

    if not weak_docs:
        print(f"\n[INFO] No meals with < {min_kw} keywords found. Nothing to do.")
        return

    # ── Enrich + commit ───────────────────────────────────────────────────────
    print(f"\n[STEP 3] Enriching {len(weak_docs):,} weak meals ...")
    t0     = time.time()
    stats  = run_enrichment(db, weak_docs, min_kw, batch_sz, dry_run)
    elapsed = time.time() - t0

    # ── Summary ───────────────────────────────────────────────────────────────
    print_summary(stats, dry_run, elapsed, min_kw)


if __name__ == "__main__":
    main()
