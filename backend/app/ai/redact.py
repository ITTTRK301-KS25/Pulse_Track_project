"""Che secret trước khi đưa bất kỳ chuỗi nào vào log (A01 AC3)."""
import re

_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]+"),
    re.compile(r"(?i)(x-api-key|api[_-]?key|authorization)\s*[:=]\s*\S+"),
)


def redact(text: str, secrets: tuple[str, ...] = ()) -> str:
    out = str(text)
    for s in secrets:
        if s:
            out = out.replace(s, "***")
    for p in _PATTERNS:
        out = p.sub("***", out)
    return out
