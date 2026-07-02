"""VAPI-backed voice provisioning for the Concierge tier.

Concierge salons get a dedicated phone number and AI receptionist that
answers 24/7. Callers hear the salon's name, hours, services, and can
leave a message or get connected. All provisioning goes through the VAPI
REST API at https://api.vapi.ai.

Two public functions:
  provision_salon_receptionist(db, business_id)
    → buys a number, creates an assistant, wires them together, writes
      voice_phone_number / vapi_phone_number_id / vapi_assistant_id back
      to the business document.

  deprovision_salon_receptionist(db, business_id)
    → deletes the VAPI assistant and phone number, clears the three voice
      fields, downgrades the tier to premium.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import httpx

from app.config import get_settings
from app.mongo_ids import business_id_value

log = logging.getLogger(__name__)

# WHY: base URL factored out so tests can easily patch it to a mock server.
_VAPI_BASE = "https://api.vapi.ai"

# WHY: prefer area code 669 (San Jose/South Bay) because the Miami beauty
# market has a large diaspora from that region and a Bay-area number feels
# familiar without being a local Miami code — which could create confusion
# if callers assume it's a direct line to the salon. Fallback is any US number.
_PREFERRED_AREA_CODE = "669"

# WHY: ElevenLabs voice "Rachel" (voiceId 21m00Tcm4TlvDq8ikWAM) is warm,
# professional, and clearly female — the right fit for a Miami beauty salon
# receptionist. Hardcoded because it's a deliberate creative choice, not
# something that should vary per-salon.
_ELEVENLABS_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

_DAY_LABELS = {
    "mon": "Monday",
    "tue": "Tuesday",
    "wed": "Wednesday",
    "thu": "Thursday",
    "fri": "Friday",
    "sat": "Saturday",
    "sun": "Sunday",
}


def _get_api_key() -> str:
    """Read VAPI_API_KEY from environment at call time (not module load).

    WHY: reading at call time (not module load) means tests can set
    VAPI_API_KEY=test-key in conftest.py without import-time side effects.
    """
    key = os.environ.get("VAPI_API_KEY", "")
    if not key:
        raise RuntimeError(
            "VAPI_API_KEY is not set. Set it in the environment or .env file."
        )
    return key


def _format_hours(hours: list[Dict[str, Any]]) -> str:
    """Convert the stored hours list into a human-readable multiline block.

    Example output:
      Monday: 9:00 AM – 6:00 PM
      Tuesday: 9:00 AM – 6:00 PM
      Wednesday: Closed
    """
    if not hours:
        return "Hours not available — please call us for current hours."

    lines: list[str] = []
    for entry in hours:
        day_label = _DAY_LABELS.get(entry.get("day", ""), entry.get("day", ""))
        if entry.get("closed"):
            lines.append(f"{day_label}: Closed")
        else:
            opens = _fmt_time(entry.get("opens_at"))
            closes = _fmt_time(entry.get("closes_at"))
            if opens and closes:
                lines.append(f"{day_label}: {opens} – {closes}")
            else:
                lines.append(f"{day_label}: Hours not available")
    return "\n".join(lines)


def _fmt_time(t: Optional[str]) -> Optional[str]:
    """Convert 24-h "HH:MM" to 12-h "H:MM AM/PM".

    WHY: the stored format matches HTML <input type="time"> output which
    is always 24-h. Phone callers hear better with 12-h AM/PM notation.
    Returns None if the input is missing or malformed.
    """
    if not t:
        return None
    try:
        h, m = t.split(":")
        hour = int(h)
        minute = int(m)
        period = "AM" if hour < 12 else "PM"
        hour_12 = hour % 12 or 12
        return f"{hour_12}:{minute:02d} {period}"
    except (ValueError, AttributeError):
        return t  # Return as-is if we can't parse it


def _format_services(services: list[Dict[str, Any]]) -> str:
    """Format the services list for inclusion in the assistant prompt.

    WHY: the prompt just needs a plain list the assistant can reference when
    a caller asks "do you do X?" — not the full Pydantic schema. We include
    price ranges if available so the assistant can give rough price guidance
    without inventing numbers.
    """
    if not services:
        return "Ask us about our full menu of services."

    lines: list[str] = []
    for svc in services[:20]:  # WHY: cap at 20 — very long service menus bloat the prompt
        name = svc.get("name", "")
        if not name:
            continue
        price_from = svc.get("price_from")
        price_to = svc.get("price_to")
        if price_from and price_to:
            lines.append(f"- {name}: ${price_from:.0f}–${price_to:.0f}")
        elif price_from:
            lines.append(f"- {name}: from ${price_from:.0f}")
        else:
            lines.append(f"- {name}")
    return "\n".join(lines) if lines else "Ask us about our full menu of services."


def _build_system_prompt(business: Dict[str, Any]) -> str:
    """Build the VAPI assistant system prompt from the business document."""
    name = business.get("name", "the salon")
    neighborhood = business.get("neighborhood_slugs", [""])[0].replace("-", " ").title() if business.get("neighborhood_slugs") else "Miami"
    phone = business.get("phone") or "our salon"

    # Build address string
    addr = business.get("address") or {}
    if isinstance(addr, dict):
        street = addr.get("street", "")
        city = addr.get("city", "Miami")
        state = addr.get("state", "FL")
        postal = addr.get("postal_code", "")
        address_parts = [p for p in [street, city, state, postal] if p]
        address_str = ", ".join(address_parts) if address_parts else "Miami, FL"
    else:
        address_str = "Miami, FL"

    # Determine primary category label
    category_slugs = business.get("category_slugs") or []
    category_label = category_slugs[0].replace("-", " ") if category_slugs else "beauty"

    hours_block = _format_hours(business.get("hours") or [])
    services_block = _format_services(business.get("services") or [])

    return f"""You are the AI receptionist for {name}, a {category_label} salon located in {neighborhood}, Miami.

SALON INFORMATION:
- Name: {name}
- Address: {address_str}
- Phone: {phone} (for call transfers if needed)
- Neighborhood: {neighborhood}

HOURS:
{hours_block}

SERVICES:
{services_block}

YOUR ROLE:
Answer questions about hours, services, and pricing. For appointment booking, let callers know the team will follow up. Never make up information you don't have — always say "Let me have our team follow up on that."

IMPORTANT RULES:
- Be warm, professional, and brief
- Never quote exact prices you're unsure about
- Always offer to take a message or have someone call back
- First message: "{name}, how can I help you today?"
"""


def _build_assistant_payload(business: Dict[str, Any]) -> Dict[str, Any]:
    """Build the VAPI POST /assistant request body."""
    name = business.get("name", "the salon")
    system_prompt = _build_system_prompt(business)
    first_message = f"{name}, how can I help you today?"
    settings = get_settings()

    return {
        "name": f"{name} — AI Receptionist",
        "model": {
            "provider": settings.vapi_assistant_model_provider,
            "model": settings.vapi_assistant_model,
            # WHY: 0.4 is warm enough for natural conversation but low enough to
            # keep responses factual and on-topic — the assistant shouldn't
            # improvise information about services or prices.
            "temperature": 0.4,
            "messages": [
                {"role": "system", "content": system_prompt},
            ],
        },
        "transcriber": {
            "provider": "deepgram",
            # WHY: nova-2 is Deepgram's highest-accuracy English model as of mid-2025.
            # Beauty salon callers often use specialized vocabulary (shellac, balayage,
            # etc.) that benefits from the best available transcription.
            "model": "nova-2",
            "language": "en",
        },
        "voice": {
            "provider": "11labs",
            "voiceId": _ELEVENLABS_VOICE_ID,
        },
        "firstMessage": first_message,
        # WHY: endCallFunctionEnabled lets the assistant say goodbye and hang up
        # cleanly instead of leaving the caller on dead air. Without this the call
        # has to be ended by the caller's own hang-up or a timeout.
        "endCallFunctionEnabled": True,
        # WHY: recordingEnabled=True gives the salon owner a call log for quality
        # review and dispute resolution. Callers hear a standard "this call may
        # be recorded" disclosure automatically when recording is on.
        "recordingEnabled": True,
    }


async def provision_salon_receptionist(db: Any, business_id: str) -> Dict[str, Any]:
    """Provision a VAPI phone number and assistant for a Concierge-tier salon.

    Steps:
      1. Fetch the business document and validate it exists.
      2. Build the assistant payload from salon data.
      3. POST /assistant → get assistant_id.
      4. POST /phone-number → buy a number (area code 669 preferred).
      5. PATCH /phone-number/{id} → wire assistant to the phone number.
      6. Write voice_phone_number, vapi_phone_number_id, vapi_assistant_id
         back to the business document.
      7. Return {"phone_number": ..., "assistant_id": ..., "phone_number_id": ...}

    Raises:
      ValueError: if the business does not exist.
      httpx.HTTPStatusError: if any VAPI API call fails.
    """
    business = await db.businesses.find_one({"_id": business_id_value(business_id)})
    if not business:
        raise ValueError(f"Business {business_id!r} not found")

    # WHY: idempotency guard — if the business already has a provisioned phone
    # number, a second call would buy another number from Twilio via VAPI and
    # orphan the first one, which VAPI continues to bill for indefinitely.
    # Force the caller to deprovision before re-provisioning.
    if business.get("vapi_phone_number_id"):
        raise ValueError(
            f"Business {business_id!r} already has a provisioned receptionist. "
            "Deprovision it first before re-provisioning."
        )

    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    assistant_payload = _build_assistant_payload(business)

    async with httpx.AsyncClient(base_url=_VAPI_BASE, timeout=30.0) as client:
        # Steps 1-3 are wrapped in a try/except so that any failure in the
        # wiring step (Step 3) cleans up the already-created VAPI resources.
        # WHY: if Step 3 raises, the assistant and phone number from Steps 1-2
        # are orphaned — VAPI bills for them forever, and the DB record is left
        # broken. Cleaning up here keeps VAPI and the DB consistent.
        assistant_id: str = ""
        phone_number_id: str = ""
        raw_number: str = ""
        try:
            # Step 1: Create the assistant
            log.info("Creating VAPI assistant for business %s", business_id)
            resp = await client.post("/assistant", json=assistant_payload, headers=headers)
            resp.raise_for_status()
            assistant_data = resp.json()
            assistant_id = assistant_data["id"]
            log.info("Created VAPI assistant %s for business %s", assistant_id, business_id)

            # Step 2: Buy a phone number — prefer area code 669, fall back to any US number
            # WHY: two attempts — preferred area code first, then fallback — because VAPI
            # sometimes has no inventory for a specific area code and would return 400
            # rather than automatically choosing an alternative.
            for area_code in [_PREFERRED_AREA_CODE, None]:
                phone_payload: Dict[str, Any] = {"provider": "twilio"}
                if area_code:
                    phone_payload["areaCode"] = area_code
                log.info("Requesting VAPI phone number (areaCode=%s)", area_code)
                try:
                    presp = await client.post("/phone-number", json=phone_payload, headers=headers)
                    presp.raise_for_status()
                    phone_data = presp.json()
                    phone_number_id = phone_data["id"]
                    raw_number = phone_data.get("number", "")
                    log.info("Bought VAPI phone number %s (%s)", raw_number, phone_number_id)
                    break
                except httpx.HTTPStatusError as e:
                    if area_code is not None:
                        log.warning(
                            "Area code %s not available (%s), retrying without preference",
                            area_code,
                            e.response.status_code,
                        )
                        continue
                    raise  # fallback also failed — re-raise

            # Step 3: Wire the assistant to the phone number
            log.info("Wiring assistant %s to phone number %s", assistant_id, phone_number_id)
            patch_resp = await client.patch(
                f"/phone-number/{phone_number_id}",
                json={"assistantId": assistant_id},
                headers=headers,
            )
            patch_resp.raise_for_status()

        except Exception:
            # Clean up any VAPI resources that were already created so they don't
            # become orphaned billable resources.
            if phone_number_id:
                log.warning(
                    "Provisioning failed — deleting orphaned phone number %s", phone_number_id
                )
                try:
                    await client.delete(f"/phone-number/{phone_number_id}", headers=headers)
                except Exception:
                    log.exception(
                        "Failed to clean up orphaned phone number %s", phone_number_id
                    )
            if assistant_id:
                log.warning(
                    "Provisioning failed — deleting orphaned assistant %s", assistant_id
                )
                try:
                    await client.delete(f"/assistant/{assistant_id}", headers=headers)
                except Exception:
                    log.exception(
                        "Failed to clean up orphaned assistant %s", assistant_id
                    )
            raise

    # Format the number as "(NXX) NXX-XXXX" if it looks like a 10-digit US E.164 number
    formatted_number = _format_us_phone(raw_number)

    # Write back to the business document
    from datetime import datetime, timezone
    await db.businesses.update_one(
        {"_id": business_id},
        {
            "$set": {
                "voice_phone_number": formatted_number,
                "vapi_phone_number_id": phone_number_id,
                "vapi_assistant_id": assistant_id,
                "featured.tier": "concierge",
                "featured.enabled": True,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )

    log.info(
        "Provisioning complete for business %s: phone=%s assistant=%s",
        business_id, formatted_number, assistant_id,
    )
    return {
        "phone_number": formatted_number,
        "assistant_id": assistant_id,
        "phone_number_id": phone_number_id,
    }


async def deprovision_salon_receptionist(db: Any, business_id: str) -> None:
    """Remove the VAPI assistant and phone number for a salon.

    Fetches the stored IDs from the business document, calls the VAPI DELETE
    endpoints, then clears the three voice fields and downgrades the tier to
    premium. Errors from VAPI (e.g. the resource was already deleted) are
    logged but do not abort the cleanup — we always clear the DB fields so
    the app doesn't get stuck in a half-deprovisioned state.

    Raises:
      ValueError: if the business does not exist.
    """
    business = await db.businesses.find_one({"_id": business_id_value(business_id)})
    if not business:
        raise ValueError(f"Business {business_id!r} not found")

    assistant_id = business.get("vapi_assistant_id")
    phone_number_id = business.get("vapi_phone_number_id")

    api_key = _get_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(base_url=_VAPI_BASE, timeout=30.0) as client:
        if assistant_id:
            log.info("Deleting VAPI assistant %s for business %s", assistant_id, business_id)
            try:
                resp = await client.delete(f"/assistant/{assistant_id}", headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                # WHY: log and continue rather than raising — if VAPI already
                # deleted the resource we still want to clear the DB fields
                # so the salon isn't stuck with stale IDs forever.
                log.warning(
                    "Failed to delete VAPI assistant %s: %s — continuing cleanup",
                    assistant_id, e.response.status_code,
                )

        if phone_number_id:
            log.info("Deleting VAPI phone number %s for business %s", phone_number_id, business_id)
            try:
                resp = await client.delete(f"/phone-number/{phone_number_id}", headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                log.warning(
                    "Failed to delete VAPI phone number %s: %s — continuing cleanup",
                    phone_number_id, e.response.status_code,
                )

    from datetime import datetime, timezone
    await db.businesses.update_one(
        {"_id": business_id},
        {
            "$set": {
                # WHY: reset to "free" rather than "premium" — the salon was on
                # Concierge specifically for the AI receptionist feature. Removing
                # that feature should return the listing to its baseline free state,
                # not silently grant a paid "premium" tier the owner never subscribed
                # to. A premium upgrade should only happen through an explicit Stripe
                # subscription, not as a side effect of deprovisioning.
                "featured.tier": "free",
                "updated_at": datetime.now(timezone.utc),
            },
            "$unset": {
                "voice_phone_number": "",
                "vapi_phone_number_id": "",
                "vapi_assistant_id": "",
            },
        },
    )
    log.info("Deprovisioning complete for business %s", business_id)


def _format_us_phone(raw: str) -> str:
    """Format a raw E.164 number like +16692328894 to (669) 232-8894.

    WHY: VAPI returns numbers in E.164 (+1XXXXXXXXXX). The formatted version
    is what the salon displays on marketing materials and what callers read.
    Returns the raw string unchanged if it doesn't look like a 10-digit US number.
    """
    if not raw:
        return raw
    # Strip +1 prefix
    digits = raw.lstrip("+")
    if digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10 and digits.isdigit():
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw
