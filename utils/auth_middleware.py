# utils/auth_middleware.py
#
# Firebase idToken verification middleware.
#
# Post-migration: ALL endpoints require a valid Firebase Bearer token.
# The userId is ALWAYS derived from the verified token (request.firebase_uid).
# Body/query "userId" fallbacks have been REMOVED for security.
#
from functools import wraps

import firebase_admin.auth
from flask import request

from utils.logger import app_logger


def _extract_bearer_token() -> str | None:
    """Pull the raw JWT from 'Authorization: Bearer <token>'."""
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:].strip()
        return token if token else None
    return None


def firebase_auth_required(f):
    """
    Decorator: require a valid Firebase idToken.  Returns HTTP 401 if
    the token is missing or invalid.

    Sets ``request.firebase_uid`` on success.
    """
    from utils.response_utils import error as api_error

    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_bearer_token()
        if not token:
            return api_error("Authentication required: missing Bearer token", 401)
        try:
            decoded = firebase_admin.auth.verify_id_token(token)
            request.firebase_uid = decoded["uid"]
            app_logger.debug(
                "[auth] token verified (required) -- uid=%s", request.firebase_uid
            )
        except firebase_admin.auth.ExpiredIdTokenError:
            return api_error("Authentication token expired", 401)
        except (firebase_admin.auth.InvalidIdTokenError,
                firebase_admin.auth.CertificateFetchError):
            return api_error("Invalid authentication token", 401)
        except Exception as e:
            app_logger.error("[auth] token verification error: %s", e)
            return api_error("Authentication error", 401)
        return f(*args, **kwargs)
    return decorated


# Keep firebase_auth_optional as a transitional alias that still sets
# firebase_uid when available but does NOT block unauthenticated requests.
# This is only used during the transition period for backward compatibility
# with old APK versions already in the wild.
def firebase_auth_optional(f):
    """
    Decorator: verify Firebase idToken when present; fall back gracefully
    if absent.  Sets ``request.firebase_uid`` (str | None).

    DEPRECATED: New endpoints should use firebase_auth_required instead.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_bearer_token()
        if token:
            try:
                decoded = firebase_admin.auth.verify_id_token(token)
                request.firebase_uid = decoded["uid"]
            except Exception:
                request.firebase_uid = None
        else:
            request.firebase_uid = None
        return f(*args, **kwargs)
    return decorated


def get_user_id_from_request(data: dict | None = None) -> str | None:
    """
    Resolve the effective userId for the current request.

    Post-migration: ONLY uses the verified Firebase UID from the token.
    Body/query param fallbacks have been REMOVED for security.
    """
    uid = getattr(request, "firebase_uid", None)
    return uid
