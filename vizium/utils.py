from urllib.parse import urlparse


def websocket_base(api_base_url: str) -> str:
    """Convert an API HTTP(S) base URL into its WS(S) counterpart."""
    parsed = urlparse(api_base_url.rstrip("/"))
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return parsed._replace(scheme=scheme).geturl().rstrip("/")


def public_attributes(obj):
    return [name for name in dir(obj) if not name.startswith("_")]
