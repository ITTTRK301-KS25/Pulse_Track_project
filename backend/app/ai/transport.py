"""Tầng HTTP tối giản bằng thư viện chuẩn (không cần cài thêm gói). Test thay bằng transport giả."""
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass, field

MAX_BODY_BYTES = 1_000_000


@dataclass(frozen=True)
class HttpRequest:
    url: str
    headers: dict = field(repr=False)   # chứa API key: không in ra repr
    body: bytes = field(repr=False)
    method: str = "POST"


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict
    body: bytes


class TransportTimeout(Exception):
    pass


class TransportError(Exception):
    pass


def urllib_transport(request: HttpRequest, timeout: float) -> HttpResponse:
    req = urllib.request.Request(request.url, data=request.body, headers=request.headers, method=request.method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(MAX_BODY_BYTES + 1)
            if len(body) > MAX_BODY_BYTES:
                raise TransportError("response too large")
            return HttpResponse(resp.status, {k.lower(): v for k, v in resp.headers.items()}, body)
    except urllib.error.HTTPError as e:
        return HttpResponse(e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read(MAX_BODY_BYTES))
    except (socket.timeout, TimeoutError):
        raise TransportTimeout() from None
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise TransportTimeout() from None
        raise TransportError(type(e.reason).__name__) from None
    except OSError as e:
        raise TransportError(type(e).__name__) from None
