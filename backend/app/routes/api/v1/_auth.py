from fastapi import Header, HTTPException, status

from app.config import get_settings


async def require_admin(x_api_key: str | None = Header(default=None)) -> None:
    expected = get_settings().admin_api_key
    if not expected:
        # No key configured -> open for local dev. In production set ADMIN_API_KEY.
        return
    if x_api_key != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin API key required",
        )
