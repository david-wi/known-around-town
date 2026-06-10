from functools import lru_cache
from typing import Dict, List, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "who_knows_local"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
