from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    database_url: str
    faceit_api_key: str | None = Field(default=None, repr=False)
    demo_storage_dir: str = "../storage/demos"
    demo_max_bytes: int = 1073741824
    demo_max_uncompressed_bytes: int = 1073741824
    demo_quota_bytes: int = 4294967296
    demo_timeout_seconds: int = 600
    cookie_secure: bool = False
    allowed_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def cookie_name(self) -> str:
        return "__Host-cs2_session" if self.cookie_secure else "cs2_session"


@lru_cache
def get_settings() -> Settings:
    return Settings()
