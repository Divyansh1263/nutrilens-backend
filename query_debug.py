import os
from firebase_admin import firestore
import firebase_admin

if not firebase_admin._apps:
    firebase_admin.initialize_app()
db = firestore.client()

print("Fetching latest debug log...")
docs = db.collection("nlp_debug_logs").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(1).stream()

for d in docs:
    print(d.to_dict())
