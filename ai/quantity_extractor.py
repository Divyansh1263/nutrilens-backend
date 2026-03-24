# ai/quantity_extractor.py
# Stage 3: Improved quantity extraction
# Supports: digits, word numbers, fractions, portion units

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

    # Look at the 1-3 tokens BEFORE the entity
    qty = 1
    fraction_found = False
    portion_found = False

    for lookback in range(1, min(4, pos + 1)):
        prev_token = tokens[pos - lookback]

        # Check digit
        if prev_token.isdigit():
            qty = int(prev_token)
            break

        # Check word number
        if prev_token in NUMBER_WORDS:
            qty = NUMBER_WORDS[prev_token]
            break

        # Check fraction
        if prev_token in FRACTIONS:
            qty = FRACTIONS[prev_token]
            fraction_found = True
            break

        # Check portion word (skip it, look further back for number)
        if prev_token in PORTION_WORDS:
            portion_found = True
            continue

        # If we hit a non-quantity token, stop looking
        if prev_token not in PORTION_WORDS:
            break

    # Special case: if we found a portion word but no number,
    # check if there's a fraction/number before the portion word
    if portion_found and qty == 1:
        for lookback in range(2, min(5, pos + 1)):  # Start from 2 to look past portion word
            prev_token = tokens[pos - lookback]
            if prev_token in PORTION_WORDS:
                continue
            if prev_token.isdigit():
                qty = int(prev_token)
                break
            if prev_token in NUMBER_WORDS:
                qty = NUMBER_WORDS[prev_token]
                break
            if prev_token in FRACTIONS:
                qty = FRACTIONS[prev_token]
                break
            break

    return qty
