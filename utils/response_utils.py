# utils/response_utils.py
from flask import jsonify
from datetime import datetime, date


def sanitize_firestore_data(data):
    """
    Recursively convert Firestore-specific types to JSON-safe values.
    Handles: datetime, date, Timestamp, DocumentReference, Sentinel values.
    """
    # Lazy imports to avoid circular dependency issues
    try:
        from google.cloud.firestore_v1 import DocumentReference
        from google.protobuf.timestamp_pb2 import Timestamp as ProtoTimestamp
    except ImportError:
        DocumentReference = None
        ProtoTimestamp = None

    if isinstance(data, dict):
        return {k: sanitize_firestore_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_firestore_data(v) for v in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, date):
        return data.isoformat()
    elif DocumentReference is not None and isinstance(data, DocumentReference):
        return data.path
    elif hasattr(data, 'isoformat'):
        # Catches Firestore Timestamp and any other date-like objects
        return data.isoformat()
    elif hasattr(data, '__class__') and 'Sentinel' in data.__class__.__name__:
        return None  # Strip Firestore Sentinel values
    else:
        return data


def success(data=None, message=""):
    """
    Standardize successful API responses.
    """
    response = {
        "success": True,
        "message": message
    }
    if data is not None:
        response["data"] = sanitize_firestore_data(data)
        
    return jsonify(response), 200

def error(message, status_code=400):
    """
    Standardize error API responses.
    """
    return jsonify({
        "success": False,
        "message": message
    }), status_code
