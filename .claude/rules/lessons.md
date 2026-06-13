
## Post-payment confirmation banner (2026-06-13)

The confirmation banner (`id="subscribed-banner"`), URL-param stripping, click-to-dismiss, and JS toast are all already implemented in `owner_me.html`. The two gaps were: (1) the banner used generic green (`bg-emerald-700`) instead of the amber theme used everywhere else for "Featured" branding, and (2) there was no auto-dismiss timer — the banner stayed until manually clicked.

Fixed in PR #207: amber colour (`bg-amber-600`) applied to both banner and toast; 10-second auto-dismiss added via `autoDismissTimer = setTimeout(dismissBanner, 10000)` with `clearTimeout` called on manual dismiss.

The server only shows the banner when BOTH `?subscribed=1` is in the URL AND `stripe_subscription_id` is set on the business — so a bookmarked URL without a real subscription shows nothing. The JS then strips `?subscribed=1` from the URL immediately so a page refresh never re-shows it.

## Seed script preserves archived status (2026-06-13)

The upsert helper in `seed/_helpers.py` does a full document replace on re-seed, preserving only `_id` and `created_at`. Without a guard, manually-archived businesses come back to life on every midnight seed run.

The fix: `if existing.get("status") == "archived" and doc.get("status") == "live": doc["status"] = "archived"` — added right before the replace_one call in `upsert()`.

The seed runs via `scripts/deploy.sh` (sets `KAT_ALLOW_PRODUCTION_RESET=true`) on every nightly container restart. Watchtower picks up new images and restarts at midnight.

The database serves THREE networks simultaneously (beauty `eb913a29`, wellness `9bf1b71d`, health `a6486f6d`) under one `who_knows_local` DB. Always filter by `network_id` when counting beauty businesses — counts without that filter include all three networks and will look wildly inflated.

## Preview login email delivery (2026-06-12)

Resend IS configured and working (`RESEND_API_KEY=re_PHtBvPRq_...`). When a code email doesn't arrive, the problem is Gmail-side filtering, not the server. The bypass link pattern (`/api/v1/preview/set-session?token=X&next=/`) is the right unblock — generate one by running the Python snippet in the backend container (see the session that created PR #205 for the exact script).

As of PR #205, every issued code is also logged at INFO level to the container — `docker logs known-around-town-backend-1 | grep "Preview code"` shows the code immediately without a DB query.

The allowed email list is in `backend/app/services/preview_auth.py` (`ALLOWED_EMAILS` + `ALLOWED_DOMAINS`). David's personal emails (`david@bodnick.com`, `david@wisdev.com`) are already in it.

## Support email configuration (2026-06-12)

The support email `hello@knowsbeauty.com` was hardcoded in ~15 places across templates and email service code. The domain has no mail records so every message to it bounced. The pattern used to make it configurable:

1. `Settings.support_email` in `config.py` (env var `SUPPORT_EMAIL`)
2. Jinja2 global set at module load from env var, overwritten in `on_startup` from DB value
3. `get_support_email()` in `site_settings.py` — DB value takes precedence over env var
4. Admin settings page field saves to DB and updates the Jinja2 global in-process immediately

For any future site-wide text that might need to change: use this same DB-over-env-var-over-default pattern from `site_settings.py`.
