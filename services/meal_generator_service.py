# services/meal_generator_service.py
# ML integration: lazy-import so the model is only loaded after gunicorn forks.
import random
from utils.logger import app_logger
from utils.date_utils import get_days_difference, get_today_str
from utils.diet_utils import (
    apply_diet_filter,
    validate_plan,
    annotate_plan_item,
    resolve_explanation,
)
from utils.meal_validation import clean_meal_pool
from utils.macro_optimizer import optimize_plan, build_macro_targets
from config.config import (
    BREAKFAST_RANGE, LUNCH_RANGE, DINNER_RANGE, SNACK_RANGE,
    CALORIE_TOLERANCE, MEAL_SPLIT_RATIOS, MAX_DISHES_PER_MEAL,
    PENALTY_YESTERDAY, PENALTY_LAST_3_DAYS, PENALTY_WEEK_FREQ_3,
    PENALTY_WEEK_FREQ_2, PREFERENCE_MULTIPLIER
)
from repositories.user_repository import user_repo
from repositories.meal_repository import meal_repo
from repositories.tracker_repository import tracker_repo

class MealGeneratorService:
    # ---------------------------------------------------------------------
    # Category keywords (simple heuristic filtering)
    # ---------------------------------------------------------------------
    BREAKFAST_KEYWORDS = {
        "poha", "upma", "idli", "dosa", "paratha", "egg", "eggs", "milk", "banana",
        "fruit", "oats", "bread", "toast", "curd", "yogurt", "pancake", "sprouts",
        "sandwich"
    }
    LUNCH_DINNER_KEYWORDS = {
        "roti", "chapati", "rice", "dal", "sabzi", "paneer", "chicken", "rajma",
        "chole", "curd", "yogurt", "salad", "khichdi", "biryani", "fish"
    }
    SNACK_KEYWORDS = {
        "fruit", "nuts", "peanut", "buttermilk", "chaas", "sprouts", "sandwich",
        "juice", "shake", "tea", "coffee", "biscuit"
    }
    
    def generate_daily_plan(self, user_id, date_str):
        app_logger.info("Generating meal plan for user %s", user_id)

        # 1. Fetch user targets
        target_calories = self.get_user_targets(user_id, date_str)
        if not target_calories:
            return None, "Error calculating targets"

        # 2. Fetch History
        recent_plans = tracker_repo.get_recent_plans(user_id, limit=7)
        user_history = tracker_repo.get_user_meal_history(user_id)

        # 3. Candidate meals from global in-memory cache (0 Firestore reads)
        all_meals = meal_repo.get_all_meals()
        app_logger.info("[meal-plan] candidate pool: %d meals", len(all_meals))

        # 4. Fetch user profile ONCE — used for dietary filter + explanations
        _profile = {}
        try:
            _profile = user_repo.get_user_profile(user_id) or {}
        except Exception as _e:
            app_logger.warning("[meal-plan] profile fetch failed: %s", _e)

        # 5. Apply dietary filter to the full pool (boolean flags only)
        filtered_meals = apply_diet_filter(all_meals, _profile)
        app_logger.info(
            "[meal-plan] dietary filter: pool %d → %d",
            len(all_meals), len(filtered_meals)
        )

        # 5b. DEDUPLICATION + HARD VALIDATION — remove impossible/duplicate entries
        pre_clean_count = len(filtered_meals)
        filtered_meals = clean_meal_pool(filtered_meals)
        app_logger.info(
            "[meal-plan] dedup+validate: %d → %d meals (removed %d)",
            pre_clean_count, len(filtered_meals), pre_clean_count - len(filtered_meals)
        )

        # Build a fast name→source_meal lookup for explanation annotation
        _meal_lookup = {m.get("mealName", ""): m for m in all_meals}

        # TASK 2: slot keys exactly match frontend contract (all lowercase)
        slots = [
            ("breakfast", BREAKFAST_RANGE, MEAL_SPLIT_RATIOS["Breakfast"]),
            ("lunch",     LUNCH_RANGE,     MEAL_SPLIT_RATIOS["Lunch"]),
            ("snack",     SNACK_RANGE,     MEAL_SPLIT_RATIOS["Snack"]),
            ("dinner",    DINNER_RANGE,    MEAL_SPLIT_RATIOS["Dinner"]),
        ]

        # ── TASK 1.1: 3-attempt regeneration loop with strict validation ────
        MAX_RETRIES = 3
        plan = None
        last_violations = []

        for attempt in range(MAX_RETRIES):
            _plan = {
                "target_calories": target_calories,
                "target_macros": {
                    "protein": round(target_calories * 0.25 / 4),
                    "carbs":   round(target_calories * 0.45 / 4),
                    "fat":     round(target_calories * 0.30 / 9),
                },
                "breakfast": [],
                "lunch":     [],
                "snack":     [],
                "dinner":    [],
            }

            used_today = set()

            # ── Primary generation loop ─────────────────────────────────────
            for slot_name, cal_range, split_ratio in slots:
                slot_target = target_calories * split_ratio
                items = self.build_multi_item_meal(
                    slot_name=slot_name,
                    slot_target=float(slot_target),
                    candidates=filtered_meals,
                    recent_plans=recent_plans,
                    user_history=user_history,
                    used_today=used_today,
                    max_items=4,
                )
                _plan[slot_name] = items
                for i in items:
                    used_today.add(i.get("mealName", ""))

            # ── Per-slot fallback ────────────────────────────────────────────
            _NON_VEG_KWS = {"chicken", "mutton", "fish", "egg"}
            _dr = _profile.get("dietary_restrictions", {})
            _is_veg   = bool(_dr.get("is_vegetarian") or _profile.get("is_vegetarian"))
            _is_vegan = bool(_dr.get("is_vegan")      or _profile.get("is_vegan"))

            for slot_name, _, split_ratio in slots:
                if _plan[slot_name]:
                    continue

                app_logger.warning(
                    "[meal-plan] slot '%s' empty — applying fallback (attempt %d)",
                    slot_name, attempt + 1
                )
                _slot_target = target_calories * split_ratio
                _pool = [
                    m for m in filtered_meals
                    if (m.get("meal_type") or "").lower() == slot_name
                    or (m.get("category")  or "").lower() == slot_name
                ]
                if len(_pool) < 5:
                    _pool = list(filtered_meals)

                if _is_veg and _pool:
                    _veg = [
                        m for m in _pool
                        if m.get("is_vegetarian") is True
                        and not any(kw in (m.get("mealName") or "").lower() for kw in _NON_VEG_KWS)
                    ]
                    if _veg:
                        _pool = _veg

                if not _pool:
                    app_logger.error("[meal-plan] fallback: pool empty for slot '%s'", slot_name)
                    continue

                _pool.sort(key=lambda m: abs((m.get("calories") or 0) - _slot_target))
                _best = _pool[0]
                _plan[slot_name] = [{
                    "mealName": _best.get("mealName", ""),
                    "quantity": 1.0,
                    "calories": round(float(_best.get("calories") or 0), 1),
                    "protein":  round(float(_best.get("protein")  or 0), 1),
                    "carbs":    round(float(_best.get("carbs")    or 0), 1),
                    "fat":      round(float(_best.get("fat")      or 0), 1),
                }]
                app_logger.info(
                    "[meal-plan] fallback → %s: '%s' (cal=%.0f)",
                    slot_name, _best.get("mealName"), float(_best.get("calories") or 0)
                )

            # ── Emergency force-fill (all slots still empty) ─────────────────
            _slot_names = [sn for sn, _, _ in slots]
            if all(len(_plan[sn]) == 0 for sn in _slot_names):
                app_logger.error("[meal-plan] ALL SLOTS EMPTY — emergency force-fill")
                for sn, _, _ in slots:
                    if filtered_meals:
                        _em = random.choice(filtered_meals)
                        _plan[sn] = [{
                            "mealName": _em.get("mealName", "fallback"),
                            "quantity": 1.0,
                            "calories": round(float(_em.get("calories") or 0), 1),
                            "protein":  round(float(_em.get("protein")  or 0), 1),
                            "carbs":    round(float(_em.get("carbs")    or 0), 1),
                            "fat":      round(float(_em.get("fat")      or 0), 1),
                        }]

            # ── TASK 1.1: Strict dietary validation ─────────────────────────
            is_valid, violations = validate_plan(_plan, _profile)
            if is_valid:
                plan = _plan
                app_logger.info(
                    "[meal-plan] dietary validation passed on attempt %d", attempt + 1
                )
                break
            else:
                last_violations = violations
                app_logger.warning(
                    "[meal-plan] attempt %d FAILED validation (%d violations): %s",
                    attempt + 1, len(violations),
                    [(v[0], v[1]) for v in violations[:3]]
                )
        else:
            # All 3 attempts failed — log and use last attempt's plan anyway
            # (better to show a slightly wrong plan than crash the app)
            app_logger.error(
                "[meal-plan] ALL %d ATTEMPTS FAILED validation — using last plan. "
                "Violations: %s",
                MAX_RETRIES, last_violations
            )
            plan = _plan

        # ── Macro optimisation pass (Tasks 1-6) ──────────────────────────────
        # Returns a 4-tuple: (plan, macro_deviation, optimization_score, score_label)
        macro_targets = build_macro_targets(target_calories)
        plan, macro_deviation, optimization_score, score_label = optimize_plan(
            plan, macro_targets, filtered_meals
        )

        # ── ML Daily Rater (Phase 4) ──────────────────────────────────────────
        # Lazy import keeps startup fast; predict_score returns -1 on failure.
        try:
            from ml.daily_rater import predict_score, interpret_score as _interpret
            _ml_raw = predict_score(macro_deviation)
            if _ml_raw < 0:   # model unavailable — graceful fallback
                ml_score       = optimization_score
                ml_score_label = score_label
            else:
                ml_score       = _ml_raw
                ml_score_label = _interpret(ml_score)
        except Exception as _ml_exc:
            app_logger.warning("[meal-plan] ML rater unavailable: %s", _ml_exc)
            ml_score       = optimization_score
            ml_score_label = score_label

        # ── Post-optimization dietary validation with retry ────────────────────
        _pre_opt_plan   = plan
        _pre_opt_dev    = macro_deviation
        _pre_opt_score  = optimization_score
        _pre_opt_label  = score_label
        OPT_RETRIES = 2
        for _opt_attempt in range(OPT_RETRIES + 1):
            _opt_valid, _opt_violations = validate_plan(plan, _profile)
            if _opt_valid:
                if _opt_attempt > 0:
                    app_logger.info(
                        "[meal-plan] Post-opt validation passed on retry %d", _opt_attempt
                    )
                else:
                    app_logger.info("[meal-plan] Post-optimization dietary validation passed")
                break
            app_logger.warning(
                "[meal-plan] Post-opt FAILED attempt %d/%d (%d violations): %s",
                _opt_attempt + 1, OPT_RETRIES + 1,
                len(_opt_violations),
                [(v[0], v[1]) for v in _opt_violations[:3]],
            )
            if _opt_attempt < OPT_RETRIES:
                plan, macro_deviation, optimization_score, score_label = optimize_plan(
                    _pre_opt_plan, macro_targets, filtered_meals
                )
            else:
                app_logger.error(
                    "[meal-plan] All post-opt retries failed — reverting to pre-opt plan"
                )
                plan               = _pre_opt_plan
                macro_deviation    = _pre_opt_dev
                optimization_score = _pre_opt_score
                score_label        = _pre_opt_label

        # Embed analytics fields in plan (TASK 3, 4, 5 + Phase 4 ML)
        plan["macro_deviation"]    = macro_deviation
        plan["optimization_score"] = optimization_score
        plan["score_label"]        = score_label
        plan["ml_score"]           = ml_score
        plan["ml_score_label"]     = ml_score_label

        # ── TASK 2.3: Annotate every item with explanation + float macros ───
        for slot_name, _, _ in slots:
            annotated = []
            for item in plan.get(slot_name, []):
                source = _meal_lookup.get(item.get("mealName", ""), item)
                annotated.append(annotate_plan_item(item, source, _profile))
            plan[slot_name] = annotated

        # ── Total calories (after annotation, post-fallback) ─────────────────
        total_gen_cals = sum(
            float(i.get("calories") or 0)
            for sn, _, _ in slots
            for i in plan[sn]
        )
        plan["total_calories"] = round(total_gen_cals)

        app_logger.info(
            "[meal-plan] FINAL PLAN: B→%d L→%d S→%d D→%d total_cal=%d",
            len(plan["breakfast"]), len(plan["lunch"]),
            len(plan["snack"]),     len(plan["dinner"]),
            plan["total_calories"],
        )

        # ── Save plan to Firestore ────────────────────────────────────────────
        tracker_repo.save_plan({
            "userId": user_id,
            "date":   date_str,
            **plan,
        })

        # ── TASK 4: Persist macro deviation to Daily Ratings (analytics) ─────
        try:
            from config.config import COL_DAILY_RATINGS
            from firebase_admin import firestore as _fs
            _rating_doc = {
                "userId":             user_id,
                "date":               date_str,
                "macro_deviation":    macro_deviation,
                "optimization_score": optimization_score,
                "score_label":        score_label,
                "ml_score":           ml_score,
                "ml_score_label":     ml_score_label,
                "target_calories":    target_calories,
                "created_at":         _fs.SERVER_TIMESTAMP,
            }
            tracker_repo.db.collection(COL_DAILY_RATINGS).document(
                f"{user_id}_{date_str}"
            ).set(_rating_doc)
            app_logger.info(
                "[meal-plan] Daily rating saved: score=%.4f dev=%s",
                optimization_score, macro_deviation
            )
        except Exception as _re:
            app_logger.warning("[meal-plan] Failed to save daily rating: %s", _re)

        return plan, ""



    # ──────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _validate_diet_plan(plan, is_veg: bool, is_vegan: bool):
        """
        Post-generation dietary validation.
        Logs an error for every item that violates the user's dietary flag.
        Does NOT raise — preserving plan delivery is more important than crashing.
        """
        _NON_VEG_KWS = {"chicken", "mutton", "fish", "egg"}
        violations = []
        for slot in ("breakfast", "lunch", "snack", "dinner"):
            for item in plan.get(slot, []):
                if is_vegan and item.get("is_vegan") is not True:
                    violations.append((slot, item.get("mealName"), "not is_vegan"))
                elif is_veg:
                    if item.get("is_vegetarian") is not True:
                        violations.append((slot, item.get("mealName"), "not is_vegetarian"))
                    elif any(kw in (item.get("mealName") or "").lower() for kw in _NON_VEG_KWS):
                        violations.append((slot, item.get("mealName"), "non-veg keyword in name"))
        if violations:
            from utils.logger import app_logger as _log
            for slot, name, reason in violations:
                _log.error(
                    "[diet-validate] VIOLATION in %s: '%s' — %s",
                    slot, name, reason
                )
        else:
            from utils.logger import app_logger as _log
            _log.info("[diet-validate] All meals pass dietary check (veg=%s vegan=%s)",
                      is_veg, is_vegan)

    def get_user_targets(self, user_id, date_str):
        try:
            target_doc = user_repo.get_daily_target(user_id, date_str)
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return 2000
            raise
        if target_doc:
            return target_doc.get("calories")
        try:
            profile = user_repo.get_user_profile(user_id)
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                return 2000
            raise
        if not profile:
             return 2000 # default fallback
        # In a fully integrated map, call utils here
        return 2000 

    def fetch_candidate_meals(self):
        # We start by using the meal combos
        combos = meal_repo.get_meal_combos()
        if not combos:
            # fallback to ordinary meals if combos dataset is empty during dev
            combos = meal_repo.get_all_meals()
        return combos

    # ---------------------------------------------------------------------
    # Multi-item meal generation (2–4 foods)
    # ---------------------------------------------------------------------
    def build_multi_item_meal(
        self,
        slot_name,
        slot_target,
        candidates,
        recent_plans,
        user_history,
        used_today,
        max_items=4,
    ):
        """
        Build a meal as a list of food items (2–4) that roughly matches slot_target.
        Uses:
          - category filtering (heuristics + existing meal fields)
          - greedy calorie fill
          - portion scaling for staples
          - no duplicates in the same day
        """
        slot_target = float(slot_target or 0)
        if slot_target <= 0:
            return []

        pool = self.filter_by_slot_category(slot_name, candidates)
        pool = [m for m in pool if (m.get("mealName") or "") and (m.get("calories") or 0) > 0]

        # As a fallback, if category filtering over-prunes.
        if len(pool) < 10:
            pool = [m for m in candidates if (m.get("mealName") or "") and (m.get("calories") or 0) > 0]

        # Sort by preference score / variety penalty (reuse existing signals)
        def score(m):
            name = m.get("mealName", "")
            pref = self.calculate_preference_score(name, user_history)
            rep_pen = self.apply_repetition_penalty(name, recent_plans)
            div_pen = self.apply_diversity_penalty(name, recent_plans)
            # We want higher preference and lower penalties
            return pref - rep_pen - div_pen

        pool.sort(key=score, reverse=True)

        items = []
        meal_cals = 0.0
        min_items = 2

        # Greedy loop: keep adding until we're close enough or hit max_items
        while len(items) < max_items and meal_cals < (slot_target - CALORIE_TOLERANCE):
            remaining = slot_target - meal_cals

            candidate = self.pick_food_for_remaining(pool, slot_name, remaining, used_today)
            if not candidate:
                break

            portioned = self.portion_to_fit(candidate, remaining)
            if not portioned:
                used_today.add(candidate.get("mealName", ""))
                continue

            items.append(portioned)
            used_today.add(portioned.get("mealName", ""))
            meal_cals += float(portioned.get("calories") or 0)

        # Ensure at least 2 items if possible
        if len(items) < min_items:
            attempts = 0
            while len(items) < min_items and attempts < 8:
                attempts += 1
                remaining = max(50.0, slot_target - meal_cals)
                candidate = self.pick_food_for_remaining(pool, slot_name, remaining, used_today)
                if not candidate:
                    break
                portioned = self.portion_to_fit(candidate, remaining)
                if not portioned:
                    used_today.add(candidate.get("mealName", ""))
                    continue
                items.append(portioned)
                used_today.add(portioned.get("mealName", ""))
                meal_cals += float(portioned.get("calories") or 0)

        # If we overshot a lot and we have more than 1 item, drop the last one
        if len(items) > 1 and meal_cals > (slot_target + CALORIE_TOLERANCE):
            last = items[-1]
            if (meal_cals - float(last.get("calories") or 0)) >= (slot_target - CALORIE_TOLERANCE):
                items.pop()

        return items

    def filter_by_slot_category(self, slot_name, candidates):
        slot = (slot_name or "").lower()
        out = []
        for m in candidates:
            name = (m.get("mealName") or "").strip()
            if not name:
                continue

            # Prefer any explicit backend category hints
            raw_cat = m.get("category")
            raw_types = m.get("meal_type")
            type_tokens = []
            if isinstance(raw_cat, str):
                type_tokens.append(raw_cat.lower())
            if isinstance(raw_types, list):
                type_tokens.extend([str(t).lower() for t in raw_types])

            # If a doc already declares its meal slot, use that.
            if slot in type_tokens:
                out.append(m)
                continue

            lowered = name.lower()
            if slot == "breakfast":
                if any(k in lowered for k in self.BREAKFAST_KEYWORDS):
                    out.append(m)
            elif slot == "snack":
                if any(k in lowered for k in self.SNACK_KEYWORDS):
                    out.append(m)
            elif slot in ("lunch", "dinner"):
                if any(k in lowered for k in self.LUNCH_DINNER_KEYWORDS):
                    out.append(m)
            else:
                out.append(m)
        return out

    def pick_food_for_remaining(self, pool, slot_name, remaining, used_today):
        if remaining <= 0:
            return None

        # Prefer foods not already used today
        available = [m for m in pool if m.get("mealName") not in used_today]
        if not available:
            return None

        # Heuristic: choose foods that aren't too large relative to remaining.
        # If remaining is big, allow larger items too.
        filtered = []
        for m in available:
            cal = float(m.get("calories") or 0)
            if cal <= 0:
                continue
            if cal <= remaining + 80:
                filtered.append(m)

        if not filtered:
            filtered = available

        # Take from the top (preference-sorted) but add randomness
        top_n = filtered[:25] if len(filtered) > 25 else filtered
        return random.choice(top_n) if top_n else None

    def portion_to_fit(self, meal, remaining):
        """
        Portion scaling:
          - If remaining calories suggest multiple units, increase quantity.
          - Allow 0.5 increments (0.5..4.0) to support small "side" additions.
        """
        base_cal = float(meal.get("calories") or 0)
        if base_cal <= 0:
            return None

        # Compute quantity to best fill remaining.
        # Use 0.5 steps so we can add small sides without huge overshoot.
        raw_qty = remaining / base_cal
        # Round to nearest 0.5
        qty = round(raw_qty * 2) / 2
        qty = max(0.5, min(qty, 4.0))

        # If base is already close, keep 1
        if abs(base_cal - remaining) <= 80:
            qty = 1.0

        item = {
            "mealName": meal.get("mealName"),
            "quantity": qty,
            "calories": round(base_cal * qty, 1),
            "protein": round(float(meal.get("protein") or 0) * qty, 1),
            "carbs": round(float(meal.get("carbs") or 0) * qty, 1),
            "fat": round(float(meal.get("fat") or 0) * qty, 1),
        }
        return item

    def select_best_meal(self, candidates, meal_type, target_cal, cal_range, recent_plans, user_history, used_today):
        best_candidate = None
        best_score = -9999
        
        # Base validation boundaries (using Tolerance)
        min_cal = target_cal - CALORIE_TOLERANCE
        max_cal = target_cal + CALORIE_TOLERANCE

        for meal in candidates:
             name = meal.get("mealName", "")
             
             # Prevent double eating same meal today
             if name in used_today: continue
             
             # Check valid meal types (allow breakfast for lunch)
             valid_types = [t.lower() for t in meal.get("meal_type", [])]
             if not valid_types: 
                 valid_types = [t.lower() for t in meal.get("category", ["lunch", "dinner", "breakfast"])]
             
             if meal_type.lower() not in valid_types:
                  if meal_type.lower() == "lunch" and ("breakfast" in valid_types or meal.get("allow_for_lunch")):
                      pass
                  else:
                      continue

             # Calculate Scoring
             nut_score = self.calculate_nutrition_score(meal, target_cal)
             rep_pen = self.apply_repetition_penalty(name, recent_plans)
             div_pen = self.apply_diversity_penalty(name, recent_plans)
             pref_score = self.calculate_preference_score(name, user_history)
             
             score = nut_score + pref_score - rep_pen - div_pen
             
             if score > best_score:
                  best_score = score
                  best_candidate = meal

        if best_candidate:
             app_logger.info(f"Selected meal: {best_candidate.get('mealName')} with score {best_score}")
        return best_candidate

    def calculate_nutrition_score(self, meal, target_cal):
         diff = abs((meal.get("calories") or 0) - target_cal)
         # Higher score for closer match
         return max(0, 100 - diff)

    def apply_repetition_penalty(self, meal_name, recent_plans):
        today_str = get_today_str()
        penalty = 0
        if not isinstance(recent_plans, list):
            return penalty
        for p in recent_plans:
            if not isinstance(p, dict):
                continue
            for slot in ["breakfast", "lunch", "dinner", "snack"]:
                slot_data = p.get(slot)
                if not slot_data:
                    continue
                # Firestore saves slots as plain lists; legacy shape may wrap in {"items": [...]}
                if isinstance(slot_data, list):
                    items = slot_data
                elif isinstance(slot_data, dict):
                    items = slot_data.get("items") or []
                else:
                    continue
                for item in items:
                    if isinstance(item, dict) and item.get("mealName") == meal_name:
                        days_diff = get_days_difference(today_str, p.get("date"))
                        if days_diff == 1:
                            return PENALTY_YESTERDAY
                        elif days_diff <= 3:
                            return max(penalty, PENALTY_LAST_3_DAYS)
        return penalty

    def apply_diversity_penalty(self, meal_name, recent_plans):
        freq = 0
        if not isinstance(recent_plans, list):
            return freq
        for p in recent_plans:
            if not isinstance(p, dict):
                continue
            for slot in ["breakfast", "lunch", "dinner", "snack"]:
                slot_data = p.get(slot)
                if not slot_data:
                    continue
                if isinstance(slot_data, list):
                    items = slot_data
                elif isinstance(slot_data, dict):
                    items = slot_data.get("items") or []
                else:
                    continue
                for item in items:
                    if isinstance(item, dict) and item.get("mealName") == meal_name:
                        freq += 1
        if freq >= 3:
            return PENALTY_WEEK_FREQ_3
        elif freq == 2:
            return PENALTY_WEEK_FREQ_2
        return 0

    def calculate_preference_score(self, meal_name, user_history):
        if not isinstance(user_history, dict):
            return 0
        history = user_history.get(meal_name)
        if isinstance(history, dict):
            return history.get("count", 0) * PREFERENCE_MULTIPLIER
        return 0

    def adjust_portion_size(self, meal, slot_target):
         # Scale meal calories to slot_target if deviation is large
         original_cal = meal.get("calories") or 0
         if original_cal == 0: return meal
         
         safe_meal = meal.copy()
         ratio = slot_target / original_cal
         
         # Bound the scaling realistically (.5 to 2.0)
         ratio = min(max(ratio, 0.5), 2.0)
         
         for macro in ["calories", "protein", "carbs", "fat"]:
              val = safe_meal.get(macro)
              if val is not None:
                   safe_meal[macro] = round((val or 0) * ratio, 1)
                   
         safe_meal["quantity"] = round((safe_meal.get("quantity") or 1) * ratio, 2)
         return safe_meal

meal_generator_service = MealGeneratorService()
