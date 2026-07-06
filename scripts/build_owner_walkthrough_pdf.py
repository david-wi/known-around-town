#!/usr/bin/env python3
"""Build the public-safe Miami Knows Beauty owner walkthrough PDF."""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# WHY: David needs one stable direct URL for the website-review walkthrough;
# the committed PDF is generated into the public static tree at that URL.
PDF_OUT = ROOT / "backend" / "app" / "static" / "walkthrough" / "mkb-owner-journey.pdf"

# WHY: Keep the PDF source in this script so CI can compare the committed PDF
# against public-safe copy and catch accidental internal review material.
INTRO = (
    "A public-safe summary of the salon owner journey: claim free, manage "
    "the listing, upgrade to Featured, and use the included marketing tools."
)
# WHY: The website page remains the canonical interactive walkthrough; the PDF
# should point reviewers back to it instead of becoming a separate stale source.
LIVE_WALKTHROUGH_URL = "https://miami.knowsbeauty.com/walkthrough"

# WHY: The PDF is intentionally short enough for a founder/site-review pass and
# excludes internal QA screenshots, PM notes, and operational status.
SECTIONS = [
    (
        "1. Find your listing",
        "Prospective owners can inspect their Miami Knows Beauty listing first. "
        "The public listing shows the salon profile, contact actions, neighborhood, "
        "category, and claim path.",
    ),
    (
        "2. Claim it free",
        "Owners can claim their listing without a credit card. The claim form asks "
        "for name, email address, role at the salon, and a short note for review.",
    ),
    (
        "3. Sign in to the dashboard",
        "After approval, owners sign in with an emailed six-digit code. No password "
        "is required.",
    ),
    (
        "4. Manage the profile",
        "The owner dashboard gives the salon a place to review its listing, update "
        "profile details, manage a gallery of up to 12 owner photos, see inquiries, "
        "and keep the page current.",
    ),
    (
        "5. Upgrade to Featured",
        "Featured is $29 per month and takes no booking commission. Featured salons "
        "receive a visible badge, stronger directory visibility, and owner tools.",
    ),
    (
        "6. Use Marketing AI",
        "Featured owners can generate Instagram captions and ad copy in seconds, "
        "using prompts tailored to their salon and offer.",
    ),
    (
        "7. Share the feature",
        "Featured owners can use badge and sharing tools to promote that they are "
        "listed on Miami Knows Beauty and send visitors back to their profile.",
    ),
]

# WHY: Letter size with sub-inch margins keeps the PDF printable while leaving
# enough line length for the owner-journey bullets to fit on one page.
PDF_MARGIN_X_INCHES = 0.72
PDF_MARGIN_Y_INCHES = 0.65


def build() -> None:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    PDF_OUT.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "WalkthroughTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=26,
            textColor=colors.HexColor("#1c1917"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            "WalkthroughSubtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10.5,
            leading=15,
            textColor=colors.HexColor("#57534e"),
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            "WalkthroughHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1c1917"),
            spaceBefore=8,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            "WalkthroughBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#292524"),
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            "WalkthroughSmall",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#78716c"),
            spaceBefore=14,
        )
    )

    story = [
        Paragraph("Miami Knows Beauty Owner Walkthrough", styles["WalkthroughTitle"]),
        Paragraph(INTRO, styles["WalkthroughSubtitle"]),
    ]

    for title, body in SECTIONS:
        story.append(Paragraph(title, styles["WalkthroughHeading"]))
        story.append(Paragraph(body, styles["WalkthroughBody"]))
        story.append(Spacer(1, 2))

    story.append(
        Paragraph(
            f"For the live walkthrough, visit {LIVE_WALKTHROUGH_URL}",
            styles["WalkthroughSmall"],
        )
    )

    doc = SimpleDocTemplate(
        str(PDF_OUT),
        pagesize=letter,
        rightMargin=PDF_MARGIN_X_INCHES * inch,
        leftMargin=PDF_MARGIN_X_INCHES * inch,
        topMargin=PDF_MARGIN_Y_INCHES * inch,
        bottomMargin=PDF_MARGIN_Y_INCHES * inch,
        title="Miami Knows Beauty Owner Walkthrough",
    )
    doc.build(story)


if __name__ == "__main__":
    build()
