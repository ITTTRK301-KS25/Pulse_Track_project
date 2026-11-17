"""Cấu hình AI đọc từ biến môi trường / file .env phía server (A01 AC1).

Biến (tất cả tùy chọn; không có AI_API_KEY + AI_MODEL thì AI ở trạng thái "chưa cấu hình",
các chức năng khác của hệ thống vẫn chạy bình thường):
  AI_PROVIDER              anthropic | openai_compatible        (mặc định anthropic)
  AI_API_KEY               secret, CHỈ đặt trong .env của server
  AI_MODEL                 tên model (bắt buộc để gọi thật)
  AI_BASE_URL              mặc định theo provider; phải là https (trừ localhost)
  AI_TIMEOUT_SECONDS       1..120, mặc định 20
  AI_MAX_RETRIES           0..5, mặc định 2 (số lần thử lại, tổng lần gọi = 1 + giá trị này)
  AI_RETRY_BACKOFF_SECONDS 0..10, mặc định 0.5
  AI_MAX_OUTPUT_TOKENS     16..8192, mặc định 1024
  AI_MOCK_MODE             true/false, mặc định false; chỉ cho phép khi APP_ENV là demo hoặc test
  APP_ENV                  dev (mặc định) | demo | test | prod
"""
from dataclasses import dataclass, field
from typing import Mapping
from urllib.parse import urlparse

PROVIDERS = ("anthropic", "openai_compatible")
DEFAULT_BASE_URL = {"anthropic": "https://api.anthropic.com", "openai_compatible": "https://api.openai.com/v1"}
MOCK_ENVS = ("demo", "test")
_TRUE, _FALSE = ("1", "true", "yes", "on"), ("0", "false", "no", "off", "")


class AIConfigError(ValueError):
    """Cấu hình sai. Thông báo chỉ nêu tên biến, không bao giờ chứa giá trị của secret."""


@dataclass(frozen=True)
class AIConfig:
    provider: str = "anthropic"
    api_key: str = field(default="", repr=False)   # repr=False: không lộ khi in/log đối tượng
    model: str = ""
    base_url: str = ""
    timeout_seconds: float = 20.0
    max_retries: int = 2
    retry_backoff_seconds: float = 0.5
    max_output_tokens: int = 1024
    mock_mode: bool = False
    app_env: str = "dev"

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    @property
    def max_attempts(self) -> int:
        return self.max_retries + 1


def _num(m: Mapping[str, str], key: str, default, lo, hi, cast):
    raw = (m.get(key) or "").strip()
    if raw == "":
        return default
    try:
        v = cast(raw)
    except ValueError:
        raise AIConfigError(f"{key} phải là số") from None
    if not (lo <= v <= hi):
        raise AIConfigError(f"{key} phải nằm trong khoảng {lo}..{hi}")
    return v


def _flag(m: Mapping[str, str], key: str) -> bool:
    raw = (m.get(key) or "").strip().lower()
    if raw in _TRUE:
        return True
    if raw in _FALSE:
        return False
    raise AIConfigError(f"{key} phải là true hoặc false")


def _check_url(url: str) -> None:
    p = urlparse(url)
    local = p.hostname in ("localhost", "127.0.0.1", "::1")
    if not p.hostname or p.scheme not in ("https", "http") or (p.scheme == "http" and not local):
        raise AIConfigError("AI_BASE_URL phải là địa chỉ https (http chỉ cho phép localhost)")


def from_mapping(m: Mapping[str, str]) -> AIConfig:
    provider = (m.get("AI_PROVIDER") or "anthropic").strip().lower()
    if provider not in PROVIDERS:
        raise AIConfigError("AI_PROVIDER phải là anthropic hoặc openai_compatible")
    app_env = (m.get("APP_ENV") or "dev").strip().lower()
    mock = _flag(m, "AI_MOCK_MODE")
    if mock and app_env not in MOCK_ENVS:
        raise AIConfigError("AI_MOCK_MODE chỉ được bật khi APP_ENV là demo hoặc test")
    base = (m.get("AI_BASE_URL") or "").strip() or DEFAULT_BASE_URL[provider]
    _check_url(base)
    return AIConfig(
        provider=provider,
        api_key=(m.get("AI_API_KEY") or "").strip(),
        model=(m.get("AI_MODEL") or "").strip(),
        base_url=base.rstrip("/"),
        timeout_seconds=_num(m, "AI_TIMEOUT_SECONDS", 20.0, 1, 120, float),
        max_retries=_num(m, "AI_MAX_RETRIES", 2, 0, 5, int),
        retry_backoff_seconds=_num(m, "AI_RETRY_BACKOFF_SECONDS", 0.5, 0, 10, float),
        max_output_tokens=_num(m, "AI_MAX_OUTPUT_TOKENS", 1024, 16, 8192, int),
        mock_mode=mock,
        app_env=app_env,
    )


_KEYS = ("AI_PROVIDER", "AI_API_KEY", "AI_MODEL", "AI_BASE_URL", "AI_TIMEOUT_SECONDS", "AI_MAX_RETRIES",
         "AI_RETRY_BACKOFF_SECONDS", "AI_MAX_OUTPUT_TOKENS", "AI_MOCK_MODE", "APP_ENV")


def load_ai_config() -> AIConfig:
    """Đọc từ .env (cùng cách config.py của nhóm) rồi biến môi trường."""
    from pydantic_settings import BaseSettings, SettingsConfigDict

    class _AIEnv(BaseSettings):
        model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
        AI_PROVIDER: str | None = None
        AI_API_KEY: str | None = None
        AI_MODEL: str | None = None
        AI_BASE_URL: str | None = None
        AI_TIMEOUT_SECONDS: str | None = None
        AI_MAX_RETRIES: str | None = None
        AI_RETRY_BACKOFF_SECONDS: str | None = None
        AI_MAX_OUTPUT_TOKENS: str | None = None
        AI_MOCK_MODE: str | None = None
        APP_ENV: str | None = None

    env = _AIEnv()
    return from_mapping({k: getattr(env, k) or "" for k in _KEYS})
