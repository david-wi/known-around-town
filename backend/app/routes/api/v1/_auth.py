import hmac

from fastapi import Cookie, Header, HTTPException, status

from app.config import get_settings

# WHY: A single cookie name reused by both the login route and the admin-page
# guard. Keeping it here (not duplicated in admin templates) means there is
# only one place to change the name if we ever rename it.
ADMIN_COOKIE_NAME = "kbt_admin_key"


def admin_key_matches(candidate: str | None) -> bool:
    """Return True only when a configured admin key matches the candidate.

    # @define KAT-075 "Revenue-path security hardening"
    """
    expected = get_settings().admin_api_key.strip()
    provided = (candidate or "").strip()
    if not expected or not provided:
        return False
    return hmac.compare_digest(provided, expected)


async def require_admin(
    x_api_key: str | None = Header(default=None),
    kbt_admin_key: str | None = Cookie(default=None),
) -> None:
    """Admin gate for both JSON API endpoints and HTML admin pages.

    Accepts either:
      - the `X-API-Key` header (used by scripts, curl, and fetch calls that
        explicitly attach the key), OR
      - the `kbt_admin_key` cookie (set by the `/admin/login` page so an
        admin opening `/admin/claims` in a browser doesn't have to type the
        key on every request, and so client-side fetch calls don't have to
        carry the raw key in JavaScript).

    If `ADMIN_API_KEY` is unset, the gate fails closed. Tests/local scripts that
    need admin access should set a local key explicitly rather than relying on
    a missing secret as an implicit grant.
    """
    if admin_key_matches(x_api_key) or admin_key_matches(kbt_admin_key):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin API key required",
    )
