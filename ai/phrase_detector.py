# ai/phrase_detector.py
# Stage 2: Multi-word food phrase detection using sliding windows
#
# IMPROVEMENT (v2.1):
#   Extended to support 4-word phrases (was 3-word max).
#   Examples: "paneer butter masala", "chicken tikka masala",
#             "vegetable pulao rice"

# Module-level cache (populated by init)
_known_phrases = set()       # set of normalized phrase strings
_max_phrase_len = 4          # UPGRADED: was 3, now supports 4-word phrases


def init_phrase_detector(meals):
    """
    Build phrase set from mealName + searchKeywords.
    Called once at server startup.

    Generates sub-phrases of length 2, 3, and 4 from multi-word meal names.
    """
    global _known_phrases

    phrases = set()
    for meal in meals:
        name = (meal.get("mealName") or meal.get("name") or meal.get("title") or "").lower().strip()
        words = name.split()

        # Add multi-word names as phrases
        if len(words) >= 2:
            phrases.add(name)
            # Generate 2-word, 3-word, and 4-word sub-phrases
            for i in range(len(words)):
                for length in range(2, min(_max_phrase_len + 1, len(words) - i + 1)):
                    sub = " ".join(words[i:i + length])
                    phrases.add(sub)

        # Add multi-word keywords
        keywords = meal.get("searchKeywords") or meal.get("aliases") or []
        for kw in keywords:
            kw_lower = kw.lower().strip()
            kw_words = kw_lower.split()
            if len(kw_words) >= 2:
                phrases.add(kw_lower)
                # Also generate sub-phrases from keywords
                for i in range(len(kw_words)):
                    for length in range(2, min(_max_phrase_len + 1, len(kw_words) - i + 1)):
                        sub = " ".join(kw_words[i:i + length])
                        phrases.add(sub)

    _known_phrases = phrases
    print(f"[phrase_detector] Phrase set built: {len(_known_phrases)} phrases "
          f"(max {_max_phrase_len} tokens)")


def detect_phrases(tokens):
    """
    Greedy longest-match phrase detection using sliding window.
    Tries windows of 4, 3, then 2 tokens (longest match first).

    Args:
        tokens: list of cleaned, spelling-corrected tokens

    Returns:
        list of strings — each is either a multi-word phrase or a single token
    """
    if not _known_phrases:
        return tokens  # No phrases loaded

    result = []
    i = 0
    n = len(tokens)

    while i < n:
        matched = False

        # Try longest window first (4 tokens, then 3, then 2)
        for window_size in range(_max_phrase_len, 1, -1):
            if i + window_size > n:
                continue

            candidate = " ".join(tokens[i:i + window_size])

            if candidate in _known_phrases:
                result.append(candidate)
                i += window_size
                matched = True
                break

        if not matched:
            result.append(tokens[i])
            i += 1

    return result
