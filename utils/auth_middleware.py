# utils/auth_middleware.py
#
# Firebase idToken verification middleware.
#
# Strategy:
#   1. If an "Authorization: Bearer <idToken>" header is present,
#      verify it with Firebase Admin SDK and store the decoded uid
#      on request.firebase_uid.
#   2. If the header is absent (old APK / dev calls), fall back to
#      reading userId from the request body / query params as before.
#      request.firebase_uid will be None in this case.
#
# This dual-mode approach means the existing APK continues to work
# without any forced upgrade, while new clients use secure tokens.
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


def firebase_auth_optional(f):
    """
    Decorator: verify Firebase idToken when present; fall back gracefully
    if absent.  Sets ``request.firebase_uid`` (str | None).

    Use this on endpoints that must support BOTH old (no-token) and new
    (token-bearing) clients during the transition period.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _extract_bearer_token()
        if token:
            try:
                decoded = firebase_admin.auth.verify_id_token(token)
                request.firebase_uid = decoded["uid"]
                app_logger.debug(
                    "[auth] token verified — uid=%s", request.firebase_uid
                )
            except firebase_admin.auth.ExpiredIdTokenError:
                app_logger.warning("[auth] idToken expired")
                request.firebase_uid = None
            except firebase_admin.auth.InvalidIdTokenError as e:
                app_logger.warning("[auth] invalid idToken: %s", e)
                request.firebase_uid = None
            except Exception as e:
                app_logger.error("[auth] token verification error: %s", e)
                request.firebase_uid = None
        else:
            request.firebase_uid = None
        return f(*args, **kwargs)
    return decorated


def firebase_auth_required(f):
    """
    Decorator: require a valid Firebase idToken.  Returns HTTP 401 if
    the token is missing or invalid.

    Use this on NEW endpoints that are token-only from day one.
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
                "[auth] token verified (required) — uid=%s", request.firebase_uid
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


def get_user_id_from_request(data: dict | None = None) -> str | None:
    """
    Resolve the effective userId for the current request.

    Priority:
      1. request.firebase_uid  — set by firebase_auth_optional / required
      2. data.get("userId")    — body param (old APK backward compat)
      3. request.args.get("userId") — query param (GET endpoints)
    """
    uid = getattr(request, "firebase_uid", None)
    if uid:
        return uid
    if data:
        uid = data.get("userId")
        if uid:
            return uid
    return request.args.get("userId")
