"""Owner login API — passwordless verification-code flow.

These endpoints are deliberately small. The actual security primitives
live in `app.services.owner_auth` (code generation, hashing, cookie
signing) and the email send lives in `app.services.owner_email`. This
module is just the HTTP shape.

Flow:

1. POST /api/v1/owner/login/request   {email}        -> 200 {ok: true}
2. POST /api/v1/owner/login/verify    {email, code}  -> 200 {ok: true, email}, sets cookie
3. POST /api/v1/owner/logout                         -> 200 {ok: true}, clears cookie

The "request" endpoint always returns 200 (modulo schema/rate-limit
errors) regardless of whether the email is associated with any business,
so an attacker cannot use this endpoint as a directory probe.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.database import get_db
from app.services.owner_auth import (
    MAX_VERIFY_ATTEMPTS,
    RATE_LIMIT_MAX_CODES,
    RATE_LIMIT_WINDOW,
    SESSION_COOKIE_NAME,
    SESSION_LIFETIME,
    code_expires_at,
    codes_match,
    generate_code,
    hash_code,
    looks_like_email,
    sign_session,
)
from app.services.owner_email import send_owner_code_email

router = APIRouter()


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=320)


class VerifyRequest(BaseModel):
    email: str = Field(..., max_length=320)
    code: str = Field(..., max_length=32)


class OkResponse(BaseModel):
    ok: bool = True


class VerifyResponse(BaseModel):
    ok: bool = True
    email: str


def _normalize_email(raw: str) -> str:
    return (raw or "").strip().lower()


def _normalize_code(raw: str) -> str:
    # WHY: strip every kind of whitespace, including internal spaces a
    # user might introduce when reading the code off the email screen
    # ("AB 23 CD"). Then upper-case so codes compare hash-equal regardless
    # of the casing the user typed.
    return "".join((raw or "").split()).upper()


def _set_session_cookie(response: Response, request: Request, email: str) -> None:
    """Attach the signed session cookie to the response.

    Cookie attributes:
    - HttpOnly: hidden from JavaScript so a stray XSS can't read it.
    - Secure: only sent over HTTPS in production. In local dev (HTTP
      against `*.localhost`) we still need the browser to keep the
      cookie, so we relax Secure when the incoming scheme is plain http.
    - SameSite=Lax: blocks the cookie on cross-site POST attempts but
      keeps top-level navigations working (the typical "click an
      email link" path).
    - Max-Age: matches SESSION_LIFETIME so the browser auto-evicts the
      cookie on the same schedule the server checks the signed
      timestamp.
    """
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=sign_session(email),
        max_age=int(SESSION_LIFETIME.total_seconds()),
        httponly=True,
        secure=is_secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


@router.post("/owner/login/request", response_model=OkResponse)
async def request_owner_login_code(payload: LoginRequest) -> OkResponse:
    """Send a one-time sign-in code to the supplied email."""
    email = _normalize_email(payload.email)
    if not looks_like_email(email):
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")

    db = get_db()

    # Rate-limit check: count codes issued to this email in the recent window.
    window_start = datetime.now(timezone.utc) - RATE_LIMIT_WINDOW
    recent = await db.owner_magic_codes.count_documents(
        {"email": email, "created_at": {"$gte": window_start}}
    )
    if recent >= RATE_LIMIT_MAX_CODES:
        # WHY: 429 with Retry-After lets a polite client back off the
        # right amount of time without polling. The hardcoded retry
        # window mirrors the rate-limit window — this is the longest a
        # caller would have to wait.
        retry_after = int(RATE_LIMIT_WINDOW.total_seconds())
        raise HTTPException(
            status_code=429,
            detail="Too many codes requested. Please wait a few minutes and try again.",
            headers={"Retry-After": str(retry_after)},
        )

    code = generate_code()
    doc = {
        "_id": str(uuid.uuid4()),
        "email": email,
        "code_hash": hash_code(code),
        "created_at": datetime.now(timezone.utc),
        "expires_at": code_expires_at(),
        "used_at": None,
        "attempts": 0,
    }
    await db.owner_magic_codes.insert_one(doc)

    # Fire-and-log the email send. We intentionally don't surface
    # provider failures to the caller — they should look identical to a
    # successful send so attackers can't probe which emails delivered.
    await send_owner_code_email(email=email, code=code)

    return OkResponse(ok=True)


@router.post("/owner/login/verify", response_model=VerifyResponse)
async def verify_owner_login_code(
    payload: VerifyRequest, request: Request, response: Response
) -> VerifyResponse:
    """Verify a code and set the owner session cookie."""
    email = _normalize_email(payload.email)
    code = _normalize_code(payload.code)

    if not looks_like_email(email) or not code:
        raise HTTPException(status_code=400, detail="Invalid email or code.")

    db = get_db()

    # Most recent unused code for this email.
    doc = await db.owner_magic_codes.find_one(
        {"email": email, "used_at": None},
        sort=[("created_at", -1)],
    )
    if not doc:
        raise HTTPException(status_code=401, detail="Invalid or expired code.")

    expires_at = doc.get("expires_at")
    if expires_at is None or _to_aware_utc(expires_at) < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Invalid or expired code.")

    attempts = int(doc.get("attempts", 0) or 0)
    if attempts >= MAX_VERIFY_ATTEMPTS:
        # WHY: once the row is locked we tell the caller to request a
        # fresh code, but we do not delete the row — it still serves as
        # a rate-limit anchor in the recent-codes window.
        raise HTTPException(
            status_code=401,
            detail="Too many incorrect attempts. Please request a new code.",
        )

    if not codes_match(code, doc.get("code_hash", "")):
        await db.owner_magic_codes.update_one(
            {"_id": doc["_id"]},
            {"$inc": {"attempts": 1}},
        )
        remaining = max(0, MAX_VERIFY_ATTEMPTS - attempts - 1)
        # WHY: showing the remaining attempts helps a real owner with a
        # typo recover without locking themselves out.
        if remaining == 0:
            detail = "That code didn't match. Please request a new code."
        else:
            detail = f"That code didn't match. {remaining} attempts remaining."
        raise HTTPException(status_code=401, detail=detail)

    # Code is good — mark it used so it cannot be replayed.
    await db.owner_magic_codes.update_one(
        {"_id": doc["_id"]},
        {"$set": {"used_at": datetime.now(timezone.utc)}},
    )

    _set_session_cookie(response, request, email)
    return VerifyResponse(ok=True, email=email)


@router.post("/owner/logout", response_model=OkResponse)
async def owner_logout(response: Response) -> OkResponse:
    """Clear the owner session cookie."""
    _clear_session_cookie(response)
    return OkResponse(ok=True)


# ---------- small helpers ----------

def _to_aware_utc(value):
    """Ensure a datetime read from Mongo is timezone-aware UTC.

    Motor with tz_aware=True returns aware datetimes, but mongomock may
    return naive ones in tests. Normalizing here lets the same code path
    work against both the production driver and the in-memory test
    backend.
    """
    if not isinstance(value, datetime):
        return value
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
