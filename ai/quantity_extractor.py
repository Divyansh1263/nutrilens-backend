# ai/quantity_extractor.py
# Stage 3: Improved quantity extraction
# Supports: digits, word numbers, fractions, portion units
#
# TASK 1 FIX: Handle [number] + [adjective/modifier] + [food] pattern.
#   e.g. "3 jawar roti" → roti gets qty=3, NOT jawar=3 / roti=1.
#   Grain/variety adjectives between a number and the food entity are
#   treated as transparent modifiers during quantity lookup.

import re

# -----------------------------------------------
# Dictionaries
# -----------------------------------------------
NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12,
}

FRACTIONS = {
    "half": 0.5,
    "quarter": 0.25,
    "three-quarter": 0.75,
    "three-quarters": 0.75,
}

PORTION_WORDS = {
    "bowl", "cup", "plate", "glass", "piece", "pieces",
    "serving", "servings", "slice", "slices",
}

# -----------------------------------------------
# TASK 1 FIX: Grain / variety adjectives that can appear between
# a quantity and the actual food entity (e.g. "3 jawar roti").
# These tokens are skipped during the backwards quantity search
# so the number is correctly attributed to the real food.
# -----------------------------------------------
FOOD_ADJECTIVES = {
    # Millet / grain varieties
    "jawar", "jowar", "bajra", "ragi", "maize", "corn",
    "multigrain", "whole", "wheat",
    # Size / style descriptors
    "plain", "simple", "small", "large", "big", "medium",
    "thin", "thick", "soft", "crispy", "fried", "baked",
    "boiled", "steamed",
    # Colour / taste descriptors
    "white", "brown", "red", "green", "yellow",
    "sweet", "spicy", "mild",
}


def extract_quantities(entities, original_text):
    """
    Extract quantities for each detected food entity from the original text.

    Strategy:
      1. Scan the original text for patterns like:
         - "<digit> <food>"          → 3 rotis
         - "<word-number> <food>"    → two rotis
         - "<fraction> <food>"       → half bowl rice
         - "<fraction> <portion> <food>" → half bowl rice
         - "<digit> <portion> <food>"    → 2 plates biryani

      2. Default to 1 if no quantity is found for an entity.

    Args:
        entities:       list of food entity strings (single or multi-word)
        original_text:  the cleaned text (lowercase, no stopwords)

    Returns:
        dict of {entity: quantity}
    """
    text_lower = original_text.lower()
    tokens = text_lower.split()
    quantities = {}

    for entity in entities:
        qty = _find_quantity_for_entity(entity, tokens, text_lower)
        quantities[entity] = qty

    return quantities


def _find_quantity_for_entity(entity, tokens, full_text):
    """
    Look backwards from the entity position to find a quantity.

    TASK 1 FIX: Transparent modifier tokens (grain adjectives like "jawar",
    portion words like "bowl") are skipped during the backwards scan so a
    number appearing before them is still correctly assigned.

    Example: "3 jawar roti"
      - entity = "roti",  pos=2
      - lookback=1 → tokens[1]="jawar" (FOOD_ADJECTIVE) → skip
      - lookback=2 → tokens[0]="3"     (digit)          → qty=3  ✓
    """
    entity_tokens = entity.split()
    first_entity_token = entity_tokens[0]

    # Find the position of the entity's first token in the full token list
    entity_positions = []
    for i, t in enumerate(tokens):
        if t == first_entity_token:
            # Verify full entity match
            candidate = " ".join(tokens[i:i + len(entity_tokens)])
            if candidate == entity:
                entity_positions.append(i)

    if not entity_positions:
        return 1  # Default

    # Use the first occurrence
    pos = entity_positions[0]

    # ── Transparent tokens: skipped when scanning backwards ───────────────
    # PORTION_WORDS: "bowl", "cup", etc.
    # FOOD_ADJECTIVES: "jawar", "jowar", "bajra", "plain", "whole", etc.
    TRANSPARENT = PORTION_WORDS | FOOD_ADJECTIVES

    qty = 1
    # Extend scan window so we can skip up to 3 transparent tokens
    max_lookback = min(6, pos + 1)

    for lookback in range(1, max_lookback):
        prev_token = tokens[pos - lookback]

        # Check digit
        if prev_token.isdigit():
            qty = int(prev_token)
            print(f"[quantity] '{entity}' qty={qty} (digit found at -{lookback})")
            break

        # Check word number
        if prev_token in NUMBER_WORDS:
            qty = NUMBER_WORDS[prev_token]
            print(f"[quantity] '{entity}' qty={qty} (word-number '{prev_token}' at -{lookback})")
            break

        # Check fraction
        if prev_token in FRACTIONS:
            qty = FRACTIONS[prev_token]
            print(f"[quantity] '{entity}' qty={qty} (fraction '{prev_token}' at -{lookback})")
            break

        # Transparent token (portion word or food adjective) → keep scanning
        if prev_token in TRANSPARENT:
            print(f"[quantity] '{entity}' skipping transparent token '{prev_token}' at -{lookback}")
            continue

        # Any other non-quantity token → stop
        break

    if qty == 1:
        print(f"[quantity] '{entity}' qty=1 (default — no number found)")
    return qty
