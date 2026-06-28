from app.main import templates as app_templates


def _render_header(header_variant: str) -> str:
    template = app_templates.env.get_template("partials/header.html")
    return template.render(
        header_variant=header_variant,
        city={"name": "Miami"},
        vertical_word="Beauty",
        header_nav=[
            {"slug": "hair", "label": "Hair"},
            {"slug": "nails", "label": "Nails"},
        ],
        active_category_slug="hair",
        theme={
            "accent_text_full": "text-rose-700",
            "accent_hover_text": "hover:text-rose-600",
        },
        owners_header_cta="For Salon Owners",
    )


def test_over_hero_active_category_link_stays_readable_on_dark_hero():
    html = _render_header("over_hero")

    assert 'class="text-sm tracking-wide transition-colors text-white font-semibold drop-shadow-sm"' in html
    assert 'class="text-sm tracking-wide transition-colors text-white hover:text-white"' in html
    assert 'class="text-sm tracking-wide transition-colors text-rose-700 font-semibold"' not in html


def test_sticky_active_category_link_keeps_network_accent():
    html = _render_header("sticky")

    assert 'class="text-sm tracking-wide transition-colors text-rose-700 font-semibold"' in html


def test_visual_language_toggle_is_desktop_only():
    html = _render_header("sticky")

    assert '<div class="relative hidden md:block">' in html
    assert 'aria-label="Language: English"' in html


def test_mobile_brand_can_shrink_without_pushing_hamburger():
    html = _render_header("sticky")

    assert 'class="group min-w-0 flex-1 md:flex-none"' in html
    assert 'class="flex shrink-0 items-center gap-3"' in html
    assert "block truncate font-serif text-xl md:text-[26px]" in html
