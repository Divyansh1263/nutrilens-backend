# ai/text_preprocessor.py
# Stage 1: Text cleaning + spelling correction + alias normalization
#
# IMPROVEMENT (v2.1):
#   Added food alias normalization — maps regional names to
#   canonical English food words before entity extraction.
#   Examples: dahi → curd, bhindi → okra, baingan → eggplant

import re
from rapidfuzz import process, fuzz

# -----------------------------------------------
# Stopwords to remove (common non-food words)
# -----------------------------------------------
STOPWORDS = {
    "i", "ate", "had", "have", "with", "some", "a", "an", "the",
    "for", "my", "of", "and", "in", "today", "yesterday", "morning",
    "afternoon", "evening", "night", "breakfast", "lunch", "dinner",
    "snack", "just", "also", "then", "after", "before", "about",
    "around", "like", "want", "log", "consumed", "eating", "meal",
    "food", "serving", "servings", "to", "was", "is", "it",
}

# -----------------------------------------------
# IMPROVEMENT: Food alias normalization
# Maps regional / alternate names to canonical terms
# that align with searchKeywords and mealName fields
# -----------------------------------------------
FOOD_ALIAS_MAP = {
    # Hindi → Canonical
    "dahi": "curd",
    "bhindi": "okra",
    "baingan": "eggplant",
    "chole": "chickpeas",
    "chhole": "chickpeas",
    "chawal": "rice",
    "anda": "egg",
    "gosht": "mutton",
    "murgh": "chicken",
    "murg": "chicken",
    "panir": "paneer",
    "suji": "semolina",
    "rava": "semolina",
    "moong": "mung",
    "urad": "black gram",
    "sarson": "mustard",
    "palak": "spinach",
    "gobi": "cauliflower",
    "aata": "wheat",
    "atta": "wheat",
    "besan": "gram flour",
    "ghee": "ghee",
    "makhan": "butter",
    "doodh": "milk",
    "dudh": "milk",
    "nimbu": "lemon",
    "jeera": "cumin",
    "haldi": "turmeric",
    "adrak": "ginger",
    "lasun": "garlic",
    "lehsun": "garlic",
    "tamatar": "tomato",
    "pyaaz": "onion",
    "peyaj": "onion",
    "mirchi": "chili",
    "chapati": "roti",
    "chapatis": "roti",
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
    IMPROVEMENT: Replace regional food aliases with canonical names.

    This runs BEFORE spelling correction so that aliases are normalized
    first, and any remaining misspellings are caught by correct_spelling().

    Args:
        tokens: list of cleaned tokens

    Returns:
        list of tokens with aliases replaced
    """
    normalized = []
    for token in tokens:
        if token in FOOD_ALIAS_MAP:
            canonical = FOOD_ALIAS_MAP[token]
            print(f"[alias] '{token}' → '{canonical}'")
            # Canonical may be multi-word (e.g., "gram flour")
            normalized.extend(canonical.split())
        else:
            normalized.append(token)
    return normalized


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
