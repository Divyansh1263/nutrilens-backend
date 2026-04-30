import os
import sys

# Add backend directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import firebase_admin
from firebase_admin import firestore

# Initialize Firebase
try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app()

db = firestore.client()

def clean_logs():
    print("Fetching all meal logs from Firestore...")
    logs_ref = db.collection("meal_logs")
    docs = list(logs_ref.stream())
    
    # Group logs by: userId + date + mealName
    grouped_logs = {}
    
    print(f"Found {len(docs)} total meal logs.")
    
    for doc in docs:
        log = doc.to_dict()
        doc_id = doc.id
        
        user_id = log.get("userId")
        date_str = log.get("date")
        meal_name = log.get("mealName")
        
        if not user_id or not date_str or not meal_name:
            continue
            
        key = f"{user_id}_{date_str}_{meal_name}"
        if key not in grouped_logs:
            grouped_logs[key] = []
        
        grouped_logs[key].append({"id": doc_id, "data": log})
        
    to_delete = []
    to_update = {}
    
    print("Finding duplicates...")
    for key, items in grouped_logs.items():
        if len(items) > 1:
            # Sort by log_time or id to keep the oldest/first one consistently
            items.sort(key=lambda x: str(x["data"].get("log_time") or x["id"]))
            
            # Keep the first one, delete the rest
            keep_item = items[0]
            keep_id = keep_item["id"]
            keep_data = keep_item["data"]
            
            total_qty = float(keep_data.get("quantity") or 1)
            
            print(f"Found {len(items)} duplicates for {key}")
            
            # Sum up quantities
            for duplicate in items[1:]:
                dup_qty = float(duplicate["data"].get("quantity") or 1)
                total_qty += dup_qty
                to_delete.append(duplicate["id"])
            
            # Recalculate macros for the kept log based on new total_qty
            if "calories_per_unit" in keep_data:
                base_cal = float(keep_data.get("calories_per_unit") or 0)
                base_prot = float(keep_data.get("protein_per_unit") or 0)
                base_carbs = float(keep_data.get("carbs_per_unit") or 0)
                base_fat = float(keep_data.get("fat_per_unit") or 0)
            elif "base_calories" in keep_data:
                base_cal = float(keep_data.get("base_calories") or 0)
                base_prot = float(keep_data.get("base_protein") or 0)
                base_carbs = float(keep_data.get("base_carbs") or 0)
                base_fat = float(keep_data.get("base_fat") or 0)
            else:
                old_qty = float(keep_data.get("quantity") or 1)
                safe_qty = old_qty if old_qty > 0 else 1.0
                base_cal = float(keep_data.get("calories") or 0) / safe_qty
                base_prot = float(keep_data.get("protein") or 0) / safe_qty
                base_carbs = float(keep_data.get("carbs") or 0) / safe_qty
                base_fat = float(keep_data.get("fat") or 0) / safe_qty
                
            updates = {
                "quantity": total_qty,
                "calories": round(base_cal * total_qty, 1),
                "protein": round(base_prot * total_qty, 1),
                "carbs": round(base_carbs * total_qty, 1),
                "fat": round(base_fat * total_qty, 1)
            }
            to_update[keep_id] = updates
            print(f"  -> Merging into {keep_id} with new quantity: {total_qty}")

    print(f"\nDeleting {len(to_delete)} duplicate logs and updating {len(to_update)} logs.")
    
    batch = db.batch()
    count = 0
    
    # Process deletions
    for doc_id in to_delete:
        batch.delete(logs_ref.document(doc_id))
        count += 1
        if count >= 400:
            batch.commit()
            batch = db.batch()
            count = 0
            
    # Process updates
    for doc_id, updates in to_update.items():
        batch.update(logs_ref.document(doc_id), updates)
        count += 1
        if count >= 400:
            batch.commit()
            batch = db.batch()
            count = 0
            
    if count > 0:
        batch.commit()
        
    print("Log cleanup complete!")

if __name__ == "__main__":
    clean_logs()
