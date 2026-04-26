# utils/calorie_utils.py
#
# Step 6.2 + Step 7 + Step 8 — In-memory cache for user calorie targets.
#
# NOTE:
#   This is an in-memory cache. It resets on every server restart.
#   To persist across restarts, replace the cache helpers with Redis calls.
#
# Cache key : user_id
# TTL       : 10 minutes
# Max size  : 100 entries  (FIFO eviction — enforced by cache_utils)
# Thread    : all cache access protected by cache_utils._cache_lock
#
import logging
from ai.target_calculator import compute_base_targets, apply_calorie_banking
from repositories.user_repository import user_repo
from utils.cache_utils import _get_cache, _set_cache
from firebase_admin import firestore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cache store
# ---------------------------------------------------------------------------
_user_target_cache: dict = {}
_USER_TARGET_TTL   = 600  # 10 minutes in seconds


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_target(user_id: str):
    """Return cached target or None (thread-safe via cache_utils)."""
    result = _get_cache(user_id, _user_target_cache, _USER_TARGET_TTL)
    if result is not None:
        logger.info("[cache] user_target HIT  — user=%s", user_id)
    else:
        logger.info("[cache] user_target MISS — user=%s", user_id)
    return result


def _set_target(user_id: str, data: dict) -> None:
    _set_cache(user_id, data, _user_target_cache, _USER_TARGET_TTL)


def invalidate_user_target_cache(user_id: str) -> None:
    """Step 6.5 — call when the user updates their profile or targets."""
    from utils.cache_utils import _cache_lock
    with _cache_lock:
        _user_target_cache.pop(user_id, None)
    logger.info("[cache] user_target INVALIDATED — user=%s", user_id)


# ---------------------------------------------------------------------------
# Public API  (unchanged signature — backward compatible)
# ---------------------------------------------------------------------------

def get_or_calculate_user_targets(user_id: str, date_str: str) -> dict:
    """
    Fetch target from daily_targets. If not exists, calculate from profile,
    save, and return.

    Step 6.2 / 7 / 8: checks in-memory thread-safe cache first; falls
    through to Firestore only on a miss.
    """
    # 1. In-memory cache check (zero Firestore reads on hit)
    cached = _get_target(user_id)
    if cached is not None:
        return cached

    # 2. Firestore daily_target lookup
    try:
        targets = user_repo.get_daily_target(user_id, date_str)
    except Exception as e:
        if "Quota exceeded" in str(e) or "429" in str(e):
            return {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        raise

    if targets:
        _set_target(user_id, targets)
        return targets

    # 3. Fallback: compute from user profile
    try:
        user_profile = user_repo.get_user_profile(user_id)
    except Exception as e:
        if "Quota exceeded" in str(e) or "429" in str(e):
            return {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}
        raise

    if not user_profile:
        return {"calories": 2000, "protein": 100, "carbs": 250, "fat": 60}

    base  = compute_base_targets(user_profile)
    final = apply_calorie_banking(user_id, base, user_repo.db)

    target_data = {
        "userId": user_id,
        "date":   date_str,
        **final,
        "generated_by": "ai",
        "created_at": firestore.SERVER_TIMESTAMP
            if hasattr(user_repo.db, "collection") else None,
    }

    try:
        user_repo.save_daily_target(user_id, date_str, target_data)
    except Exception as e:
        if "Quota exceeded" in str(e) or "429" in str(e):
            _set_target(user_id, final)
            return final
        raise

    _set_target(user_id, final)
    return final
