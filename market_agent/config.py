from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().lstrip("\ufeff")
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    kakao_rest_api_key: str | None = None
    naver_client_id: str | None = None
    naver_client_secret: str | None = None
    openai_api_key: str | None = None
    openai_model: str = "gpt-5.4-mini"
    openai_base_url: str | None = None

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> "Settings":
        dotenv_path = Path(env_path) if env_path else Path.cwd() / ".env"
        load_dotenv(dotenv_path)
        return cls(
            kakao_rest_api_key=os.getenv("KAKAO_REST_API_KEY") or None,
            naver_client_id=os.getenv("NAVER_CLIENT_ID") or None,
            naver_client_secret=os.getenv("NAVER_CLIENT_SECRET") or None,
            openai_api_key=os.getenv("OPENAI_API_KEY") or None,
            openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-mini"),
            openai_base_url=os.getenv("OPENAI_BASE_URL") or None,
        )

    @property
    def kakao_enabled(self) -> bool:
        return bool(self.kakao_rest_api_key)

    @property
    def naver_enabled(self) -> bool:
        return bool(self.naver_client_id and self.naver_client_secret)

    @property
    def openai_enabled(self) -> bool:
        return bool(self.openai_api_key)
