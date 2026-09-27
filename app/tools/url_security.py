import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(Exception):
    """Raised when a URL is considered unsafe."""


def validate_url(url: str) -> None:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise UnsafeURL(
            "Only HTTP and HTTPS URLs are allowed."
        )

    if not parsed.hostname:
        raise UnsafeURL(
            "URL must contain a hostname."
        )

    hostname = parsed.hostname.lower()

    blocked_hostnames = {
        "localhost",
        "localhost.localdomain",
    }

    if hostname in blocked_hostnames:
        raise UnsafeURL(
            "Localhost URLs are not allowed."
        )

    try:
        addresses = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )

    except socket.gaierror as exc:
        raise UnsafeURL(
            "Could not resolve hostname."
        ) from exc

    for address in addresses:

        ip = ipaddress.ip_address(
            address[4][0]
        )

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        ):
            raise UnsafeURL(
                "URL resolves to a blocked IP address."
            )