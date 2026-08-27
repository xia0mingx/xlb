from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # SQLite by default so the app runs with no external services.
    # For Postgres: DATABASE_URL=postgresql+asyncpg://dewdrop:dewdrop@localhost:5432/dewdrop
    database_url: str = "sqlite+aiosqlite:///./xlb.db"

    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Scraping
    scrape_timeout: float = 20.0
    scrape_retries: int = 3
    scrape_delay_seconds: float = 1.5
    scrape_concurrency: int = 4

    # Scheduler
    enable_scheduler: bool = False
    refresh_interval_hours: int = 6

    # Matching: listings below this confidence are hidden from the public price table
    match_confidence_threshold: float = 0.85

    # Synthetic seed products (jobs/seed.py) are development scaffolding: fictional
    # retailers, invented prices, no images. They are hidden from the API by default
    # so the catalog only shows products backed by a real listing. Set true to see
    # them again - useful when working on the app with no network.
    show_synthetic_products: bool = False

    # Chat assistant. Talks to an OpenAI-compatible chat-completions endpoint
    # (OpenCode). No defaults for the endpoint or key on purpose: an unset key
    # must fail loudly at the route rather than silently point somewhere wrong.
    llm_base_url: str = ""
    llm_model: str = ""
    opencode_api_key: str = ""
    chat_max_rounds: int = 6
    chat_timeout_seconds: float = 30.0
    chat_max_history: int = 20

    @property
    def chat_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_model and self.opencode_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
