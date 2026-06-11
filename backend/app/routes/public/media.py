"""Public media-serving route.

Streams GridFS files (owner-uploaded photos) to the browser.

Route: GET /media/{photo_id}

No authentication required — photos on public listing pages must be
accessible to every visitor. The photo_id (a GridFS ObjectId hex string)
is not guessable in any meaningful sense: 24 hex characters from a
cryptographically random ObjectId gives 2^96 possible values.
"""

from __future__ import annotations

import logging

from bson import ObjectId
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.database import get_gridfs_bucket

log = logging.getLogger(__name__)
router = APIRouter()

# WHY: 1-year cache for immutable photos. GridFS files are write-once —
# we never update the bytes of an existing photo, we only delete it and
# upload a new one. So a photo at /media/{id} is truly immutable and can
# be cached for the full year.
_CACHE_CONTROL = "public, max-age=31536000, immutable"

# WHY: whitelist of MIME types the /media/ route will forward; anything else
# falls through to the "image/jpeg" safe default.
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.get("/media/{photo_id}")
async def serve_photo(photo_id: str) -> StreamingResponse:
    """Stream a GridFS photo to the browser.

    Returns 400 for a malformed id, 404 when the file is not in GridFS.
    Sets a 1-year immutable cache header so browsers never re-fetch the
    same file.
    """
    try:
        oid = ObjectId(photo_id)
    except Exception:
        raise HTTPException(400, "Invalid photo identifier")

    bucket = get_gridfs_bucket()
    try:
        grid_out = await bucket.open_download_stream(oid)
    except Exception as exc:
        # WHY: log the real exception before returning 404 so a GridFS timeout
        # or Atlas connectivity error shows up in server logs instead of being
        # silently swallowed as a missing-file 404.
        log.warning("GridFS open_download_stream failed for %s: %s", photo_id, exc)
        raise HTTPException(404, "Photo not found")

    # WHY: fall back to image/jpeg if the metadata field is missing or has
    # an unrecognised value. JPEG is the most common case and browsers handle
    # it gracefully even when the Content-Type header is slightly wrong.
    raw_ct = (grid_out.metadata or {}).get("content_type", "image/jpeg")
    content_type = raw_ct if raw_ct in _ALLOWED_CONTENT_TYPES else "image/jpeg"

    async def _stream():
        while True:
            chunk = await grid_out.readchunk()
            if not chunk:
                break
            yield chunk

    return StreamingResponse(
        _stream(),
        media_type=content_type,
        headers={"Cache-Control": _CACHE_CONTROL},
    )
