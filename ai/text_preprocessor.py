# ai/text_preprocessor.py
# Stage 1: Text cleaning + spelling correction + alias normalization
#
# IMPROVEMENT (v2.1):
# IMPROVEMENT (v2.4 TASK 3): Added curry-rice multi-word aliases
#   Added food alias normalization — maps regional names to
#   canonical English food words before entity extraction.
#   Examples: dahi → curd, bhindi → okra, baingan → eggplant

import re
from rapidfuzz import process, fuzz

# -----------------------------------------------
# Stopwords to remove (common non-food words)
# -----------------------------------------------
STOPWORDS = {
    # English
    "i", "ate", "had", "have", "with", "some", "a", "an", "the",
    "for", "my", "of", "and", "in", "today", "yesterday", "morning",
    "afternoon", "evening", "night", "breakfast", "lunch", "dinner",
    "snack", "just", "also", "then", "after", "before", "about",
    "around", "like", "want", "log", "consumed", "eating", "meal",
    "food", "serving", "servings", "to", "was", "is", "it",
    # Hinglish
    "maine", "mene", "khaya", "kha", "li", "liya", "hai", "tha", "thi",
    "hun", "aur", "wala", "wali", "kiya", "khate", "khayi", "raha",
    "rahi", "aaj", "kal", "subah", "dopahar", "raat", "shaam",
    "sirf", "bas", "bhi", "nahi", "nai", "thoda",
}

# -----------------------------------------------
# IMPROVEMENT: Food alias normalization
# Maps regional / alternate names to canonical terms
# that align with searchKeywords and mealName fields
# -----------------------------------------------
FOOD_ALIAS_MAP = {
    # ── Vegetables ──────────────────────────────────────────────────────────
    "aloo": "potato",
    "alu": "potato",
    "bhindi": "okra",
    "baingan": "eggplant",
    "brinjal": "eggplant",
    "palak": "spinach",
    "gobi": "cauliflower",
    "gobhi": "cauliflower",
    "matar": "peas",
    "shimla": "capsicum",
    "shimlamirch": "capsicum",
    "lauki": "bottle gourd",
    "ghia": "bottle gourd",
    "karela": "bitter gourd",
    "kaddu": "pumpkin",
    "tinda": "tinda",
    "methi": "fenugreek",
    "sarson": "mustard",
    "tamatar": "tomato",
    "pyaaz": "onion",
    "peyaj": "onion",
    "mirchi": "chili",
    "hari mirchi": "green chili",
    # ── Fruits ──────────────────────────────────────────────────────────────
    "kela": "banana",
    "aam": "mango",
    "seb": "apple",
    "angoor": "grapes",
    "santra": "orange",
    "nimbu": "lemon",
    "amrud": "guava",
    "papita": "papaya",
    "nashpati": "pear",
    "sitafal": "custard apple",
    # ── Dairy / Fats ─────────────────────────────────────────────────────────
    "dahi": "curd",
    "doodh": "milk",
    "dudh": "milk",
    "makhan": "butter",
    "malai": "cream",
    "ghee": "ghee",
    "panir": "paneer",
    "chenna": "paneer",
    # ── Protein ──────────────────────────────────────────────────────────────
    "anda": "egg",
    "anday": "egg",
    "murgh": "chicken",
    "murg": "chicken",
    "gosht": "mutton",
    "machli": "fish",
    "machchi": "fish",
    "jhinga": "prawn",
    "makhana": "fox nut",
    # ── Grains / Staples ─────────────────────────────────────────────────────
    "chawal": "rice",
    "chaawal": "rice",
    "chapati": "roti",
    "chapatis": "roti",
    "chapatti": "roti",
    "aata": "wheat",
    "atta": "wheat",
    "suji": "semolina",
    "rava": "semolina",
    "maida": "refined flour",
    "besan": "gram flour",
    # ── Legumes / Lentils ────────────────────────────────────────────────────
    "chana": "chickpeas",
    "chole": "chickpeas",
    "chhole": "chickpeas",
    "moong": "mung",
    "urad": "black gram",
    "masoor": "red lentil",
    "toor": "pigeon pea",
    "arhar": "pigeon pea",
    "rajma": "kidney beans",
    "lobia": "black eyed peas",
    # ── Spices / Condiments ─────────────────────────────────────────────────
    "jeera": "cumin",
    "haldi": "turmeric",
    "adrak": "ginger",
    "lasun": "garlic",
    "lehsun": "garlic",
    "dhania": "coriander",
    "saunf": "fennel",
    "hing": "asafoetida",
    "imli": "tamarind",
    # ── Snacks / Dishes ──────────────────────────────────────────────────────
    "momo":   "momos",
    "samosa": "samosa",
    "tikki":  "aloo tikki",
    # TASK 1 (v2.5): sabzi → more specific canonical name matching Firestore mealNames
    "sabzi":  "mixed vegetable sabzi",
    "subzi":  "mixed vegetable sabzi",   # common alternate spelling
}

# ── Multi-word alias map (phrase-level replacement) ───────────────────────────
# Maps phrases of 2+ words → canonical name used in mealName / searchKeywords
MULTI_WORD_ALIAS_MAP = {
    "dahi chawal": "curd rice",
    "aloo gobhi": "aloo gobi",
    "aloo gobi": "aloo gobi",
    "aloo matar": "aloo matar",
    "dal chawal": "dal chawal",
    "dal rice": "dal chawal",
    "rajma chawal": "rajma chawal",
    "rajma rice": "rajma chawal",
    "kadhi chawal": "kadhi chawal",
    "kadhi rice": "kadhi chawal",
    "moong dal": "moong dal",
    "masoor dal": "masoor dal",
    "toor dal": "toor dal",
    "arhar dal": "toor dal",
    "urad dal": "urad dal",
    "kali dal": "dal makhani",
    "paneer butter masla": "paneer butter masala",
    "paner tikka": "paneer tikka",
    "chicken tikka masla": "chicken tikka masala",
    "chole bhature": "chole bhature",
    "idli sambar": "idli sambar",
    "poha jalebi": "poha jalebi",
    "bread butter": "bread butter",
    # TASK 3 (prev): Curry-rice generic aliases → canonical dal chawal
    "curry rice":     "dal chawal",
    "rice curry":     "dal chawal",
    "curry and rice": "dal chawal",
    # TASK 3: Rice variant normalisation → plain rice
    "plain rice":     "rice",
    "boiled rice":    "rice",
    "white rice":     "rice",
    # TASK 4: Expand curry-rice variants → dal chawal
    "gravy rice":     "dal chawal",
    "sabzi rice":     "dal chawal",
    "dal rice":       "dal chawal",
}

# Module-level cache (populated by init)
_vocabulary = set()
_vocab_list = []


def init_preprocessor(meals):
    """
    Build the spelling-correction vocabulary from all meal data.
    Called once at server startup.
    """
    global _vocabulary, _vocab_list

    words = set()
    for meal in meals:
        # Add individual words from mealName
        name_val = (meal.get("mealName") or meal.get("name") or meal.get("title") or meal.get("food_name") or "")
        for w in name_val.lower().split():
            words.add(w)

        # Add individual words from searchKeywords
        keywords = meal.get("searchKeywords") or meal.get("aliases") or []
        for kw in keywords:
            for w in kw.lower().split():
                words.add(w)

    # Also add all alias keys and values to vocabulary
    for alias, canonical in FOOD_ALIAS_MAP.items():
        words.add(alias)
        for w in canonical.split():
            words.add(w)

    _vocabulary = words
    _vocab_list = list(words)
    print(f"[text_preprocessor] Vocabulary built: {len(_vocabulary)} words "
          f"(includes {len(FOOD_ALIAS_MAP)} aliases)")


def clean_text(text):
    """
    Lowercase, remove punctuation (keep hyphens for words like
    'three-quarter'), normalize whitespace, remove stopwords.
    """
    text = text.lower().strip()

    # Remove punctuation except hyphens
    text = re.sub(r"[^\w\s\-]", " ", text)

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()

    # Remove stopwords
    tokens = text.split()
    tokens = [t for t in tokens if t not in STOPWORDS]

    return " ".join(tokens)


def normalize_aliases(tokens):
    """
    Replace regional food aliases with canonical names.
    Handles both single-token aliases (FOOD_ALIAS_MAP) and
    multi-token phrases (MULTI_WORD_ALIAS_MAP) via bigram/trigram scan.

    Runs BEFORE spelling correction so aliases are normalized first.

    Args:
        tokens: list of cleaned tokens

    Returns:
        list of tokens with aliases replaced
    """
    # ── Pass 1: multi-word phrase replacement (bigram → trigram scan) ────────
    result_pass1 = []
    i = 0
    n = len(tokens)
    while i < n:
        matched = False
        # Try 3-token phrase first, then 2-token
        for window in (3, 2):
            if i + window > n:
                continue
            phrase = " ".join(tokens[i:i + window])
            if phrase in MULTI_WORD_ALIAS_MAP:
                canonical = MULTI_WORD_ALIAS_MAP[phrase]
                print(f"[multi-alias] '{phrase}' → '{canonical}'")
                result_pass1.extend(canonical.split())
                i += window
                matched = True
                break
        if not matched:
            result_pass1.append(tokens[i])
            i += 1

    # ── Pass 2: single-token alias replacement ───────────────────────────────
    result_pass2 = []
    for token in result_pass1:
        if token in FOOD_ALIAS_MAP:
            canonical = FOOD_ALIAS_MAP[token]
            print(f"[alias] '{token}' → '{canonical}'")
            # Canonical may be multi-word (e.g., "gram flour")
            result_pass2.extend(canonical.split())
        else:
            result_pass2.append(token)

    return result_pass2


def correct_spelling(tokens, threshold=85):
    """
    Fuzzy-correct each token against the food vocabulary.
    Only corrects if the token is NOT already in the vocabulary.

    Args:
        tokens:     list of string tokens
        threshold:  minimum similarity score (0–100) to accept a correction

    Returns:
        list of corrected tokens
    """
    if not _vocab_list:
        return tokens  # No vocab loaded yet

    corrected = []
    for token in tokens:
        # Skip numbers, fractions, and quantity words
        if token.isdigit() or token in {"half", "quarter", "one", "two",
            "three", "four", "five", "six", "seven", "eight", "nine", "ten"}:
            corrected.append(token)
            continue

        # Already in vocabulary → no correction needed
        if token in _vocabulary:
            corrected.append(token)
            continue

        # Fuzzy match against vocabulary
        result = process.extractOne(
            token,
            _vocab_list,
            scorer=fuzz.ratio,
            score_cutoff=threshold
        )

        if result:
            corrected_word, score, _ = result
            print(f"[spelling] '{token}' → '{corrected_word}' (score={score})")
            corrected.append(corrected_word)
        else:
            # No good match — keep original
            corrected.append(token)

    return corrected
