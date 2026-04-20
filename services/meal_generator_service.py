# services/meal_generator_service.py
import random
from utils.logger import app_logger
from utils.date_utils import get_days_difference, get_today_str
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
        
        # 3. Fetch candidate meal combos
        # We must generate multi-item meals, so we prefer single foods dataset.
        all_meals = meal_repo.get_all_meals()
        app_logger.info(f"Candidate meals count: {len(all_meals)}")
        
        # 4 & 5. Filter Candidates (dietary & conditions)
        # TODO: integrate specific profile filtering logic if present in user doc
        filtered_meals = all_meals  # Default pass-through for now
        
        plan = {
            "target_calories": target_calories,
            "target_macros": { # Hardcoded scale of target for structure
                "protein": round(target_calories * 0.25 / 4),
                "carbs": round(target_calories * 0.45 / 4),
                "fat": round(target_calories * 0.30 / 9)
            }
        }
        
        total_gen_cals = 0
        used_today = set()

        # Generate each slot
        slots = [
            ("breakfast", BREAKFAST_RANGE, MEAL_SPLIT_RATIOS["Breakfast"]),
            ("lunch", LUNCH_RANGE, MEAL_SPLIT_RATIOS["Lunch"]),
            ("snack", SNACK_RANGE, MEAL_SPLIT_RATIOS["Snack"]),
            ("dinner", DINNER_RANGE, MEAL_SPLIT_RATIOS["Dinner"])
        ]
        
        for slot_name, cal_range, split_ratio in slots:
            # target specific to slot
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

            # Sum this meal
            meal_cals = sum(float(i.get("calories") or 0) for i in items)
            total_gen_cals += meal_cals

            # Step 6: API response should return arrays of foods (per prompt)
            plan[slot_name] = items
                 
        plan["total_calories"] = total_gen_cals

        # ── TASKS 1-4: Per-slot fallback ─────────────────────────────────────
        # TASK 1: check each slot for an empty list (not relying on solve_meal)
        # TASK 2: respect vegetarian flag from user profile
        # TASK 3: sort by calorie proximity; mutate plan[slot] in-place
        # TASK 4: log every applied fallback

        # Determine vegetarian preference from user profile (best-effort)
        _is_veg = False
        try:
            from repositories.user_repository import user_repo as _ur
            _profile = _ur.get_user_profile(user_id)
            _is_veg = bool(_profile and _profile.get("is_vegetarian"))
        except Exception:
            pass

        _slot_split = {
            "breakfast": MEAL_SPLIT_RATIOS["Breakfast"],
            "lunch":     MEAL_SPLIT_RATIOS["Lunch"],
            "snack":     MEAL_SPLIT_RATIOS["Snack"],
            "dinner":    MEAL_SPLIT_RATIOS["Dinner"],
        }
        _NON_VEG_KWS = {"chicken", "mutton", "fish", "egg"}

        for _slot_name, _, _split_ratio in slots:
            # TASK 1: detect empty slot
            if plan.get(_slot_name):
                continue

            app_logger.warning(
                "[meal-plan] slot '%s' is empty after generation — applying fallback",
                _slot_name
            )

            # TASK 2: build a type-filtered pool
            _slot_target = target_calories * _split_ratio
            _pool = [
                m for m in filtered_meals
                if (m.get("meal_type") or "").lower() == _slot_name
                or (m.get("category") or "").lower() == _slot_name
            ]

            # Widen to full candidate set if type-pool is too small
            if len(_pool) < 5:
                _pool = list(filtered_meals)

            # TASK 2: veg filter
            if _is_veg and _pool:
                _veg_pool = [
                    m for m in _pool
                    if m.get("is_vegetarian") is True
                    and not any(
                        kw in (m.get("mealName") or "").lower()
                        for kw in _NON_VEG_KWS
                    )
                ]
                if _veg_pool:
                    _pool = _veg_pool

            if not _pool:
                app_logger.error(
                    "[meal-plan] fallback: no candidates at all for slot '%s'", _slot_name
                )
                continue

            # TASK 3: pick by calorie proximity, no random
            _pool_sorted = sorted(
                _pool,
                key=lambda m: abs((m.get("calories") or 0) - _slot_target)
            )
            _best = _pool_sorted[0]
            _fb_item = {
                "mealName": _best.get("mealName", ""),
                "quantity": 1.0,
                "calories": round(float(_best.get("calories") or 0), 1),
                "protein":  round(float(_best.get("protein")  or 0), 1),
                "carbs":    round(float(_best.get("carbs")    or 0), 1),
                "fat":      round(float(_best.get("fat")      or 0), 1),
            }

            # TASK 3: mutate in-place
            plan[_slot_name] = [_fb_item]
            total_gen_cals += _fb_item["calories"]

            # TASK 4: log the applied fallback
            app_logger.info(
                "[meal-plan] slot fallback applied → %s: '%s' "
                "(cal=%.0f, target≈%.0f, pool=%d, veg=%s)",
                _slot_name, _fb_item["mealName"], _fb_item["calories"],
                _slot_target, len(_pool), _is_veg
            )

        # Update total after any fallbacks were applied
        plan["total_calories"] = round(total_gen_cals)

        # TASK 5: Final safety — assert at least one slot has items
        _slot_names = [s for s, _, _ in slots]
        _any_filled = any(bool(plan.get(s)) for s in _slot_names)

        if not _any_filled:
            app_logger.error(
                "[meal-plan] all slots empty after fallback — forcing 1 random meal per slot"
            )
            import random as _rnd
            for _slot_name, _, _split_ratio in slots:
                if filtered_meals:
                    _emergency = _rnd.choice(filtered_meals)
                    plan[_slot_name] = [{
                        "mealName": _emergency.get("mealName", "fallback"),
                        "quantity": 1.0,
                        "calories": round(float(_emergency.get("calories") or 0), 1),
                        "protein":  round(float(_emergency.get("protein")  or 0), 1),
                        "carbs":    round(float(_emergency.get("carbs")    or 0), 1),
                        "fat":      round(float(_emergency.get("fat")      or 0), 1),
                    }]
                    app_logger.info(
                        "[meal-plan] emergency fill: %s → '%s'",
                        _slot_name, _emergency.get("mealName")
                    )

        # Save to DB
        tracker_repo.save_plan({
            # IMPORTANT: repository queries use "userId"
            "userId": user_id,
            "date": date_str,
            **plan
        })
        
        return plan, ""


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
