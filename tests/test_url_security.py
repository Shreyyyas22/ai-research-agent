import pytest

from app.tools.url_security import UnsafeURL, validate_url

def test_localhost_is_blocked() -> None:
    with pytest.raises(UnsafeURL):
        validate_url("http://localhost")

def test_loopback_ip_is_blocked() -> None:
    with pytest.raises(UnsafeURL):
        validate_url("http://127.0.0.1")

def test_cloud_metadata_ip_is_blocked() -> None:
    with pytest.raises(UnsafeURL):
        validate_url("http://169.254.169.254")


def test_private_ip_is_blocked() -> None:
    with pytest.raises(UnsafeURL):
        validate_url("http://192.168.1.1")


def test_ftp_is_blocked() -> None:
    with pytest.raises(UnsafeURL):
        validate_url("ftp://example.com")