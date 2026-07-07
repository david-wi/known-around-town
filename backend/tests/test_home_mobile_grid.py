"""Regression test: the home page's two responsive grids need a single-column
base class for mobile.

Without an explicit `grid-cols-1`, a `grid lg:grid-cols-2` element has NO
column definition below the breakpoint, so the implicit auto track sizes to
the widest child's min-content. The neighborhood mini-list h4 is `truncate`
(nowrap), so the longest business name set the layout width — the homepage
rendered 476 CSS px wide on a 390 px phone (86 px of horizontal overflow).
The Neighborhood Spotlight `grid md:grid-cols-12` had the same gap: its cards
extended to 410 px and were clipped by the section's overflow-hidden.
`grid-cols-1` is already present in the precompiled reference.css.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(seeded_db):
    from app.main import app

    return TestClient(app)


def test_home_grids_have_single_column_mobile_base(client):
    r = client.get("/", headers={"host": "miami.knowsbeauty.localhost"})
    assert r.status_code == 200, r.text
    body = r.text
    # Two-column neighborhood mini-lists: one column below lg.
    assert "grid grid-cols-1 lg:grid-cols-2" in body
    # Neighborhood Spotlight: one column below md.
    assert "grid grid-cols-1 md:grid-cols-12" in body
