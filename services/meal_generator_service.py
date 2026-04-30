# services/meal_generator_service.py
from utils.logger import app_logger
from repositories.user_repository import user_repo
from repositories.tracker_repository import tracker_repo
from ai.plan_selector import PlanSelector
from ai.smart_swap_knn import SmartSwapKNN, get_knn_model
from repositories.meal_repository import meal_repo
import copy

class MealGeneratorService:
    
    def _recompute_totals(self, plan):
        """STEP 1: Recompute totals from all meal items dynamically."""
        total_calories = 0.0
        total_protein = 0.0
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            for item in plan.get("meals", {}).get(slot, []):
                total_calories += float(item.get("calories", 0))
                total_protein += float(item.get("protein", 0))
        
        plan["actual_calories"] = round(total_calories, 1)
        plan["actual_protein"] = round(total_protein, 1)
        plan["finalCalories"] = plan["actual_calories"]
        plan["finalProtein"] = plan["actual_protein"]
        return plan

    def generate_daily_plan(self, user_id, date_str):
        app_logger.info("Generating meal plan for user %s using PlanSelector", user_id)

        # 1. Fetch user profile
        try:
            profile = user_repo.get_user_profile(user_id) or {}
            profile["userId"] = user_id
        except Exception as _e:
            app_logger.warning("[meal-plan] profile fetch failed: %s", _e)
            return None, "Error fetching profile"

        # 2. Use PlanSelector to pick the best whole-day plan
        selector = PlanSelector(tracker_repo.db)
        best_plan_raw = selector.select_plan(profile)

        if not best_plan_raw:
            app_logger.error("[meal-plan] PlanSelector found no valid plans.")
            return None, "No suitable meal plan found."
            
        best_plan = copy.deepcopy(best_plan_raw)

        user_target_calories = best_plan.get("user_target_calories", 2000)
        target_protein = best_plan.get("user_target_protein", 0)

        app_logger.info("[meal-plan] Selected Plan ID: %s (Score based on %s target cals)", 
                        best_plan.get("planId"), user_target_calories)

        # 3. Scale Plan Quantities
        all_meals = meal_repo.get_all_meals()
        scaled_plan = self.scale_plan(best_plan, user_target_calories, all_meals)
        scaled_plan = self._recompute_totals(scaled_plan)
        before_cal = scaled_plan["actual_calories"]
        before_prot = scaled_plan["actual_protein"]

        # 4. Protein Correction Layer
        corrected_plan = self.fix_protein(scaled_plan, all_meals, profile, target_protein)
        corrected_plan = self._recompute_totals(corrected_plan)

        # 5. Final Validation Layer (Dietary Strictness)
        validated_plan = self.apply_knn_validation(corrected_plan, all_meals, profile)
        validated_plan = self._recompute_totals(validated_plan)

        # 6. Micro Adjustments (Moved to end)
        adjusted_plan = self.micro_adjust_plan(validated_plan, user_target_calories)
        adjusted_plan = self._recompute_totals(adjusted_plan)

        # 7. Final Protein Correction (If still low after calorie adjustments)
        final_plan = self.final_protein_check(adjusted_plan, all_meals, profile, target_protein, user_target_calories)
        final_plan = self._recompute_totals(final_plan)

        # 8. STEP 1 & 2: Final Correction Loop
        for i in range(3):
            final_plan = self._recompute_totals(final_plan)
            after_cal = final_plan["actual_calories"]
            after_prot = final_plan["actual_protein"]

            cal_diff = abs(after_cal - user_target_calories) / user_target_calories if user_target_calories > 0 else 0
            prot_diff = abs(after_prot - target_protein) / target_protein if target_protein > 0 else 0

            if cal_diff <= 0.05 and (target_protein == 0 or prot_diff <= 0.10):
                break

            # STEP 4: Priority Rule 1 (Calorie Accuracy)
            if cal_diff > 0.05:
                if after_cal > user_target_calories:
                    prev_cal = final_plan["actual_calories"]
                    final_plan = self._adjust_item_qty(final_plan, ["rice", "chawal"], -0.5)
                    if final_plan["actual_calories"] == prev_cal:
                        final_plan = self._adjust_item_qty(final_plan, ["roti", "chapati", "naan", "paratha"], -1.0)
                else:
                    prev_cal = final_plan["actual_calories"]
                    final_plan = self._adjust_item_qty(final_plan, ["rice", "chawal"], 0.5)
                    if final_plan["actual_calories"] == prev_cal:
                        final_plan = self._adjust_item_qty(final_plan, ["dal", "sabzi"], 0.5)
            
            # STEP 4: Priority Rule 2 (Protein Accuracy)
            final_plan = self._recompute_totals(final_plan)
            if target_protein > 0:
                new_prot_diff = abs(final_plan["actual_protein"] - target_protein) / target_protein
                if new_prot_diff > 0.10 and target_protein > final_plan["actual_protein"]:
                    final_plan = self.final_protein_check(final_plan, all_meals, profile, target_protein, user_target_calories)

        # 9. STEP 3: Final Check & Logging
        final_plan = self._recompute_totals(final_plan)
        after_cal = final_plan["actual_calories"]
        after_prot = final_plan["actual_protein"]

        app_logger.info("[meal-plan] STEP 6: DEBUG LOGGING")
        app_logger.info(f"[meal-plan] before_calories={before_cal}, after_calories={after_cal}")
        app_logger.info(f"[meal-plan] before_protein={before_prot}, after_protein={after_prot}")

        # --- STEP 1: FINAL DIET SAFETY GUARANTEE (CRITICAL) ---
        final_plan = self.apply_knn_validation(final_plan, all_meals, profile)
        
        # --- STEP 2: FINAL MACRO CONSISTENCY ---
        final_plan = self._recompute_totals(final_plan)
        after_cal = final_plan["actual_calories"]
        after_prot = final_plan["actual_protein"]

        cal_diff = abs(after_cal - user_target_calories) / user_target_calories if user_target_calories > 0 else 0
        prot_diff = abs(after_prot - target_protein) / target_protein if target_protein > 0 else 0

        if cal_diff > 0.05 or prot_diff > 0.10:
            app_logger.warning(f"[meal-plan] STEP 3: Final plan still out of bounds after loop. Cal error: {cal_diff:.1%}, Prot error: {prot_diff:.1%}")

        # --- NEW CODE: Annotate items (explanations, servingSize) ---
        from utils.diet_utils import annotate_plan_item
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            annotated_slot = []
            for item in final_plan.get("meals", {}).get(slot, []):
                name = item.get("mealName", "").lower()
                full_meal = next((m for m in all_meals if m.get("mealName", "").lower() == name), None)
                if not full_meal:
                    full_meal = next((m for m in all_meals if name in m.get("mealName", "").lower()), None)
                annotated = annotate_plan_item(item, full_meal if full_meal else item, profile)
                annotated_slot.append(annotated)
            final_plan.setdefault("meals", {})[slot] = annotated_slot

        # Save plan to Firestore under user's logs
        user_plan = {
            "userId": user_id,
            "date":   date_str,
            "target_calories": user_target_calories,
            "target_macros": {
                "protein": target_protein
            },
            "actual_calories": after_cal,
            "actual_protein": after_prot,
            "finalCalories": after_cal,
            "finalProtein": after_prot,
            "breakfast": final_plan.get("meals", {}).get("breakfast", []),
            "lunch":     final_plan.get("meals", {}).get("lunch", []),
            "snack":     final_plan.get("meals", {}).get("snack", []),
            "dinner":    final_plan.get("meals", {}).get("dinner", []),
            "source_plan_id": final_plan.get("planId"),
            "source_plan_name": final_plan.get("planName")
        }

        # --- STEP 3: RESPONSE INTEGRITY FIX ---
        app_logger.info(f"FINAL PLAN SENT: {user_plan}")

        tracker_repo.save_plan(user_plan)
        return user_plan, ""

    def scale_plan(self, plan, user_target_calories, all_meals):
        plan_cals = float(plan.get("targetCalories") or 2000)
        ratio = user_target_calories / plan_cals if plan_cals > 0 else 1.0
        ratio = max(0.7, min(ratio, 1.5))
        
        meals = plan.get("meals", {})
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            items = meals.get(slot, [])
            for item in items:
                name = item.get("mealName", "").lower()
                old_qty = float(item.get("quantity", 1.0))
                
                # Populate missing base macros using all_meals
                if not item.get("calories"):
                    full_meal = next((m for m in all_meals if m.get("mealName", "").lower() == name), None)
                    if not full_meal:
                        # Fallback to partial match if exact match fails
                        full_meal = next((m for m in all_meals if name in m.get("mealName", "").lower()), None)
                        
                    if full_meal:
                        item["calories"] = float(full_meal.get("calories", 0)) * old_qty
                        item["protein"] = float(full_meal.get("protein", 0)) * old_qty
                        item["carbs"] = float(full_meal.get("carbs", 0)) * old_qty
                        item["fat"] = float(full_meal.get("fat", 0)) * old_qty

                raw_new_qty = old_qty * ratio
                new_qty = raw_new_qty
                
                if any(k in name for k in ["roti", "chapati", "paratha", "naan", "bread"]):
                    new_qty = round(raw_new_qty)
                    new_qty = max(1.0, new_qty)
                elif any(k in name for k in ["rice", "chawal", "dal", "sabzi", "paneer", "chicken", "rajma", "chole", "oats", "poha", "upma"]):
                    new_qty = round(raw_new_qty * 2) / 2
                    new_qty = max(0.5, new_qty)
                elif "whey" in name or "protein shake" in name:
                    new_qty = round(raw_new_qty * 2) / 2
                    new_qty = min(1.5, max(0.5, new_qty))
                elif "egg" in name:
                    new_qty = round(raw_new_qty)
                    new_qty = min(4.0, max(1.0, new_qty))
                elif any(k in name for k in ["milk", "tea", "coffee", "lassi", "chaas", "juice", "beverage", "buttermilk"]):
                    diff = raw_new_qty - old_qty
                    if diff > 0.25:
                        new_qty = old_qty + 0.5
                    elif diff < -0.25:
                        new_qty = old_qty - 0.5
                    else:
                        new_qty = old_qty
                    new_qty = max(0.5, new_qty)
                else:
                    new_qty = round(raw_new_qty * 2) / 2
                    new_qty = max(1.0, new_qty)
                
                qty_ratio = new_qty / old_qty if old_qty > 0 else 1.0
                
                item["quantity"] = new_qty
                item["calories"] = round(float(item.get("calories", 0)) * qty_ratio, 1)
                item["protein"] = round(float(item.get("protein", 0)) * qty_ratio, 1)
                item["carbs"] = round(float(item.get("carbs", 0)) * qty_ratio, 1)
                item["fat"] = round(float(item.get("fat", 0)) * qty_ratio, 1)

        return plan

    def micro_adjust_plan(self, plan, user_target_calories):
        """STEP 3: Final Micro Adjustment (moved to end)."""
        difference = user_target_calories - plan["actual_calories"]
        
        while abs(difference) > user_target_calories * 0.05: # Loop until within 5%
            made_adjustment = False
            
            for keyword, step, max_limit in [(["rice", "chawal"], 0.5, 2.0), 
                                             (["roti", "chapati", "naan", "paratha"], 1.0, 4.0), 
                                             (["dal"], 0.5, 2.0)]:
                for slot in ["breakfast", "lunch", "snack", "dinner"]:
                    items = plan.get("meals", {}).get(slot, [])
                    for item in items:
                        name = item.get("mealName", "").lower()
                        if any(k in name for k in keyword):
                            old_qty = item["quantity"]
                            
                            if difference > 0:
                                new_qty = old_qty + step
                            else:
                                new_qty = old_qty - step
                                
                            if new_qty < 0.5 or new_qty > max_limit:
                                continue
                                
                            base_cal = float(item["calories"]) / old_qty if old_qty > 0 else 0
                            base_prot = float(item["protein"]) / old_qty if old_qty > 0 else 0
                            base_carbs = float(item["carbs"]) / old_qty if old_qty > 0 else 0
                            base_fat = float(item["fat"]) / old_qty if old_qty > 0 else 0
                            
                            cal_change = (base_cal * new_qty) - item["calories"]
                            
                            # Do not overshoot in the opposite direction
                            if difference > 0 and cal_change > difference + 20: continue
                            if difference < 0 and cal_change < difference - 20: continue
                            
                            item["quantity"] = new_qty
                            item["calories"] = round(base_cal * new_qty, 1)
                            item["protein"] = round(base_prot * new_qty, 1)
                            item["carbs"] = round(base_carbs * new_qty, 1)
                            item["fat"] = round(base_fat * new_qty, 1)
                            
                            difference -= cal_change
                            made_adjustment = True
                            break
                    if made_adjustment: break
                if made_adjustment: break
                
            if not made_adjustment:
                # Can't fix further with these constraints
                break

        return plan

    def _adjust_item_qty(self, plan, keywords, step):
        """Helper to increment/decrement a specific item matching the keywords."""
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            items = plan.get("meals", {}).get(slot, [])
            for item in items:
                name = item.get("mealName", "").lower()
                if any(k in name for k in keywords):
                    old_qty = item["quantity"]
                    new_qty = old_qty + step
                    
                    if new_qty < 0.5 or new_qty > 4.0:
                        continue
                        
                    base_cal = float(item["calories"]) / old_qty if old_qty > 0 else 0
                    base_prot = float(item["protein"]) / old_qty if old_qty > 0 else 0
                    base_carbs = float(item["carbs"]) / old_qty if old_qty > 0 else 0
                    base_fat = float(item["fat"]) / old_qty if old_qty > 0 else 0
                    
                    item["quantity"] = new_qty
                    item["calories"] = round(base_cal * new_qty, 1)
                    item["protein"] = round(base_prot * new_qty, 1)
                    item["carbs"] = round(base_carbs * new_qty, 1)
                    item["fat"] = round(base_fat * new_qty, 1)
                    
                    return self._recompute_totals(plan)
        return plan

    def fix_protein(self, plan, meals_db, user, target_protein):
        current_protein = plan.get("actual_protein", 0)
        deficit = target_protein - current_protein
        if deficit <= 5:
            return plan

        is_vegan = bool(user.get("is_vegan", False))
        is_veg = bool(user.get("is_vegetarian", False))

        # Helper to get high protein candidates
        high_protein_candidates = []
        for meal in meals_db:
            if not meal.get("is_high_protein"): continue
            if is_vegan and not meal.get("is_vegan"): continue
            if is_veg and not (meal.get("is_vegetarian") or meal.get("is_vegan")): continue
            high_protein_candidates.append(meal)

        def density(m):
            cals = float(m.get("calories") or 1)
            if cals <= 0: cals = 1
            prot = float(m.get("protein") or 0)
            return prot / cals

        high_protein_candidates.sort(key=density, reverse=True)

        meal_counts = {}
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            for item in plan.get("meals", {}).get(slot, []):
                name = item.get("mealName", "").lower()
                meal_counts[name] = meal_counts.get(name, 0) + 1

        target_calories = plan.get("targetCalories", 2000)
        if "user_target_calories" in plan:
             target_calories = plan["user_target_calories"]
        max_cals = target_calories * 1.10

        # STEP 1: PRIORITY SWAPS
        swaps = 0
        low_protein_items = []
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            items = plan.get("meals", {}).get(slot, [])
            for idx, item in enumerate(items):
                prot = float(item.get("protein", 0))
                if prot < 8:
                    low_protein_items.append({
                        "slot": slot,
                        "index": idx,
                        "item": item,
                        "protein": prot
                    })
        
        low_protein_items.sort(key=lambda x: x["protein"])

        for lp in low_protein_items:
            if swaps >= 5 or current_protein >= target_protein - 5:
                break
                
            slot = lp["slot"]
            old_item = lp["item"]
            old_cal = float(old_item.get("calories", 0))
            old_prot = float(old_item.get("protein", 0))

            candidates = []
            for meal in high_protein_candidates:
                valid_types = [t.lower() for t in meal.get("validMealTypes", [])] + [t.lower() for t in meal.get("meal_type", [])] + [meal.get("category", "").lower()]
                if slot not in valid_types and "main course" not in valid_types:
                    continue

                cand_prot = float(meal.get("protein", 0))
                cand_cal = float(meal.get("calories", 0))
                
                if cand_prot <= old_prot + 5: continue
                if meal_counts.get(meal.get("mealName", "").lower(), 0) >= 2: continue

                new_plan_cal = plan.get("actual_calories", 0) - old_cal + cand_cal
                if new_plan_cal > max_cals: continue

                candidates.append(meal)

            if not candidates:
                continue

            best_candidate = candidates[0] # already sorted by density

            cand_prot = float(best_candidate.get("protein", 0))
            cand_cal = float(best_candidate.get("calories", 0))

            new_item = {
                "mealName": best_candidate.get("mealName", ""),
                "quantity": 1.0,
                "calories": cand_cal,
                "protein": cand_prot,
                "carbs": float(best_candidate.get("carbs") or 0),
                "fat": float(best_candidate.get("fat") or 0)
            }

            plan["meals"][slot][lp["index"]] = new_item
            added_name = new_item["mealName"].lower()
            meal_counts[added_name] = meal_counts.get(added_name, 0) + 1

            plan["actual_calories"] += (cand_cal - old_cal)
            plan["actual_protein"] += (cand_prot - old_prot)
            current_protein += (cand_prot - old_prot)
            swaps += 1

        # STEP 2: ADDITIONS IF STILL DEFICIT
        if current_protein < target_protein - 5:
            additions = 0
            slots_cycle = ["breakfast", "snack", "dinner", "lunch"]
            
            for candidate in high_protein_candidates:
                if additions >= 4 or current_protein >= target_protein - 5:
                    break
                    
                name = candidate.get("mealName", "")
                if meal_counts.get(name.lower(), 0) >= 2:
                    continue

                cand_prot = float(candidate.get("protein") or 0)
                cand_cals = float(candidate.get("calories") or 0)

                if plan.get("actual_calories", 0) + cand_cals > max_cals:
                    continue
                    
                slot = slots_cycle[additions % len(slots_cycle)]

                new_item = {
                    "mealName": name,
                    "quantity": 1.0,
                    "calories": cand_cals,
                    "protein": cand_prot,
                    "carbs": float(candidate.get("carbs") or 0),
                    "fat": float(candidate.get("fat") or 0)
                }
                
                meals_dict = plan.setdefault("meals", {})
                meals_dict.setdefault(slot, []).append(new_item)
                
                added_name = name.lower()
                meal_counts[added_name] = meal_counts.get(added_name, 0) + 1
                plan["actual_protein"] += cand_prot
                plan["actual_calories"] += cand_cals
                current_protein += cand_prot
                additions += 1

        plan = self._recompute_totals(plan)
        return plan

    def final_protein_check(self, plan, meals_db, user, target_protein, user_target_calories):
        """STEP 4: Final Protein Correction"""
        plan = self._recompute_totals(plan)
        current_protein = plan.get("actual_protein", 0)
        
        # Protein deficit > 10%
        if target_protein > 0 and (target_protein - current_protein) / target_protein > 0.10:
            plan = self.fix_protein(plan, meals_db, user, target_protein)
            plan = self._recompute_totals(plan)
        return plan

    def apply_knn_validation(self, plan, meals_db, user):
        is_vegan = bool(user.get("is_vegan", False))
        is_veg = bool(user.get("is_vegetarian", False))
        is_gf = bool(user.get("is_gluten_free", False))
        is_nf = bool(user.get("is_nut_free", False))

        if not (is_vegan or is_veg or is_gf or is_nf):
            return plan

        target_calories = plan.get("target_calories", 2000)
        if "user_target_calories" in plan:
             target_calories = plan["user_target_calories"]
        
        target_protein = float(plan.get("target_macros", {}).get("protein", 0))
        if "user_target_protein" in plan:
             target_protein = plan["user_target_protein"]

        replacements = 0
        invalid_items = []

        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            items = plan.get("meals", {}).get(slot, [])
            for idx, item in enumerate(items):
                name = item.get("mealName", "").lower()
                full_meal = next((m for m in meals_db if m.get("mealName", "").lower() == name), None)

                invalid = False
                if full_meal:
                    if is_vegan and not full_meal.get("is_vegan"): invalid = True
                    elif is_veg and not (full_meal.get("is_vegetarian") or full_meal.get("is_vegan")): invalid = True
                    elif is_gf and not full_meal.get("is_gluten_free"): invalid = True
                    elif is_nf and not full_meal.get("is_nut_free"): invalid = True
                else:
                    # If not in DB, fallback to string matching to protect veg users
                    from utils.diet_utils import _NON_VEG_KWS
                    if is_vegan or is_veg:
                        if any(kw in name for kw in _NON_VEG_KWS):
                            invalid = True
                            full_meal = {"mealName": name, "calories": item.get("calories", 300), "protein": item.get("protein", 10), "carbs": item.get("carbs", 30), "fat": item.get("fat", 10)}

                if invalid:
                    invalid_items.append({
                        "slot": slot,
                        "index": idx,
                        "item": item,
                        "full_meal": full_meal or item
                    })

        if not invalid_items:
            return plan

        knn = get_knn_model()
        if not knn.knn: # In case the model wasn't loaded or trained
            knn.fit(meals_db)

        existing_meals = set()
        for slot in ["breakfast", "lunch", "snack", "dinner"]:
            for item in plan.get("meals", {}).get(slot, []):
                existing_meals.add(item.get("mealName", "").lower())

        for inv in invalid_items:
            # Replace ALL invalid items for dietary safety!
            # if replacements >= 3:
            #     break
            
            old_item = inv["item"]
            
            candidates = knn.find_replacements_for_user(inv["full_meal"], user, k=10)
            
            best_cand = None
            best_qty = 1.0
            
            for cand in candidates:
                if cand.get("mealName", "").lower() in existing_meals: continue
                
                base_cand_cal = float(cand.get("calories", 1))
                if base_cand_cal == 0: base_cand_cal = 1
                
                target_item_cal = float(old_item.get("calories", 0))
                req_qty = target_item_cal / base_cand_cal
                
                if req_qty < 0.25 or req_qty > 4.0:
                    continue

                best_cand = cand
                best_qty = round(req_qty * 2) / 2
                if best_qty < 0.5: best_qty = 0.5
                break

            if not best_cand:
                continue

            cand_cal = float(best_cand.get("calories", 0)) * best_qty
            cand_prot = float(best_cand.get("protein", 0)) * best_qty

            new_item = {
                "mealName": best_cand.get("mealName", ""),
                "quantity": best_qty,
                "calories": round(cand_cal, 1),
                "protein": round(cand_prot, 1),
                "carbs": round(float(best_cand.get("carbs", 0)) * best_qty, 1),
                "fat": round(float(best_cand.get("fat", 0)) * best_qty, 1)
            }

            plan["actual_calories"] += (new_item["calories"] - float(old_item.get("calories", 0)))
            plan["actual_protein"] += (new_item["protein"] - float(old_item.get("protein", 0)))
            
            plan["meals"][inv["slot"]][inv["index"]] = new_item
            existing_meals.add(new_item["mealName"].lower())
            replacements += 1

        return plan

meal_generator_service = MealGeneratorService()
