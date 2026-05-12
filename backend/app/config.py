from functools import lru_cache
from typing import Dict, List, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "who_knows_local"

    network_domains: str = ""

    admin_api_key: str = ""

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
