# utils/cache_utils.py
#
# Step 7 + Step 8 — Production-safe, thread-safe in-memory cache helpers.
#
# NOTE:
#   This is an in-memory cache. It resets on every server restart.
#   In production this can be replaced with Redis or a distributed cache
#   by swapping out _get_cache / _set_cache with Redis client calls — the
#   call-sites in tracker_service.py and calorie_utils.py need no changes.
#
# Features:
#   Step 7.1  — MAX_CACHE_SIZE cap (FIFO eviction)
#   Step 7.2  — timestamp stored alongside every entry {"data": …, "ts": …}
#   Step 7.3  — lazy cleanup on every read and write
#   Step 7.4  — generic _get_cache / _set_cache / _cleanup_cache helpers
#   Step 7.5  — cleanup summary logged
#   Step 8.1  — threading.Lock guards all cache mutations
#   Step 8.2  — stdlib logging instead of print
#
import time
import logging
from threading import Lock

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MAX_CACHE_SIZE = 100   # max entries per cache dict before FIFO eviction

# A single lock instance is shared across ALL cache dicts.
# Fine-grained per-dict locks would reduce contention but add complexity;
# a single lock is safe and sufficient for this traffic level.
_cache_lock = Lock()


# ---------------------------------------------------------------------------
# Step 7.4 + 8.1 — Thread-safe generic helpers
# ---------------------------------------------------------------------------

def _cleanup_cache(cache: dict, ttl: float) -> None:
    """
    Step 7.3 — Remove expired entries, then FIFO-evict if still over limit.

    MUST be called while the caller holds _cache_lock.
    """
    now = time.time()
    before = len(cache)

    # 1. Expire stale entries
    expired_keys = [k for k, v in cache.items() if (now - v["ts"]) >= ttl]
    for k in expired_keys:
        del cache[k]

    # 2. FIFO eviction for size cap
    while len(cache) > MAX_CACHE_SIZE:
        oldest = next(iter(cache))
        del cache[oldest]

    removed = before - len(cache)
    if removed > 0:
        logger.info(
            "[cache] CLEANUP — removed %d entries "
            "(expired=%d, evicted=%d, remaining=%d)",
            removed, len(expired_keys), removed - len(expired_keys), len(cache),
        )


def _get_cache(key, cache: dict, ttl: float):
    """
    Step 7.4 / 8.1 — Thread-safe cache lookup.

    Runs cleanup inside the lock, then returns the stored value or None.
    """
    with _cache_lock:
        _cleanup_cache(cache, ttl)
        entry = cache.get(key)
        if entry is not None:
            return entry["data"]
        return None


def _set_cache(key, value, cache: dict, ttl: float) -> None:
    """
    Step 7.4 / 8.1 — Thread-safe cache write.

    Enforces MAX_CACHE_SIZE via cleanup before inserting.
    Step 7.2 — always stores {"data": value, "ts": timestamp}.
    """
    with _cache_lock:
        _cleanup_cache(cache, ttl)
        cache[key] = {"data": value, "ts": time.time()}
