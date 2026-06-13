from functools import lru_cache
from typing import Dict, List, Tuple
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


# WHY: Host names that mean "a MongoDB running on this same box / inside this
# same Compose stack" rather than the managed cloud database. The app must
# never silently use one of these in production — a throwaway local Mongo was
# left exposed to the internet and wiped by a ransomware bot on 2026-06-11.
# Production data lives in MongoDB Atlas, reached via a `mongodb+srv://...`
# URL, so any of these targets in production is a misconfiguration we want to
# fail loudly on, not fall back to.
_LOCAL_MONGO_HOSTS = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "mongo",  # the docker-compose service name for the local dev Mongo
        "mongodb",
    }
)


class LocalMongoForbiddenError(RuntimeError):
    """Raised at startup when the configured MongoDB target is a local one.

    WHY this is a hard error and not a warning: a silent fall-back to a local
    database is exactly how production could end up reading and writing the
    wrong (and unprotected) database without anyone noticing. Crashing on boot
    surfaces the misconfiguration immediately in the deploy log instead of
    quietly serving the wrong data.
    """


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # WHY: no default value. Previously this defaulted to
    # "mongodb://localhost:27017", which meant a missing/blank MONGODB_URL in
    # production silently connected to a local Mongo instead of failing. An
    # empty string is caught by validate_mongodb_url() below and turned into a
    # loud startup error, so a misconfigured deploy can never quietly run
    # against the wrong database.
    mongodb_url: str = ""
    mongodb_database: str = "who_knows_local"

    # WHY: the ONE escape hatch for local development. A developer running the
    # app against a Mongo on their own machine (localhost / the Compose `mongo`
    # service) sets ALLOW_LOCAL_MONGODB=true in their local .env. Production
    # never sets it, so production can never connect to a local Mongo. This
    # keeps the dev experience unchanged while closing the production
    # fall-back path.
    allow_local_mongodb: bool = False

    network_domains: str = ""

    admin_api_key: str = ""

    # Stripe billing.  All three must be set before the checkout and
    # webhook endpoints become active.  Leaving them empty disables
    # billing gracefully (the endpoints return 503) so the rest of
    # the app stays functional during early development.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # WHY: price ID is the Stripe-assigned id for the Pro annual plan
    # (price_...).  Stored in config rather than hard-coded so we can
    # swap it between test mode and live mode without a code change.
    stripe_price_id_pro: str = ""

    # WHY: 25 is enough early adopters to create visible social proof
    # (badge shown on listing pages) without devaluing the "founding"
    # status. Configurable so David can raise the cap if early demand
    # is strong without a code deploy.
    founding_partner_cap: int = 25

    # WHY: read through pydantic-settings (same as all other config) rather
    # than os.environ.get() directly, so the setting is documented in one
    # place and works with .env files in dev. Empty string means the GA4
    # script is not emitted — no dead snippet or console noise on dev.
    ga_measurement_id: str = ""

    # WHY: when both the custom domain (miami.knowsbeauty.com) and the
    # dev subdomain (miami.knowsbeauty.ai.devintensive.com) serve the same
    # content, search engines see duplicate pages at two addresses. Setting
    # CANONICAL_BASE_URL=https://miami.knowsbeauty.com makes every page
    # declare the .com URL as the authoritative one, concentrating ranking
    # signals on the public-facing domain rather than splitting them. Leave
    # empty to use the incoming request URL (safe while only one domain exists).
    canonical_base_url: str = ""

    # WHY: Google Search Console requires site ownership verification before
    # it will show indexing reports or accept sitemap submissions. The easiest
    # verification method is a <meta name="google-site-verification"> tag in
    # the page <head>. Setting this env var adds the tag to every page so David
    # can verify ownership in one config change without a code deploy.
    google_site_verification: str = ""

    # WHY: when True (the default), every page is hidden behind an email + code
    # login so the site stays private during the pre-launch period. Set to False
    # (or remove the env var) to open the site to the public. A single env-var
    # toggle is faster and safer than a code deploy when launch day arrives.
    preview_mode_enabled: bool = True

    # WHY: Places API key enables Google rating lookup and AggregateRating
    # rich snippets. Ratings are cached in business documents (not fetched
    # live on each page load), so a missing key just means ratings stay blank
    # — the rest of the app continues to work normally.
    google_places_api_key: str = ""

    # WHY: the public-facing support email shown throughout the site and in
    # outbound emails. Configurable so David can point it at a working inbox
    # (e.g. a Google Workspace address or forwarding address) via one env-var
    # change and a container restart, without a code deploy. The default is
    # hello@knowsbeauty.com — update to a real monitored address before launch.
    support_email: str = "hello@knowsbeauty.com"

    port: int = 8000
    log_level: str = "INFO"

    def parse_network_domains(self) -> List[Tuple[str, str]]:
        pairs: List[Tuple[str, str]] = []
        for chunk in self.network_domains.split(","):
            chunk = chunk.strip()
            if not chunk or ":" not in chunk:
                continue
            slug, suffix = chunk.split(":", 1)
            pairs.append((slug.strip().lower(), suffix.strip().lower()))
        return pairs

    def _mongo_host(self) -> str:
        """Best-effort extraction of the host from the MongoDB URL.

        WHY urlsplit instead of a regex: connection strings vary
        (`mongodb://`, `mongodb+srv://`, optional `user:pass@`, optional port,
        comma-separated replica-set members). urlsplit handles the userinfo/
        port stripping for the common single-host case, and we additionally
        take only the first member of a comma-separated host list so a
        replica-set URL is checked by its first host.
        """
        raw = (self.mongodb_url or "").strip()
        if not raw:
            return ""
        # A bare `mongodb+srv://host/db` parses fine; urlsplit's .hostname
        # lowercases and strips any `user:pass@` and `:port`.
        host = urlsplit(raw).hostname or ""
        # Replica-set URLs can list several hosts: take the first.
        host = host.split(",", 1)[0]
        return host.lower()

    def mongo_host(self) -> str:
        """Public accessor for the parsed MongoDB host.

        WHY this exists: the destructive seed/reset guard
        (`seed._helpers.assert_seed_target_allowed`) needs to classify the same
        host the app validates, and must use the exact parsing rules above so
        the two guards can never disagree about what counts as "local".
        """
        return self._mongo_host()

    def is_local_mongo_target(self) -> bool:
        """True only when BOTH the dev opt-in is set AND the host is local.

        WHY both conditions: the opt-in flag alone is not proof the target is a
        throwaway local database — a developer can leave ALLOW_LOCAL_MONGODB
        set in their shell while MONGODB_URL points at the managed Atlas
        database. Requiring the host to ALSO be a known-local one means a
        mistakenly-aimed-at-Atlas run is never treated as "local", so the
        destructive seed guard keeps protecting production even when the dev
        opt-in happens to be on.
        """
        return bool(self.allow_local_mongodb) and self.mongo_host() in _LOCAL_MONGO_HOSTS

    def validate_mongodb_url(self) -> None:
        """Fail loudly unless MONGODB_URL is set to a non-local database.

        Called once at startup (from app.database.get_client). Raises
        LocalMongoForbiddenError when the URL is empty or points at a local
        Mongo and the ALLOW_LOCAL_MONGODB dev opt-in is not set.
        """
        if not (self.mongodb_url or "").strip():
            raise LocalMongoForbiddenError(
                "MONGODB_URL is not set. The app refuses to start without an "
                "explicit database URL. In production set MONGODB_URL to the "
                "MongoDB Atlas connection string; for local development set a "
                "local URL together with ALLOW_LOCAL_MONGODB=true."
            )
        if self.allow_local_mongodb:
            return
        host = self._mongo_host()
        if host in _LOCAL_MONGO_HOSTS:
            raise LocalMongoForbiddenError(
                f"MONGODB_URL points at a local MongoDB host ({host!r}), which "
                "is not allowed in production. Production must use the managed "
                "MongoDB Atlas database. If this is a local development run, "
                "set ALLOW_LOCAL_MONGODB=true to opt in."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
