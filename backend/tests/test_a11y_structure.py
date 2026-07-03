"""Regression guards for semantic accessibility structure on public pages."""

from __future__ import annotations

from html.parser import HTMLParser

import pytest
from fastapi.testclient import TestClient


class _StructureParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.footer_headings: list[str] = []
        self.main_complementary: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        in_main = "main" in self.stack
        in_footer = "footer" in self.stack

        if in_footer and tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.footer_headings.append(tag)

        if in_main and (tag == "aside" or attrs_dict.get("role") == "complementary"):
            label = attrs_dict.get("aria-label") or attrs_dict.get("class") or tag
            self.main_complementary.append(label)

        self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index] == tag:
                del self.stack[index:]
                return


def _parse(html: str) -> _StructureParser:
    parser = _StructureParser()
    parser.feed(html)
    return parser


@pytest.fixture
def client(seeded_db) -> TestClient:
    from app.main import app

    return TestClient(app)


def _get(client: TestClient, path: str) -> str:
    response = client.get(path, headers={"host": "miami.knowsbeauty.localhost"})
    assert response.status_code == 200, response.text
    return response.text


def test_public_pages_do_not_emit_nested_complementary_landmarks(client: TestClient):
    """# @define-test KAT-076

    Home/listing sidebars are visually supporting content inside the primary
    page flow. They must not become nested complementary landmarks, which axe
    flags and screen-reader landmark navigation exposes as noisy structure.
    """
    pages = {
        "home": _get(client, "/"),
        "business": _get(client, "/b/igk-salon-south-beach"),
    }

    for label, html in pages.items():
        parser = _parse(html)
        assert parser.main_complementary == [], (
            f"{label} has nested complementary landmarks inside <main>: "
            f"{parser.main_complementary}"
        )


def test_footer_labels_do_not_create_skipped_heading_levels(client: TestClient):
    """# @define-test KAT-076

    Footer column labels are navigation labels, not page-section headings.
    Keeping them out of the heading outline avoids the h1 -> h4 skip that axe
    reported on every public page.
    """
    pages = {
        "home": _get(client, "/"),
        "business": _get(client, "/b/igk-salon-south-beach"),
    }

    for label, html in pages.items():
        parser = _parse(html)
        assert parser.footer_headings == [], (
            f"{label} footer labels should not be heading elements: "
            f"{parser.footer_headings}"
        )
