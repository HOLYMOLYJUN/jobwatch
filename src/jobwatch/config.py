"""설정."""

from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env", env_prefix="JW_", extra="ignore"
    )

    db_url: str = f"sqlite:///{PROJECT_ROOT / 'var' / 'jobwatch.db'}"
    watchlist_path: Path = PROJECT_ROOT / "watchlist.yml"

    slack_webhook_url: str = ""
    slack_bot_token: str = ""
    slack_app_token: str = ""
    slack_channel: str = "#jobs"

    request_delay_sec: float = 1.0
    user_agent: str = "jobwatch/0.1 (personal job alert bot)"
    max_pages: int = 60

    @field_validator("db_url", mode="before")
    @classmethod
    def _blank_means_default(cls, v):
        """.env.example 을 그대로 복사하면 `JW_DB_URL=` 처럼 빈 값이 들어온다.

        빈 문자열은 '설정하지 않음'으로 봐야 하는데, 그대로 두면
        SQLAlchemy 가 URL 파싱 단계에서 죽는다. 설정 파일을 복사해 쓰는 건
        정상적인 사용법이므로 코드에서 흡수한다.
        """
        if v is None or (isinstance(v, str) and not v.strip()):
            return f"sqlite:///{PROJECT_ROOT / 'var' / 'jobwatch.db'}"
        return v


settings = Settings()
