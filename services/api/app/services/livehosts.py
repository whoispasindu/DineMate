import ipaddress
from collections.abc import Iterable
from urllib.parse import urlsplit

LIVE_PATH = "/live"


def is_local_host(host: str) -> bool:
    name = host.strip("[]").lower()
    try:
        address = ipaddress.ip_address(name)
    except ValueError:
        return name == "localhost" or name.endswith((".local", ".localhost")) or "." not in name
    return address.is_private or address.is_loopback or address.is_link_local


def live_url_allowed(url: str, extra_hosts: Iterable[str] = ()) -> bool:
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    host = parts.hostname
    if parts.scheme not in ("http", "https") or not host or port == 0:
        return False
    if parts.username or parts.password or parts.query or parts.fragment or parts.path != LIVE_PATH:
        return False
    return is_local_host(host) or host.lower() in {h.lower() for h in extra_hosts}
