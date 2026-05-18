"""Validate the raw JSON the LLM returned for each network, drop bad entries,
deduplicate, and write the cleaned-up structure to backend/seed/_real_businesses.json
which seed_miami.py reads on each deploy.

Run inside the backend container:
    python -m seed._validate_real
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

# The slugs we'll accept per network. Anything else gets rejected so the
# seed doesn't end up with categories or neighborhoods that don't exist
# in our category map / neighborhood list.
ALLOWED_NEIGHBORHOODS = {
    "wynwood", "brickell", "south-beach", "coral-gables", "design-district",
    "edgewater", "coconut-grove", "little-havana", "sunny-isles", "aventura",
    "bal-harbour", "midtown", "downtown", "key-biscayne",
}

ALLOWED_CATEGORIES = {
    "beauty":   {"hair", "nails", "spa", "lash-brow", "med-spa", "barber", "makeup", "waxing"},
    "wellness": {"spa", "recovery", "iv-hydration", "yoga-meditation", "holistic",
                  "nutrition", "sleep-stress", "retreats"},
    "health":   {"aesthetics", "metabolic", "longevity", "dental", "mental-health",
                  "fertility", "pt-recovery", "primary-care"},
}

ALLOWED_PRICES = {"$", "$$", "$$$", "$$$$"}

# Some category-slug aliases the LLM is likely to return — map to our exact slugs.
CATEGORY_ALIASES = {
    "beauty": {
        "lashes": "lash-brow",
        "lash": "lash-brow",
        "brow": "lash-brow",
        "lash-and-brow": "lash-brow",
        "medspa": "med-spa",
        "barbershop": "barber",
        "barber-shop": "barber",
    },
    "wellness": {
        "iv": "iv-hydration",
        "iv-therapy": "iv-hydration",
        "yoga": "yoga-meditation",
        "meditation": "yoga-meditation",
        "sound-bath": "yoga-meditation",
    },
    "health": {
        "med-spa": "aesthetics",
        "weight-loss": "metabolic",
        "weight-metabolic": "metabolic",
        "ortho": "dental",
        "orthodontics": "dental",
        "therapy": "mental-health",
        "psych": "mental-health",
        "obgyn": "fertility",
        "physical-therapy": "pt-recovery",
        "chiropractic": "pt-recovery",
        "chiropractor": "pt-recovery",
        "concierge": "primary-care",
        "primary": "primary-care",
    },
}

NEIGHBORHOOD_ALIASES = {
    "sunny-isles-beach": "sunny-isles",
    "south-of-fifth": "south-beach",
    "sobe": "south-beach",
    "miami-beach": "south-beach",
    "midbeach": "south-beach",
    "mid-beach": "south-beach",
}

SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _slugify(text: str) -> str:
    t = text.lower()
    t = re.sub(r"&", " and ", t)
    t = re.sub(r"[^a-z0-9]+", "-", t)
    return t.strip("-")[:80]


def _normalize_phone(s: Any) -> str | None:
    if not s or not isinstance(s, str):
        return None
    digits = re.sub(r"\D", "", s)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return s.strip()  # keep original if it's not a clean 10-digit US number
    return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"


def _strip_codefence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _try_parse_json_array(text: str) -> List[Dict[str, Any]]:
    """Parse a JSON array, with two recovery strategies for messy LLM output:
    1) strip leading/trailing prose around the [...] block
    2) if the array got truncated mid-entry, find the last complete }, then close ]
    """
    text = _strip_codefence(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strategy 1: clip to first [ and last ]
    first = text.find("[")
    last = text.rfind("]")
    if first >= 0 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except json.JSONDecodeError:
            pass

    # Strategy 2: array got truncated mid-entry. Walk through and find the
    # last complete top-level object (close brace at depth 1) and rebuild
    # a valid array ending there.
    if first < 0:
        return []
    snippet = text[first:]
    depth = 0
    last_complete_end = -1
    in_string = False
    escape = False
    for i, ch in enumerate(snippet):
        if escape:
            escape = False; continue
        if ch == "\\" and in_string:
            escape = True; continue
        if ch == '"':
            in_string = not in_string; continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # We just closed a top-level object inside the array
                last_complete_end = i
    if last_complete_end >= 0:
        return json.loads(snippet[: last_complete_end + 1] + "]")
    return []


def validate(raw_text: str, network: str) -> List[Dict[str, Any]]:
    data = _try_parse_json_array(raw_text)
    if not data:
        raise SystemExit(f"Could not parse JSON for {network}")

    if not isinstance(data, list):
        raise SystemExit(f"Expected a JSON array for {network}, got {type(data).__name__}")

    cats = ALLOWED_CATEGORIES[network]
    cat_aliases = CATEGORY_ALIASES.get(network, {})

    cleaned: Dict[str, Dict[str, Any]] = {}
    rejects: List[Dict[str, Any]] = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            rejects.append({"reason": "no-name", "entry": entry}); continue

        slug = entry.get("slug") or _slugify(name)
        slug = slug.lower().strip()
        if not SLUG_PATTERN.match(slug):
            slug = _slugify(slug)

        nb_raw = (entry.get("neighborhood") or "").strip().lower()
        # Normalize "South Beach" -> "south-beach", "Sunny Isles Beach" -> "sunny-isles-beach"
        nb = re.sub(r"[^a-z0-9]+", "-", nb_raw).strip("-")
        nb = NEIGHBORHOOD_ALIASES.get(nb, nb)
        if nb not in ALLOWED_NEIGHBORHOODS:
            rejects.append({"reason": f"neighborhood:{nb}", "entry": entry}); continue

        cat_raw = (entry.get("category") or "").strip().lower()
        cat = re.sub(r"[^a-z0-9]+", "-", cat_raw).strip("-")
        cat = cat_aliases.get(cat, cat)
        if cat not in cats:
            rejects.append({"reason": f"category:{cat}", "entry": entry}); continue

        price = entry.get("price_cues") or "$$"
        if price not in ALLOWED_PRICES:
            price = "$$"

        short_desc = (entry.get("short_description") or "").strip()
        if not short_desc:
            rejects.append({"reason": "no-description", "entry": entry}); continue

        # Build the cleaned entry
        clean = {
            "slug": slug,
            "name": name,
            "neighborhood_slug": nb,
            "category_slug": cat,
            "price_cues": price,
            "short_description": short_desc,
            "address": (entry.get("address") or "").strip() or None,
            "phone": _normalize_phone(entry.get("phone")),
            "website": (entry.get("website") or None) or None,
            "instagram": (entry.get("instagram") or None),
            "editors_pick": bool(entry.get("editors_pick", False)),
            "premium": bool(entry.get("premium", False)),
        }
        # Drop pure duplicates by slug
        cleaned[slug] = clean

    print(f"  {network}: {len(cleaned)} clean / {len(data)} returned / {len(rejects)} rejected", file=sys.stderr)
    if rejects:
        print(f"    rejects: {[r['reason'] for r in rejects[:8]]}", file=sys.stderr)
    return list(cleaned.values())


def main() -> None:
    out: Dict[str, List[Dict[str, Any]]] = {}
    for net in ("beauty", "wellness", "health"):
        merged: Dict[str, Dict[str, Any]] = {}
        # Read every round we have (raw-<net>.json, raw-<net>-2.json, raw-<net>-3.json, ...)
        for path in sorted(Path("/tmp").glob(f"raw-{net}*.json")):
            raw_text = path.read_text()
            for entry in validate(raw_text, net):
                merged.setdefault(entry["slug"], entry)
        out[net] = list(merged.values())

    dest = Path(__file__).parent / "_real_businesses.json"
    dest.write_text(json.dumps(out, indent=2))
    totals = " / ".join(f"{n}={len(v)}" for n, v in out.items())
    print(f"\nWrote {dest} — {totals}", file=sys.stderr)


if __name__ == "__main__":
    main()
