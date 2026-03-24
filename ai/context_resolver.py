# ai/context_resolver.py
# Stage 6: Context-aware meal resolution
# Detects common food combinations and returns context scores
#
# IMPROVEMENT (v2.1):
#   Changed from OVERRIDE behavior to SCORING behavior.
#   Instead of replacing entities, returns context_scores dict
#   that feeds into hybrid_matcher as a 4th signal.
#   Original entities are preserved — context just boosts
#   the combo meal in hybrid scoring.

# -----------------------------------------------
# Context Rules: (frozenset of foods) → canonical meal name
# -----------------------------------------------
CONTEXT_RULES = {
    frozenset(["dal", "rice"]): "Dal Chawal",
    frozenset(["dal", "chawal"]): "Dal Chawal",
    frozenset(["rajma", "rice"]): "Rajma Chawal",
    frozenset(["rajma", "chawal"]): "Rajma Chawal",
    frozenset(["chole", "rice"]): "Chole Chawal",
    frozenset(["chole", "chawal"]): "Chole Chawal",
    frozenset(["chickpeas", "rice"]): "Chole Chawal",
    frozenset(["kadhi", "rice"]): "Kadhi Chawal",
    frozenset(["kadhi", "chawal"]): "Kadhi Chawal",
    frozenset(["sambar", "rice"]): "Sambar Rice",
    frozenset(["curd", "rice"]): "Curd Rice",
    frozenset(["dahi", "rice"]): "Curd Rice",
    frozenset(["lemon", "rice"]): "Lemon Rice",
    frozenset(["roti", "sabzi"]): "Roti Sabzi",
    frozenset(["chapati", "sabzi"]): "Roti Sabzi",
    frozenset(["idli", "sambar"]): "Idli Sambar",
    frozenset(["idli", "chutney"]): "Idli Chutney",
    frozenset(["dosa", "sambar"]): "Dosa Sambar",
    frozenset(["dosa", "chutney"]): "Dosa Chutney",
    frozenset(["vada", "sambar"]): "Medu Vada",
    frozenset(["puri", "sabzi"]): "Puri Sabzi",
    frozenset(["puri", "aloo"]): "Puri Aloo",
    frozenset(["poha", "jalebi"]): "Poha Jalebi",
    frozenset(["paratha", "curd"]): "Paratha",
    frozenset(["naan", "paneer"]): "Paneer Butter Masala",
}

# Context boost value (used as the context_score signal in hybrid scoring)
CONTEXT_BOOST = 1.0


def resolve_context(entities, quantities):
    """
    IMPROVED: Instead of replacing entities with combo meals,
    this now returns a context_scores dict alongside the original entities.

    The context_scores map entity names to a boost value (0.0 or 1.0).
    Entities that are part of a detected combo have their context_score
    set to CONTEXT_BOOST. The combo meal name is ADDED as a new entity
    (not replacing the originals), and the hybrid matcher uses the
    context_score as a 4th signal.

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

    # Check pairs
    for i in range(len(entity_set)):
        if i in consumed:
            continue
        for j in range(i + 1, len(entity_set)):
            if j in consumed:
                continue

            pair = frozenset([entity_set[i], entity_set[j]])

            if pair in CONTEXT_RULES:
                combo_name = CONTEXT_RULES[pair]
                qty_i = quantities.get(entities[i], 1)
                qty_j = quantities.get(entities[j], 1)
                combo_qty = max(qty_i, qty_j)

                # Add the combo meal as a new entity with context boost
                resolved_entities.append(combo_name)
                resolved_quantities[combo_name] = combo_qty
                resolved_context_scores[combo_name] = CONTEXT_BOOST

                consumed.add(i)
                consumed.add(j)

                print(f"[context] '{entities[i]}' + '{entities[j]}' "
                      f"→ '{combo_name}' (context_score={CONTEXT_BOOST})")
                break

    # Add remaining un-consumed entities (no context boost)
    for i, entity in enumerate(entities):
        if i not in consumed:
            resolved_entities.append(entity)
            resolved_quantities[entity] = quantities.get(entity, 1)
            resolved_context_scores[entity] = 0.0

    return resolved_entities, resolved_quantities, resolved_context_scores
