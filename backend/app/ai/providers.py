"""Dựng request và đọc phản hồi theo từng nhà cung cấp LLM."""
import json

from app.ai.config import AIConfig
from app.ai.transport import HttpRequest


def build_request(cfg: AIConfig, system: str, user: str) -> HttpRequest:
    if cfg.provider == "anthropic":
        body = {"model": cfg.model, "max_tokens": cfg.max_output_tokens, "system": system,
                "messages": [{"role": "user", "content": user}]}
        headers = {"content-type": "application/json", "x-api-key": cfg.api_key,
                   "anthropic-version": "2023-06-01", "user-agent": "PulseTrack/1.0"}
        return HttpRequest(cfg.base_url + "/v1/messages", headers, json.dumps(body).encode("utf-8"))
    body = {"model": cfg.model, "max_tokens": cfg.max_output_tokens,
            "response_format": {"type": "json_object"},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    headers = {
        "content-type": "application/json",
        "authorization": "Bearer " + cfg.api_key,
        "user-agent": "PulseTrack/1.0",
    }
    return HttpRequest(cfg.base_url + "/chat/completions", headers, json.dumps(body).encode("utf-8"))


def extract_text(provider: str, body: bytes) -> str:
    """Lấy phần chữ của phản hồi. Sai cấu trúc -> ValueError."""
    try:
        data = json.loads(body.decode("utf-8"))
        if provider == "anthropic":
            parts = [b["text"] for b in data["content"] if b.get("type") == "text"]
            text = "".join(parts)
        else:
            text = data["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise ValueError("unexpected provider response") from None
    if not isinstance(text, str) or not text.strip():
        raise ValueError("empty text")
    return text
