"""Preview login API — email + numeric code flow for the pre-launch gate.

These endpoints power the /preview-login page and are intentionally kept
thin. The security primitives live in app.services.preview_auth.

Flow:
  POST /api/v1/preview/login/request  {email}        -> 200 {ok: true}
  POST /api/v1/preview/login/verify   {email, code}  -> 200 {ok: true}, sets cookie

The request endpoint always returns 200 for a well-formed email address,
even when the email is not on the allow-list. WHY: returning 403 for
disallowed emails would let an attacker probe whether specific addresses
are on the list.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.preview_auth import (
    PREVIEW_COOKIE_NAME,
    SESSION_TTL_SECONDS,
    code_expires_at,
    constant_equal,
    generate_code,
    generate_session_token,
    hash_value,
    is_allowed_email,
    session_expires_at,
)
from app.services.owner_auth import looks_like_email
from app.services.preview_email import send_preview_code_email

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=320)


class VerifyRequest(BaseModel):
    email: str = Field(..., max_length=320)
    # WHY: max_length=20 to accept user-entered codes with spaces between
    # digits ("1 2 3 4 5 6" = 11 chars). _normalize_code strips non-digits
    # after validation so the 6-digit check is applied to the cleaned value.
    code: str = Field(..., max_length=20)


class OkResponse(BaseModel):
    ok: bool = True


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _normalize_code(raw: str) -> str:
    # WHY: strip whitespace users may type when reading the code aloud or
    # transcribing from a phone screen. Keep only digits.
    return "".join(ch for ch in (raw or "") if ch.isdigit())


def _set_preview_cookie(response: Response, request: Request, token: str) -> None:
    """Attach the preview_token cookie to the response.

    Attributes:
    - HttpOnly: hidden from JavaScript — a stray XSS cannot steal it.
    - Secure: sent over HTTPS only in production; relaxed on plain http so
      local dev works without SSL.
    - SameSite=Lax: blocks cookie on cross-site POST; keeps top-level
      navigation (click a link from email) working.
    - Max-Age matches SESSION_TTL_SECONDS so the browser evicts the cookie
      on the same schedule the server checks session expiry.
    """
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key=PREVIEW_COOKIE_NAME,
        value=token,
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )


@router.post("/preview/login/request", response_model=OkResponse)
async def request_preview_code(payload: LoginRequest) -> OkResponse:
    """Send a one-time preview access code to the supplied email.

    Returns 200 regardless of allow-list membership for a valid email —
    see module docstring for the reason.
    """
    email = _normalize_email(payload.email)
    if not looks_like_email(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    # Only send a real code to allowed addresses; for everyone else we
    # return 200 and silently drop the send. The caller sees identical
    # behaviour either way.
    if is_allowed_email(email):
        db = get_db()
        code = generate_code()
        doc = {
            "_id": str(uuid.uuid4()),
            "email": email,
            "code_hash": hash_value(code),
            "created_at": datetime.now(timezone.utc),
            "expires_at": code_expires_at(),
            "used_at": None,
        }
        await db.preview_codes.insert_one(doc)
        await send_preview_code_email(email=email, code=code)

    return OkResponse(ok=True)


@router.post("/preview/login/verify", response_model=OkResponse)
async def verify_preview_code(
    payload: VerifyRequest, request: Request, response: Response
) -> OkResponse:
    """Verify a preview code and set the long-lived preview_token cookie."""
    email = _normalize_email(payload.email)
    code = _normalize_code(payload.code)

    if not looks_like_email(email) or len(code) != 6:
        raise HTTPException(status_code=400, detail="Invalid email or code.")

    # Disallowed email — never had a code, never will. Return the same
    # 401 as an incorrect code so there's no difference in API shape.
    if not is_allowed_email(email):
        raise HTTPException(status_code=401, detail="Invalid or expired code.")

    db = get_db()
    now = datetime.now(timezone.utc)

    # Find the most recent unused, unexpired code for this email.
    doc = await db.preview_codes.find_one(
        {
            "email": email,
            "used_at": None,
            "expires_at": {"$gt": now},
        },
        sort=[("created_at", -1)],
    )
    if not doc:
        raise HTTPException(status_code=401, detail="Invalid or expired code.")

    submitted_hash = hash_value(code)
    stored_hash = doc.get("code_hash", "")
    if not constant_equal(submitted_hash, stored_hash):
        raise HTTPException(status_code=401, detail="That code did not match. Please try again.")

    # Mark the code as used so it cannot be replayed.
    await db.preview_codes.update_one(
        {"_id": doc["_id"]},
        {"$set": {"used_at": now}},
    )

    # Issue a session token and store a hashed copy in preview_sessions.
    token = generate_session_token()
    expires = session_expires_at()
    session_doc = {
        "_id": str(uuid.uuid4()),
        "email": email,
        "token_hash": hash_value(token),
        "created_at": now,
        "expires_at": expires,
    }
    await db.preview_sessions.insert_one(session_doc)

    _set_preview_cookie(response, request, token)
    return OkResponse(ok=True)
