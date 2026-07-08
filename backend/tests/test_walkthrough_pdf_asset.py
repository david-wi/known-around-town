import importlib.util
from pathlib import Path

from fastapi.testclient import TestClient
from pypdf import PdfReader

from app.main import app


BACKEND_DIR = Path(__file__).resolve().parent.parent
ROOT = BACKEND_DIR.parent
STATIC_DIR = BACKEND_DIR / "app" / "static"
STATIC_WALKTHROUGH_DIR = STATIC_DIR / "walkthrough"
PUBLIC_PDF_RELATIVE_PATH = Path("walkthrough/mkb-owner-journey.pdf")
PUBLIC_PDF = STATIC_DIR / PUBLIC_PDF_RELATIVE_PATH
PDF_SOURCE = ROOT / "scripts" / "build_owner_walkthrough_pdf.py"
# WHY: all files below backend/app/static are publicly served as /assets, so
# only this reviewed owner walkthrough PDF may be committed as a static PDF.
ALLOWED_STATIC_PDFS = {
    PUBLIC_PDF_RELATIVE_PATH,
}
# WHY: static/walkthrough is a narrow public handoff folder; screenshots,
# drafts, HTML previews, and internal PM PDFs must fail CI there.
ALLOWED_PUBLIC_WALKTHROUGH_ASSETS = {
    Path("mkb-owner-journey.pdf"),
}
# WHY: these text-like static files can carry PM notes even when they are not
# PDFs; binary image/font files are excluded because text decoding is noisy.
TEXT_STATIC_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".svg",
    ".txt",
}
EXPECTED_PUBLIC_PHRASES = {
    "Claim it free",
    "Upgrade to Featured",
    "Use Marketing AI",
    "full gallery of up to 12 unique owner photos that help the salon stand out",
    "sign in with an emailed six-character code",
    "takes no booking commission",
    "https://miami.knowsbeauty.com/walkthrough",
}
INTERNAL_ONLY_TERMS = {
    "internal review",
    "PM review",
    "David's 36",
    "operational status",
    "Stripe/env",
    "Dorian",
    "review packet",
}


def _load_pdf_source():
    spec = importlib.util.spec_from_file_location("build_owner_walkthrough_pdf", PDF_SOURCE)
    assert spec
    assert spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _pdf_text(path: Path) -> str:
    reader = PdfReader(path)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _normalized_text(text: str) -> str:
    return " ".join(text.split())


def test_public_owner_walkthrough_pdf_asset_is_served(mock_db) -> None:
    """The owner walkthrough PDF link David may share must not 404.

    @define KAT-040
    WHY: /walkthrough is already public owner-acquisition copy. The PDF version
    is a public-safe handoff artifact and should keep serving from the stable
    URL that earlier outreach/status updates referenced.
    """
    client = TestClient(app, raise_server_exceptions=False)

    response = client.get("/assets/walkthrough/mkb-owner-journey.pdf")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF-")
    assert PUBLIC_PDF.read_bytes().startswith(b"%PDF-")


def test_public_walkthrough_assets_are_recursively_allowlisted() -> None:
    """Internal walkthrough files include PM notes and must not be public assets.

    @define KAT-040
    """
    public_walkthrough_assets = {
        path.relative_to(STATIC_WALKTHROUGH_DIR)
        for path in STATIC_WALKTHROUGH_DIR.rglob("*")
        if path.is_file()
    }

    assert public_walkthrough_assets == ALLOWED_PUBLIC_WALKTHROUGH_ASSETS


def test_public_static_tree_does_not_publish_private_review_material() -> None:
    """No private review document can hide elsewhere under public /assets.

    @define KAT-040
    """
    public_pdfs = {
        path.relative_to(STATIC_DIR)
        for path in STATIC_DIR.rglob("*.pdf")
        if path.is_file()
    }

    assert public_pdfs == ALLOWED_STATIC_PDFS

    text_assets = [
        path
        for path in STATIC_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in TEXT_STATIC_SUFFIXES
    ]
    for path in text_assets:
        asset_text = path.read_text(encoding="utf-8").lower()
        for term in INTERNAL_ONLY_TERMS:
            assert term.lower() not in asset_text, path


def test_public_owner_walkthrough_pdf_uses_public_safe_copy() -> None:
    """The committed PDF must match the public-safe owner journey copy.

    @define KAT-040
    """
    pdf_source = _load_pdf_source()
    canonical_text = "\n".join(
        [
            "Miami Knows Beauty Owner Walkthrough",
            pdf_source.INTRO,
            pdf_source.LIVE_WALKTHROUGH_URL,
            *[
                item
                for section in pdf_source.SECTIONS
                for item in section
            ],
        ]
    )

    for phrase in EXPECTED_PUBLIC_PHRASES:
        assert phrase in canonical_text

    for term in INTERNAL_ONLY_TERMS:
        assert term.lower() not in canonical_text.lower()

    pdf_text = _pdf_text(PUBLIC_PDF)
    normalized_pdf_text = _normalized_text(pdf_text)

    for line in canonical_text.splitlines():
        assert _normalized_text(line) in normalized_pdf_text

    for phrase in EXPECTED_PUBLIC_PHRASES:
        assert _normalized_text(phrase) in normalized_pdf_text

    for term in INTERNAL_ONLY_TERMS:
        assert term.lower() not in pdf_text.lower()


def test_committed_public_pdf_matches_generated_source(tmp_path) -> None:
    """The committed public PDF should not drift from its source script.

    @define KAT-040
    """
    pdf_source = _load_pdf_source()
    generated_pdf = tmp_path / "mkb-owner-journey.pdf"
    original_pdf_out = pdf_source.PDF_OUT
    pdf_source.PDF_OUT = generated_pdf
    try:
        pdf_source.build()
    finally:
        pdf_source.PDF_OUT = original_pdf_out

    assert _normalized_text(_pdf_text(generated_pdf)) == _normalized_text(_pdf_text(PUBLIC_PDF))
