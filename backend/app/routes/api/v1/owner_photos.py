"""Owner photo upload and delete endpoints.

Lets a signed-in salon owner upload photos that appear in their
public listing gallery.

Routes:
    POST   /api/v1/owner/photos          — upload one photo (multipart)
    DELETE /api/v1/owner/photos/{photo_id} — remove a photo

Photos are stored in MongoDB GridFS under the "business_photos" bucket.
Each photo is served publicly at /media/{photo_id}.  The URL stored in
business.photos[].url is that /media/... path.
"""

from __future__ import annotations

import io
import logging
import uuid
from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from app.database import get_db, get_gridfs_bucket
from app.services.owner_auth import SESSION_COOKIE_NAME, verify_session

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/owner/photos")

# WHY: 10 MB cap — large enough for a high-quality phone photo but small
# enough to keep GridFS documents from bloating Atlas storage.
_MAX_BYTES = 10 * 1024 * 1024

# WHY: allow the three formats browsers and phones produce natively. AVIF
# is excluded — encoder support is still inconsistent, and the template
# uses background-image CSS which needs a broadly-supported format.
_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}

# WHY: magic-byte prefix check as a second layer after the MIME check. A
# client can lie about Content-Type; the bytes cannot. We check only the
# first 4 bytes because that is enough to distinguish the three formats.
_MAGIC: dict[bytes, str] = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG":      "image/png",
    b"RIFF":         "image/webp",  # RIFF....WEBP — refined below
}

# WHY: limit per business to prevent runaway storage use. 12 photos is
# plenty for a salon gallery and keeps Atlas under $0.01/business/month
# in GridFS storage at typical photo sizes.
_MAX_PHOTOS = 12


def _detect_mime(data: bytes) -> str | None:
    """Return the detected MIME type from the first few bytes, or None."""
    for prefix, mime in _MAGIC.items():
        if data[:len(prefix)] == prefix:
            if mime == "image/webp":
                # WHY: RIFF headers are shared by WAV and AVI; verify the
                # "WEBP" four-bytes at offset 8 to confirm it is actually WebP.
                return "image/webp" if data[8:12] == b"WEBP" else None
            return mime
    return None


def _session_email(request: Request) -> str:
    """Extract and verify owner session; raise 401 if missing or invalid."""
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    try:
        session = verify_session(cookie) if cookie else None
    except Exception:
        session = None
    if not session or not session.get("email"):
        raise HTTPException(401, "Not signed in")
    return session["email"].lower()


@router.post("")
async def upload_photo(request: Request, file: UploadFile = File(...)) -> dict:
    """Upload a photo for the signed-in owner's listing.

    Stores the image in GridFS and appends a Photo entry to the business
    document.  Returns the updated photo list so the browser can re-render
    the gallery without a page reload.
    """
    email = _session_email(request)

    # Read the full file into memory so we can:
    # 1. Check the size before writing to GridFS.
    # 2. Inspect the magic bytes to verify it is a real image.
    data = await file.read()
    if len(data) > _MAX_BYTES:
        raise HTTPException(413, f"File too large — maximum {_MAX_BYTES // 1_048_576} MB")

    if not data:
        raise HTTPException(400, "Empty file")

    detected = _detect_mime(data)
    if detected is None or detected not in _ALLOWED_MIME:
        raise HTTPException(
            415,
            "Unsupported file type — please upload a JPEG, PNG, or WebP image",
        )

    db = get_db()
    business = await db.businesses.find_one({"claimed_email": email})
    if not business:
        raise HTTPException(404, "No verified listing found for this account")

    existing_photos = business.get("photos") or []
    if len(existing_photos) >= _MAX_PHOTOS:
        raise HTTPException(
            409,
            f"Maximum {_MAX_PHOTOS} photos allowed — delete one before uploading another",
        )

    # WHY: store as GridFS rather than a URL field pointing to an external
    # CDN so photos work immediately with zero external-service setup. The
    # /media/{id} route serves them with the right Content-Type header and
    # a long cache lifetime. Moving to a CDN later is just a URL swap.
    bucket = get_gridfs_bucket()
    photo_id = await bucket.upload_from_stream(
        file.filename or "photo",
        io.BytesIO(data),
        metadata={
            "content_type": detected,
            "business_id": str(business["_id"]),
            "uploaded_by": email,
            "uploaded_at": datetime.now(timezone.utc),
        },
    )

    photo_url = f"/media/{photo_id}"
    # WHY: the first uploaded photo becomes the hero so it appears in the
    # listing header immediately. Owners can change the order later via the
    # dashboard reorder control.
    is_hero = len(existing_photos) == 0

    photo_entry = {
        "url": photo_url,
        "alt": "",
        "caption": "",
        "order": len(existing_photos),
        "is_hero": is_hero,
    }

    await db.businesses.update_one(
        {"_id": business["_id"]},
        {
            "$push": {"photos": photo_entry},
            "$set": {"updated_at": datetime.now(timezone.utc)},
        },
    )

    log.info(
        "Photo uploaded: business=%s photo_id=%s bytes=%d",
        business["_id"], photo_id, len(data),
    )

    # Re-fetch so the response reflects exactly what is now in DB.
    updated = await db.businesses.find_one({"_id": business["_id"]})
    return {"photos": (updated or {}).get("photos") or []}


@router.delete("/{photo_id}")
async def delete_photo(photo_id: str, request: Request) -> dict:
    """Remove a photo from the owner's listing and from GridFS.

    photo_id is the hex ObjectId of the GridFS file (the path segment after
    /media/ in the photo URL).
    """
    email = _session_email(request)

    db = get_db()
    business = await db.businesses.find_one({"claimed_email": email})
    if not business:
        raise HTTPException(404, "No verified listing found for this account")

    # WHY: validate that photo_id is a valid ObjectId before trying to look
    # it up in GridFS. An invalid id would raise a bson error deeper in the
    # stack and produce a confusing 500.
    try:
        oid = ObjectId(photo_id)
    except Exception:
        raise HTTPException(400, "Invalid photo identifier")

    photo_url = f"/media/{photo_id}"
    existing_photos = business.get("photos") or []

    # Confirm this business actually has this photo (authorization check).
    if not any(p.get("url") == photo_url for p in existing_photos if isinstance(p, dict)):
        raise HTTPException(404, "Photo not found on your listing")

    # Remove from the business document.
    deleted_was_hero = any(
        p.get("url") == photo_url and p.get("is_hero") for p in existing_photos if isinstance(p, dict)
    )
    remaining = [p for p in existing_photos if isinstance(p, dict) and p.get("url") != photo_url]

    # Re-index the remaining photos.  Only update hero if the deleted photo
    # was the hero — otherwise the existing hero must not change.
    for i, p in enumerate(remaining):
        p["order"] = i
    if deleted_was_hero and remaining:
        # WHY: promote the next photo to hero so the listing header always has
        # an image. Without this, deleting the hero leaves the page headerless.
        for p in remaining:
            p["is_hero"] = False
        remaining[0]["is_hero"] = True

    await db.businesses.update_one(
        {"_id": business["_id"]},
        {
            "$set": {
                "photos": remaining,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    # Remove from GridFS (best-effort — don't fail the request if the file
    # is already gone from GridFS, e.g. after a manual cleanup).
    try:
        bucket = get_gridfs_bucket()
        await bucket.delete(oid)
    except Exception as exc:
        log.warning("GridFS delete failed for %s (non-fatal): %s", photo_id, exc)

    log.info("Photo deleted: business=%s photo_id=%s", business["_id"], photo_id)
    return {"photos": remaining}
