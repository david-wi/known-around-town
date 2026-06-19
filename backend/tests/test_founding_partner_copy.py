"""Guards that Founding Partner copy never promises permanence or a price lock.

The owner instruction is to never promise "forever" or "locked-in" anything.
The Founding Partner concept itself stays (gold badge, scarcity of spots), but
the badge must not be described as "permanent"/"forever" and the offer must not
imply a price that is locked against future increases. These are pure-string
assertions on the copy default; the corresponding template wording is kept in
sync with copy.py.
"""

from app.services.copy import DEFAULTS

# WHY: words that would re-introduce a permanence or price-lock promise into the
# claim copy. Substring match is enough — any of these in the claim body is a
# regression of the owner's "never promise forever" instruction.
_FORBIDDEN_IN_CLAIM_BODY = ("permanent", "forever", "locked-in", "locked in", "price lock")


def test_claim_body_still_names_founding_partner_and_badge():
    body = DEFAULTS["business.claim.body"]
    # The concept itself is retained — we only removed the over-promises.
    assert "Founding Partner" in body
    assert "gold badge" in body


def test_claim_body_has_no_permanence_or_price_lock_promise():
    body = DEFAULTS["business.claim.body"].lower()
    for phrase in _FORBIDDEN_IN_CLAIM_BODY:
        assert phrase not in body, f"claim body must not promise {phrase!r}"
