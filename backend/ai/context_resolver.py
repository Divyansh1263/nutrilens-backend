# ai/context_resolver.py
# Stage 6: Context-aware meal resolution
# Detects common food combinations and returns context scores
#
# IMPROVEMENTS (v2.4):
#   - Split rules into STRONG (boost=1.0) and WEAK (boost=0.5)
#   - Strong rules = well-known canonical Indian combos
#   - Weak rules  = generic / secondary combos
#   - resolve_context() checks strong first, then weak
#   - TASK 1: dal+roti, chapati+dal, rice+curry promoted to STRONG
#   - TASK 7: context strength (STRONG/WEAK) logged per pair

# ── STRONG context rules ──────────────────────────────────────────────────────
# High-confidence canonical Indian meal pairs. boost = STRONG_BOOST (1.0)
STRONG_CONTEXT_RULES = {
    frozenset(["dal",          "rice"]):     "Dal Chawal",
    frozenset(["dal",          "chawal"]):   "Dal Chawal",
    frozenset(["rajma",        "rice"]):     "Rajma Chawal",
    frozenset(["rajma",        "chawal"]):   "Rajma Chawal",
    frozenset(["kidney beans", "rice"]):    "Rajma Chawal",
    frozenset(["chole",        "rice"]):     "Chole Chawal",
    frozenset(["chole",        "chawal"]):   "Chole Chawal",
    frozenset(["chickpeas",    "rice"]):     "Chole Chawal",
    frozenset(["kadhi",        "rice"]):     "Kadhi Chawal",
    frozenset(["kadhi",        "chawal"]):   "Kadhi Chawal",
    frozenset(["sambar",       "rice"]):     "Sambar Rice",
    frozenset(["curd",         "rice"]):     "Curd Rice",
    frozenset(["dahi",         "rice"]):     "Curd Rice",
    frozenset(["idli",         "sambar"]):   "Idli Sambar",
    frozenset(["dosa",         "sambar"]):   "Dosa Sambar",
    frozenset(["vada",         "sambar"]):   "Medu Vada",
    frozenset(["medu vada",    "sambar"]):   "Medu Vada",
    frozenset(["roti",           "sabzi"]):               "Roti Sabzi",
    frozenset(["chapati",        "sabzi"]):               "Roti Sabzi",
    # Post-alias forms ("sabzi" → "mixed vegetable sabzi" in Step 2)
    frozenset(["roti",           "mixed vegetable sabzi"]): "Roti Sabzi",
    frozenset(["chapati",        "mixed vegetable sabzi"]): "Roti Sabzi",
    frozenset(["puri",           "sabzi"]):               "Puri Sabzi",
    frozenset(["puri",           "mixed vegetable sabzi"]): "Puri Sabzi",
    frozenset(["puri",           "aloo"]):           "Puri Aloo",
    frozenset(["puri",           "potato"]):         "Puri Aloo",
    frozenset(["poha",           "jalebi"]):         "Poha Jalebi",
    frozenset(["bread",          "egg"]):            "Bread Omelette",
    frozenset(["bread",          "anda"]):           "Bread Omelette",
    # TASK 1: Promoted from WEAK — canonical combos deserve strong boost
    frozenset(["dal",            "roti"]):           "Dal Roti",
    frozenset(["chapati",        "dal"]):            "Dal Roti",
    frozenset(["rice",           "curry"]):          "Dal Chawal",
}

# ── WEAK context rules ────────────────────────────────────────────────────────
# Secondary / generic combos. boost = WEAK_BOOST (0.5)
WEAK_CONTEXT_RULES = {
    frozenset(["lemon",     "rice"]):    "Lemon Rice",
    frozenset(["egg",       "rice"]):    "Egg Rice",
    frozenset(["anda",      "rice"]):    "Egg Rice",
    frozenset(["fish",      "rice"]):    "Fish Curry Rice",
    frozenset(["machli",    "rice"]):    "Fish Curry Rice",
    frozenset(["mutton",    "rice"]):    "Mutton Rice",
    frozenset(["gosht",     "rice"]):    "Mutton Rice",
    frozenset(["chicken",   "rice"]):    "Chicken Rice",
    frozenset(["murgh",     "rice"]):    "Chicken Rice",
    frozenset(["sabzi",     "rice"]):    "Sabzi Chawal",
    frozenset(["sabzi",     "chawal"]):  "Sabzi Chawal",
    # NOTE: dal+roti and chapati+dal promoted to STRONG_CONTEXT_RULES (TASK 1)
    frozenset(["paneer",    "roti"]):    "Paneer Roti",
    frozenset(["paneer",    "chapati"]): "Paneer Roti",
    frozenset(["aloo",      "roti"]):    "Aloo Roti",
    frozenset(["potato",    "roti"]):    "Aloo Roti",
    frozenset(["egg",       "paratha"]): "Egg Paratha",
    frozenset(["anda",      "paratha"]): "Egg Paratha",
    frozenset(["aloo",      "paratha"]): "Aloo Paratha",
    frozenset(["potato",    "paratha"]): "Aloo Paratha",
    frozenset(["naan",      "paneer"]):  "Paneer Butter Masala",
    frozenset(["idli",      "chutney"]): "Idli Chutney",
    frozenset(["dosa",      "chutney"]): "Dosa Chutney",
    frozenset(["uttapam",   "sambar"]):  "Uttapam Sambar",
    frozenset(["paratha",   "curd"]):    "Paratha",
    frozenset(["paratha",   "dahi"]):    "Paratha",
    frozenset(["bread",     "butter"]):  "Bread Butter",
}

# Boost values
STRONG_BOOST = 1.0
WEAK_BOOST   = 0.5

# Unified dict — used by any code that still references CONTEXT_RULES directly
CONTEXT_RULES = {**STRONG_CONTEXT_RULES, **WEAK_CONTEXT_RULES}


def resolve_context(entities, quantities):
    """
    IMPROVED: Instead of replacing entities with combo meals,
    this now returns a context_scores dict alongside the original entities.

    Tiered boosting:
      - STRONG combo pair detected → context_score = STRONG_BOOST (1.0)
      - WEAK combo pair detected   → context_score = WEAK_BOOST  (0.5)
      - No match                   → context_score = 0.0

    Args:
        entities:    list of detected food entity strings
        quantities:  dict of {entity: quantity}

    Returns:
        (resolved_entities, resolved_quantities, context_scores)
        - resolved_entities:    updated list (combo added, originals removed)
        - resolved_quantities:  updated dict
        - context_scores:       dict of {entity: score} for hybrid matcher
    """
    context_scores = {e: 0.0 for e in entities}  # Default: no context boost

    if len(entities) < 2:
        return entities, quantities, context_scores

    resolved_entities = []
    resolved_quantities = {}
    resolved_context_scores = {}
    consumed = set()

    entity_set = [e.lower() for e in entities]

    # Check pairs — strong rules first, then weak
    for i in range(len(entity_set)):
        if i in consumed:
            continue
        for j in range(i + 1, len(entity_set)):
            if j in consumed:
                continue

            pair = frozenset([entity_set[i], entity_set[j]])

            # Determine which rule set matched and the appropriate boost
            if pair in STRONG_CONTEXT_RULES:
                combo_name = STRONG_CONTEXT_RULES[pair]
                boost = STRONG_BOOST
            elif pair in WEAK_CONTEXT_RULES:
                combo_name = WEAK_CONTEXT_RULES[pair]
                boost = WEAK_BOOST
            else:
                continue

            qty_i = quantities.get(entities[i], 1)
            qty_j = quantities.get(entities[j], 1)
            combo_qty = max(qty_i, qty_j)

            resolved_entities.append(combo_name)
            resolved_quantities[combo_name] = combo_qty
            resolved_context_scores[combo_name] = boost

            consumed.add(i)
            consumed.add(j)

            # TASK 7: Log context strength clearly
            tier = "STRONG" if boost == STRONG_BOOST else "WEAK"
            print(
                f"[context] '{entities[i]}' + '{entities[j]}' "
                f"→ '{combo_name}' [context_strength={tier}, boost={boost:.1f}]"
            )
            break

    # Add remaining un-consumed entities (no context boost)
    for i, entity in enumerate(entities):
        if i not in consumed:
            resolved_entities.append(entity)
            resolved_quantities[entity] = quantities.get(entity, 1)
            resolved_context_scores[entity] = 0.0

    return resolved_entities, resolved_quantities, resolved_context_scores
