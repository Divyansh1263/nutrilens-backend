import os
from firebase_admin import firestore
import firebase_admin

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

print("\n--- Testing Single Record Fetch ---")
docs = list(db.collection("nlp_debug_logs").order_by("timestamp", direction=firestore.Query.ASCENDING).stream())
doc = docs[-1] if docs else None
if doc:
    print(doc.to_dict())
