"""Tests for owner photo upload/delete and the public /media/{id} serving route.

Coverage:
  POST   /api/v1/owner/photos          — auth, no business, JPEG/PNG/WebP, bad MIME,
                                         oversized, hero promotion, photo-count limit
  DELETE /api/v1/owner/photos/{id}     — auth, missing photo, bad id, hero re-assignment
  GET    /media/{id}                   — happy path, bad id, not found
"""

from __future__ import annotations

import io
import struct
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi.testclient import TestClient


# ─── helpers ────────────────────────────────────────────────────────────────

def _make_client(db):
    from app.main import app
    return TestClient(app, raise_server_exceptions=False)


def _signed_cookie(email: str) -> str:
    from app.services.owner_auth import sign_session
    return sign_session(email)


async def _insert_business(db, *, email: str, photos: list | None = None) -> str:
    import uuid
    biz_id = str(uuid.uuid4())
    doc: dict[str, Any] = {
        "_id": biz_id,
        "name": "Photo Test Salon",
        "slug": "photo-test-salon",
        "claimed_email": email,
        "featured": {"tier": "free", "enabled": False},
        "photos": photos or [],
    }
    await db.businesses.insert_one(doc)
    return biz_id


def _jpeg_bytes() -> bytes:
    """Minimal valid JPEG (3×3 pixel, 1×1 MCU block)."""
    # Just the magic bytes — enough to pass the detector check in the route.
    return b"\xff\xd8\xff\xe0" + b"\x00" * 128


def _png_bytes() -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * 128


def _webp_bytes() -> bytes:
    # RIFF header + "WEBP" fourcc at offset 8
    return b"RIFF\x40\x00\x00\x00WEBP" + b"\x00" * 64


def _text_bytes() -> bytes:
    return b"Hello, I am not an image."


def _mock_gridfs_bucket(fake_id: ObjectId | None = None):
    """Return a mock GridFS bucket with sensible defaults."""
    if fake_id is None:
        fake_id = ObjectId()

    bucket = MagicMock()
    bucket.upload_from_stream = AsyncMock(return_value=fake_id)
    bucket.delete = AsyncMock(return_value=None)

    # open_download_stream returns a mock grid-out object
    grid_out = MagicMock()
    grid_out.metadata = {"content_type": "image/jpeg"}
    # WHY: readchunk must yield data once then return b"" to signal EOF so the
    # streaming response terminates cleanly.
    grid_out.readchunk = AsyncMock(side_effect=[b"\xff\xd8\xff" + b"\x00" * 32, b""])
    bucket.open_download_stream = AsyncMock(return_value=grid_out)

    return bucket


# ─── Upload endpoint ─────────────────────────────────────────────────────────

class TestPhotoUpload:
    @pytest.fixture
    def client(self, seeded_db):
        return _make_client(seeded_db)

    def test_upload_requires_auth(self, client, seeded_db):
        """No session cookie → 401."""
        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
            )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_upload_404_when_no_business(self, client, seeded_db):
        """Signed in but no claimed business → 404."""
        email = "orphan@test.com"
        cookie = _signed_cookie(email)
        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("photo.jpg", _jpeg_bytes(), "image/jpeg")},
                cookies={"kb_owner_session": cookie},
            )
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_jpeg_succeeds(self, client, seeded_db):
        """Valid JPEG upload → 200, photo added to business doc."""
        email = "jpegowner@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)
        fake_id = ObjectId()

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket(fake_id)):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("salon.jpg", _jpeg_bytes(), "image/jpeg")},
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 200
        data = r.json()
        assert len(data["photos"]) == 1
        photo = data["photos"][0]
        assert photo["url"] == f"/media/{fake_id}"
        # WHY: first photo must be hero so it shows on the listing immediately.
        assert photo["is_hero"] is True

    @pytest.mark.asyncio
    async def test_upload_png_succeeds(self, client, seeded_db):
        """PNG upload is accepted."""
        email = "pngowner@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)
        fake_id = ObjectId()

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket(fake_id)):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("logo.png", _png_bytes(), "image/png")},
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_webp_succeeds(self, client, seeded_db):
        """WebP upload is accepted."""
        email = "webpowner@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)
        fake_id = ObjectId()

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket(fake_id)):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("salon.webp", _webp_bytes(), "image/webp")},
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_rejects_text_file_spoofed_as_image(self, client, seeded_db):
        """Spoofed MIME type with text bytes → 415 (magic-byte check catches it)."""
        email = "spoof@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.post(
                "/api/v1/owner/photos",
                # Claiming image/jpeg but the bytes are text
                files={"file": ("evil.jpg", _text_bytes(), "image/jpeg")},
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 415

    @pytest.mark.asyncio
    async def test_upload_rejects_oversized_file(self, client, seeded_db):
        """File over 10 MB → 413."""
        email = "bigfile@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)

        # WHY: magic bytes at the start make it look like a real JPEG so the
        # test exercises the size check rather than the MIME check.
        big_data = _jpeg_bytes() + b"\x00" * (11 * 1024 * 1024)

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("huge.jpg", big_data, "image/jpeg")},
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 413

    @pytest.mark.asyncio
    async def test_upload_second_photo_not_hero(self, client, seeded_db):
        """Second upload should not claim hero status — the first photo keeps it."""
        email = "twophoto@test.com"
        first_id = ObjectId()
        await _insert_business(seeded_db, email=email, photos=[
            {"url": f"/media/{first_id}", "alt": "", "caption": "", "order": 0, "is_hero": True},
        ])
        cookie = _signed_cookie(email)
        second_id = ObjectId()

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket(second_id)):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("second.jpg", _jpeg_bytes(), "image/jpeg")},
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 200
        photos = r.json()["photos"]
        assert len(photos) == 2
        heroes = [p for p in photos if p.get("is_hero")]
        assert len(heroes) == 1
        assert heroes[0]["url"] == f"/media/{first_id}"

    @pytest.mark.asyncio
    async def test_upload_rejects_when_at_limit(self, client, seeded_db):
        """12 photos already → 409."""
        email = "full@test.com"
        existing_photos = [
            {"url": f"/media/{ObjectId()}", "alt": "", "caption": "", "order": i, "is_hero": i == 0}
            for i in range(12)
        ]
        await _insert_business(seeded_db, email=email, photos=existing_photos)
        cookie = _signed_cookie(email)

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.post(
                "/api/v1/owner/photos",
                files={"file": ("one-more.jpg", _jpeg_bytes(), "image/jpeg")},
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 409


# ─── Delete endpoint ─────────────────────────────────────────────────────────

class TestPhotoDelete:
    @pytest.fixture
    def client(self, seeded_db):
        return _make_client(seeded_db)

    def test_delete_requires_auth(self, client, seeded_db):
        """No session cookie → 401."""
        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.delete(f"/api/v1/owner/photos/{ObjectId()}")
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_delete_success(self, client, seeded_db):
        """Delete an existing photo → 200, photo removed from doc, GridFS.delete called."""
        email = "deleter@test.com"
        photo_id = ObjectId()
        await _insert_business(seeded_db, email=email, photos=[
            {"url": f"/media/{photo_id}", "alt": "", "caption": "", "order": 0, "is_hero": True},
        ])
        cookie = _signed_cookie(email)
        bucket = _mock_gridfs_bucket()

        with patch("app.database.get_gridfs_bucket", return_value=bucket):
            r = client.delete(
                f"/api/v1/owner/photos/{photo_id}",
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 200
        assert r.json()["photos"] == []
        # Confirm GridFS.delete was called with the correct ObjectId
        bucket.delete.assert_awaited_once_with(photo_id)

    @pytest.mark.asyncio
    async def test_delete_promotes_next_photo_to_hero(self, client, seeded_db):
        """Deleting the hero photo makes the next one the new hero."""
        email = "promotetest@test.com"
        hero_id   = ObjectId()
        second_id = ObjectId()
        await _insert_business(seeded_db, email=email, photos=[
            {"url": f"/media/{hero_id}",   "alt": "", "caption": "", "order": 0, "is_hero": True},
            {"url": f"/media/{second_id}", "alt": "", "caption": "", "order": 1, "is_hero": False},
        ])
        cookie = _signed_cookie(email)

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.delete(
                f"/api/v1/owner/photos/{hero_id}",
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 200
        remaining = r.json()["photos"]
        assert len(remaining) == 1
        # WHY: the second photo must now be marked is_hero=True — the listing
        # header shows no image at all if no photo is the hero.
        assert remaining[0]["is_hero"] is True
        assert remaining[0]["url"] == f"/media/{second_id}"

    @pytest.mark.asyncio
    async def test_delete_400_on_invalid_id(self, client, seeded_db):
        """Malformed photo id → 400."""
        email = "badid@test.com"
        await _insert_business(seeded_db, email=email)
        cookie = _signed_cookie(email)

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.delete(
                "/api/v1/owner/photos/not-a-valid-objectid",
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_404_when_photo_not_on_business(self, client, seeded_db):
        """Trying to delete another business's photo → 404 (auth check)."""
        email = "owner-a@test.com"
        await _insert_business(seeded_db, email=email, photos=[
            {"url": f"/media/{ObjectId()}", "alt": "", "caption": "", "order": 0, "is_hero": True},
        ])
        cookie = _signed_cookie(email)
        # A different photo_id that doesn't belong to this owner
        unrelated_id = ObjectId()

        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.delete(
                f"/api/v1/owner/photos/{unrelated_id}",
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_succeeds_even_if_gridfs_delete_fails(self, client, seeded_db):
        """GridFS.delete raising an exception must not fail the delete request.

        WHY: the business document is the source of truth — if the file is
        already gone from GridFS (e.g. after manual cleanup), the photo should
        still be removable from the listing without a 500 error.
        """
        email = "gridfsfail@test.com"
        photo_id = ObjectId()
        await _insert_business(seeded_db, email=email, photos=[
            {"url": f"/media/{photo_id}", "alt": "", "caption": "", "order": 0, "is_hero": True},
        ])
        cookie = _signed_cookie(email)

        bucket = _mock_gridfs_bucket()
        bucket.delete = AsyncMock(side_effect=Exception("GridFS error"))

        with patch("app.database.get_gridfs_bucket", return_value=bucket):
            r = client.delete(
                f"/api/v1/owner/photos/{photo_id}",
                cookies={"kb_owner_session": cookie},
            )

        assert r.status_code == 200
        assert r.json()["photos"] == []


# ─── Media serving endpoint ──────────────────────────────────────────────────

class TestMediaServing:
    @pytest.fixture
    def client(self, seeded_db):
        return _make_client(seeded_db)

    @pytest.mark.asyncio
    async def test_serve_photo_happy_path(self, client, seeded_db):
        """Valid photo_id → 200 with image bytes and correct headers."""
        photo_id = ObjectId()
        bucket = _mock_gridfs_bucket(photo_id)

        with patch("app.database.get_gridfs_bucket", return_value=bucket):
            r = client.get(f"/media/{photo_id}")

        assert r.status_code == 200
        assert "image/" in r.headers.get("content-type", "")
        # WHY: immutable cache headers are critical — browsers re-fetch images
        # with every page load if there is no long cache header.
        cache = r.headers.get("cache-control", "")
        assert "immutable" in cache
        assert "max-age=31536000" in cache

    def test_serve_photo_400_on_bad_id(self, client, seeded_db):
        """Malformed id (not a 24-hex ObjectId) → 400."""
        with patch("app.database.get_gridfs_bucket", return_value=_mock_gridfs_bucket()):
            r = client.get("/media/not-an-objectid")
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_serve_photo_404_when_not_in_gridfs(self, client, seeded_db):
        """Valid ObjectId but not in GridFS → 404."""
        photo_id = ObjectId()
        bucket = _mock_gridfs_bucket()
        bucket.open_download_stream = AsyncMock(side_effect=Exception("not found"))

        with patch("app.database.get_gridfs_bucket", return_value=bucket):
            r = client.get(f"/media/{photo_id}")

        assert r.status_code == 404


# ─── Magic-byte detector unit tests ─────────────────────────────────────────

class TestMimeDetector:
    """Unit tests for the _detect_mime helper — these run without HTTP overhead."""

    def _detect(self, data: bytes):
        from app.routes.api.v1.owner_photos import _detect_mime
        return _detect_mime(data)

    def test_jpeg_detected(self):
        assert self._detect(_jpeg_bytes()) == "image/jpeg"

    def test_png_detected(self):
        assert self._detect(_png_bytes()) == "image/png"

    def test_webp_detected(self):
        assert self._detect(_webp_bytes()) == "image/webp"

    def test_text_returns_none(self):
        assert self._detect(_text_bytes()) is None

    def test_riff_without_webp_fourcc_returns_none(self):
        """RIFF prefix without WEBP at offset 8 must not be accepted (e.g. WAV)."""
        wav_bytes = b"RIFF\x40\x00\x00\x00WAVE" + b"\x00" * 32
        assert self._detect(wav_bytes) is None

    def test_empty_bytes_returns_none(self):
        assert self._detect(b"") is None
