"""Application configuration using pydantic-settings."""

from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── App ──
    app_name: str = "Spring2Fast"
    app_env: str = "development"
    app_debug: bool = True
    log_level: str = "DEBUG"

    # ── Server ──
    host: str = "0.0.0.0"
    port: int = 8000

    # ── LLM API Keys ──
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    llm_provider: str = "auto"
    llm_model: Optional[str] = None
    serper_api_key: Optional[str] = None
    enable_serper_search: bool = False
    enable_mcp_research: bool = False
    mcp_server_config_path: str = "./mcp_servers.json"
    mcp_docs_server_name: str = "docs"
    mcp_docs_tool_name: str = "search_docs"

    # ── GitHub ──
    github_token: Optional[str] = None

    # ── Database ──
    database_url: str = "sqlite+aiosqlite:///./spring2fast.db"

    # ── Directories ──
    workspace_dir: str = "./workspace"
    output_dir: str = "./output"

    @property
    def workspace_path(self) -> Path:
        path = Path(self.workspace_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def output_path(self) -> Path:
        path = Path(self.output_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


settings = Settings()
