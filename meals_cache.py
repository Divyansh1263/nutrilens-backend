"""
meals_cache.py
==============
Global in-memory cache for the meals Firestore collection.

Design goals
------------
• Meals are loaded ONCE at server startup (load_meals_cache).
• All subsequent reads hit this module-level list — ZERO Firestore reads per request.
• Falls back to .cache/meals_cache.json if Firestore is unavailable or empty.
• Thread-safe: a threading.Lock protects the write path; reads are lock-free
  because Python list replacement is atomic (GIL) and we only swap the reference.
• refresh_meals_cache() reloads from Firestore on demand (e.g., admin endpoint).
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from utils.logger import app_logger


# ------------------------------------------------------------------ #
# Cache path helper — Cloud Run has read-only FS except /tmp         #
# ------------------------------------------------------------------ #

def get_cache_path(filename: str) -> str:
    """
    Return a writable path for a cache file.

    On Cloud Run the app directory is read-only; /tmp is the only
    writable location.  Set CACHE_DIR env var to override (e.g. for
    local dev where you want the cache next to the source).
    """
    base = os.environ.get("CACHE_DIR", "/tmp")
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, filename)

# ------------------------------------------------------------------ #
# TASK 1 – Global cache variables                                     #
# ------------------------------------------------------------------ #

MEALS_CACHE: List[Dict[str, Any]] = []
MEALS_SOURCE: Optional[str] = None        # "firestore" | "local" | None

# Internal write lock – guards the load/refresh path only.
_load_lock = threading.Lock()

# Pre-built index: meal_type (lowercase) → list of meals
_MEALS_BY_TYPE: Dict[str, List[Dict[str, Any]]] = {
    "breakfast": [],
    "lunch": [],
    "snack": [],
    "dinner": [],
}


# ------------------------------------------------------------------ #
# TASK 2 – Load cache at startup                                      #
# ------------------------------------------------------------------ #

def load_meals_cache() -> None:
    """
    Populate MEALS_CACHE from Firestore (primary) or local JSON (fallback).

    Call this ONCE before any routes handle requests.
    Subsequent calls are safe but skip re-loading if cache is already warm.
    """
    global MEALS_CACHE, MEALS_SOURCE, _MEALS_BY_TYPE

    with _load_lock:
        # Idempotency guard – skip if already loaded
        if MEALS_CACHE:
            app_logger.info(
                "[cache] Already loaded %d meals from %s – skipping reload.",
                len(MEALS_CACHE), MEALS_SOURCE
            )
            return

        # ── Attempt 1: Firestore ──────────────────────────────────── #
        meals = _load_from_firestore()
        source = "firestore"

        # ── Attempt 2: Local JSON fallback ───────────────────────── #
        if not meals:
            app_logger.warning(
                "[cache-fallback] Firestore returned 0 meals — loading from local cache."
            )
            meals = _load_from_local()
            source = "local"

        # ── Attempt 3: dev_store seed (last resort) ──────────────── #
        if not meals:
            app_logger.warning(
                "[cache-fallback] Local cache also empty — using seed meals."
            )
            from dev_store import SEED_MEALS
            meals = list(SEED_MEALS)
            source = "seed"

        # ── Commit ───────────────────────────────────────────────── #
        by_type: Dict[str, List[Dict[str, Any]]] = {
            "breakfast": [], "lunch": [], "snack": [], "dinner": []
        }
        for m in meals:
            mt = (m.get("meal_type") or "").lower()
            if mt in by_type:
                by_type[mt].append(m)

        # Atomic swap (GIL makes list assignment safe for readers)
        MEALS_CACHE = meals
        MEALS_SOURCE = source
        _MEALS_BY_TYPE = by_type

        if source == "firestore":
            app_logger.info(
                "[cache-init] Loaded %d meals from firestore", len(MEALS_CACHE)
            )
        else:
            app_logger.warning(
                "[cache-fallback] Loaded %d meals from %s", len(MEALS_CACHE), source
            )

        # Persist to disk so next crash/restart has a warm local copy
        if source == "firestore":
            _persist_to_disk(MEALS_CACHE)

        # Keep dev_store.MEALS_CACHE in sync for legacy code paths
        try:
            from dev_store import set_meals_cache
            set_meals_cache(MEALS_CACHE)
        except Exception:
            pass


# ------------------------------------------------------------------ #
# TASK 6 – Optional refresh                                           #
# ------------------------------------------------------------------ #

def refresh_meals_cache() -> None:
    """
    Force-reload from Firestore and replace the in-memory cache.

    Thread-safe.  Safe to call from an admin endpoint or cron job.
    """
    global MEALS_CACHE, MEALS_SOURCE, _MEALS_BY_TYPE

    app_logger.info("[cache-refresh] Refreshing meals cache from Firestore …")

    with _load_lock:
        meals = _load_from_firestore()
        source = "firestore"

        if not meals:
            app_logger.warning("[cache-refresh] Firestore empty — keeping existing cache.")
            return

        by_type: Dict[str, List[Dict[str, Any]]] = {
            "breakfast": [], "lunch": [], "snack": [], "dinner": []
        }
        for m in meals:
            mt = (m.get("meal_type") or "").lower()
            if mt in by_type:
                by_type[mt].append(m)

        MEALS_CACHE = meals
        MEALS_SOURCE = source
        _MEALS_BY_TYPE = by_type

        app_logger.info(
            "[cache-refresh] Refreshed: %d meals from firestore", len(MEALS_CACHE)
        )

        _persist_to_disk(MEALS_CACHE)

        try:
            from dev_store import set_meals_cache
            set_meals_cache(MEALS_CACHE)
        except Exception:
            pass


# ------------------------------------------------------------------ #
# TASK 5 – Safety accessor                                            #
# ------------------------------------------------------------------ #

def get_meals(context: str = "") -> List[Dict[str, Any]]:
    """
    Return the in-memory meals list.

    Args:
        context: Optional label used in the per-request log line (TASK 7).

    Raises:
        RuntimeError: If the cache is empty (startup load failed entirely).
    """
    # TASK 5 – safety check
    if not MEALS_CACHE:
        raise RuntimeError(
            "Meals cache is empty. Ensure load_meals_cache() ran at startup."
        )

    # TASK 7 – log once per request call-site
    if context:
        app_logger.debug(
            "[cache] Using %d meals from %s (context=%s)",
            len(MEALS_CACHE), MEALS_SOURCE, context
        )

    return MEALS_CACHE


def get_meals_by_type(meal_type: str) -> List[Dict[str, Any]]:
    """Return pre-indexed meals for a given meal_type (zero iteration cost)."""
    return _MEALS_BY_TYPE.get(meal_type.lower(), [])


# ------------------------------------------------------------------ #
# Private helpers                                                     #
# ------------------------------------------------------------------ #

def _load_from_firestore() -> List[Dict[str, Any]]:
    try:
        from firebase_admin import firestore
        db = firestore.client()
        docs = db.collection("meals").stream()
        meals: List[Dict[str, Any]] = []
        for d in docs:
            m = d.to_dict()
            m["id"] = d.id
            meals.append(m)
        return meals
    except Exception as exc:
        app_logger.error("[cache] Firestore load failed: %s", exc)
        return []


def _local_cache_path() -> str:
    # Cloud Run: write to /tmp (or CACHE_DIR). Local dev: same unless overridden.
    return get_cache_path("meals_cache.json")


def _load_from_local() -> List[Dict[str, Any]]:
    path = _local_cache_path()
    if not os.path.exists(path):
        app_logger.warning("[cache] No local cache at %s — using in-memory fallback", path)
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return [d for d in data if isinstance(d, dict)]
    except Exception as exc:
        app_logger.warning("[cache] Local cache load failed (%s) — using in-memory fallback", exc)
    return []


def _persist_to_disk(meals: List[Dict[str, Any]]) -> None:
    path = _local_cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(meals, f, ensure_ascii=False)
        app_logger.info("[cache] Persisted %d meals to %s", len(meals), path)
    except Exception as exc:
        app_logger.warning("[cache] Could not persist meals to disk: %s", exc)
