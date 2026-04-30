# services/meal_logging_service.py
import logging
from datetime import datetime
from repositories.tracker_repository import tracker_repo
from repositories.meal_repository import meal_repo
from firebase_admin import firestore

_log = logging.getLogger(__name__)

class MealLoggingService:
    def log_meal(self, user_id, meal_name, quantity, meal_type, source="manual", provided_macros=None, date_str=None):
        """
        Log a meal.

        Normal path: look up the meal in Firestore by name and compute totals.
        Fallback path: if Firestore is rate limited (or meal missing), accept provided macros
        from the client to keep the app usable in dev/demo mode.
        """
        # 1. Fetch Macros
        meal_data = None
        try:
            meal_data = meal_repo.get_meal_by_name(meal_name)
        except Exception:
            meal_data = None

        if not meal_data and not provided_macros:
            return None, f"Meal {meal_name} not found"
            
        qty = float(quantity)
        # Use date from frontend if provided, otherwise default to today
        if not date_str:
            date_str = str(datetime.now().date())
        today = date_str

        # Use provided macros if meal lookup failed
        if not meal_data and provided_macros:
            unit_cal = float(provided_macros.get("calories") or 0)
            unit_prot = float(provided_macros.get("protein") or 0)
            unit_carbs = float(provided_macros.get("carbs") or 0)
            unit_fat = float(provided_macros.get("fat") or 0)
            meal_data = {
                "mealName": meal_name,
                "calories": unit_cal,
                "protein": unit_prot,
                "carbs": unit_carbs,
                "fat": unit_fat,
            }
        
        # 2. Build Log
        # FIX v2.6: store both *_per_unit (base) and total (quantity-scaled) fields.
        # /update-log reads *_per_unit so it can recalculate exactly at any qty.
        unit_cal   = round(float(meal_data.get("calories") or 0), 1)
        unit_prot  = round(float(meal_data.get("protein")  or 0), 1)
        unit_carbs = round(float(meal_data.get("carbs")    or 0), 1)
        unit_fat   = round(float(meal_data.get("fat")      or 0), 1)

        log_data = {
            "userId":             user_id,
            "date":               today,
            "mealName":           meal_data.get("mealName", meal_name),
            "mealType":           meal_type,
            # Totals
            "calories":           round(unit_cal   * qty, 1),
            "protein":            round(unit_prot  * qty, 1),
            "carbs":              round(unit_carbs * qty, 1),
            "fat":                round(unit_fat   * qty, 1),
            "quantity":           qty,
            # Per-unit base macros — used by /update-log
            "base_calories":      unit_cal,
            "base_protein":       unit_prot,
            "base_carbs":         unit_carbs,
            "base_fat":           unit_fat,
            "source":             source,
            "log_time":           firestore.SERVER_TIMESTAMP
        }
        print("LOG MEAL:", log_data["mealName"], "qty:", log_data["quantity"], "final_cal:", log_data["calories"])
        
        # 3. TASK 4 — Duplicate log guard
        #    If same mealName already logged for this user+date, ADD qty to the
        #    existing document instead of inserting a second entry.
        existing = tracker_repo.check_existing_log(user_id, log_data["mealName"], today)
        if existing:
            existing_log_id = existing.get("logId") or existing.get("id", "")
            old_qty = float(existing.get("quantity") or 1)
            new_qty = old_qty + qty

            # Recalculate totals from per-unit base stored on existing document
            base_cal   = float(existing.get("base_calories") or 0)
            base_prot  = float(existing.get("base_protein")  or 0)
            base_carbs = float(existing.get("base_carbs")    or 0)
            base_fat   = float(existing.get("base_fat")      or 0)


            merged_updates = {
                "quantity":  new_qty,
                "calories":  round(base_cal   * new_qty, 1),
                "protein":   round(base_prot  * new_qty, 1),
                "carbs":     round(base_carbs * new_qty, 1),
                "fat":       round(base_fat   * new_qty, 1),
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
            tracker_repo.update_log_quantity(existing_log_id, merged_updates)
            _log.info(
                "[log-meal] UPDATED existing log '%s' (id=%s): qty %.1f → %.1f",
                log_data["mealName"], existing_log_id, old_qty, new_qty,
            )
            log_id = existing_log_id
        else:
            # Normal insert — no duplicate found
            log_id = tracker_repo.log_meal(log_data)
            _log.info(
                "[log-meal] INSERTED new log '%s' (id=%s) qty=%.1f",
                log_data["mealName"], log_id, qty,
            )

        # 4. Update preference history
        try:
            tracker_repo.update_user_meal_frequency(user_id, meal_name, log_data["date"])
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                pass
            else:
                raise

        # 5. Recalculate daily tracker
        from services.tracker_service import tracker_service
        try:
            tracker_service.recalculate_daily_tracker(user_id, log_data["date"])
        except Exception as e:
            if "Quota exceeded" in str(e) or "429" in str(e):
                pass
            else:
                raise

        return log_id, ""

    def update_log_quantity(self, log_id, new_quantity):
        """
        Update quantity and recalculate macros for a logged meal.

        Per-unit base priority chain (prevents double-scaling):
          1. base_calories  — stamped by annotate_plan_item on plan-sourced logs
          2. calories_per_unit — stamped by log_meal() on NLP/manual logs
          3. Ratio fallback — legacy docs only (pre v2.6)

        Returns (success: bool, error: str, updated: dict)
        """
        qty = float(new_quantity)
        _log.info("[update-log] logId=%s new_qty=%.2f", log_id, qty)
        if qty <= 0:
            return False, "Quantity must be > 0", {}

        log_data = tracker_repo.get_log(log_id)
        if not log_data:
            return False, "Log not found", {}

        base_cal = log_data.get("base_calories") or 0.0
        base_prot = log_data.get("base_protein") or 0.0
        base_carbs = log_data.get("base_carbs") or 0.0
        base_fat = log_data.get("base_fat") or 0.0

        cal   = round(float(base_cal) * qty, 1)
        prot  = round(float(base_prot) * qty, 1)
        carbs = round(float(base_carbs) * qty, 1)
        fat   = round(float(base_fat) * qty, 1)
        
        _log.info("[update-log] using base_* fields: base_cal=%.4f", float(base_cal))

        updates = {
            "quantity":   qty,
            "calories":   cal,
            "protein":    prot,
            "carbs":      carbs,
            "fat":        fat,
            "updated_at": firestore.SERVER_TIMESTAMP
        }

        tracker_repo.update_log_quantity(log_id, updates)

        from services.tracker_service import tracker_service
        tracker_service.recalculate_daily_tracker(log_data["userId"], log_data["date"])

        updated_macros = {
            "logId":    log_id,
            "mealName": log_data.get("mealName", ""),
            "quantity": qty,
            "calories": cal,
            "protein":  prot,
            "carbs":    carbs,
            "fat":      fat,
        }
        return True, "", updated_macros
        
    def delete_log(self, log_id):
        log_data = tracker_repo.get_log(log_id)
        if not log_data: return False, "Log not found"

        success = tracker_repo.delete_log(log_id)
        if success:
             from services.tracker_service import tracker_service
             tracker_service.recalculate_daily_tracker(log_data["userId"], log_data["date"])
             return True, ""
        return False, "Log not found"

meal_logging_service = MealLoggingService()
