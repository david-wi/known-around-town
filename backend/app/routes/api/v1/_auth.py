from fastapi import Cookie, Header, HTTPException, status

from app.config import get_settings

# WHY: A single cookie name reused by both the login route and the admin-page
# guard. Keeping it here (not duplicated in admin templates) means there is
# only one place to change the name if we ever rename it.
ADMIN_COOKIE_NAME = "kbt_admin_key"


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

    If `ADMIN_API_KEY` is unset (typical local dev), the gate is wide open.
    Production must set the env var.
    """
    expected = get_settings().admin_api_key
    if not expected:
        # No key configured -> open for local dev. In production set ADMIN_API_KEY.
        return
    if x_api_key == expected or kbt_admin_key == expected:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Admin API key required",
    )
