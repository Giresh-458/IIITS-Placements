from pydantic_settings import BaseSettings, SettingsConfigDict

class CrawlBudgetConfig(BaseSettings):
    max_runtime_seconds: int = 3600
    max_urls: int = 1000
    max_pages_per_source: int = 50
    max_depth: int = 3
    max_browser_pages: int = 5
    max_pdf_pages: int = 20
    max_retries: int = 3
    per_domain_delay_seconds: int = 2
    request_timeout_seconds: int = 30
    browser_timeout_seconds: int = 60

class EligibilityConfig(BaseSettings):
    cse_min_lpa: float = 10.0
    ece_min_lpa: float = 6.5
    recent_event_days_window: int = 15

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://user:password@localhost:5432/placement_db"
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "llama3"
    
    crawl_budget: CrawlBudgetConfig = CrawlBudgetConfig()
    eligibility: EligibilityConfig = EligibilityConfig()
    
    enable_scheduled_crawls: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", env_nested_delimiter="__")

settings = Settings()
