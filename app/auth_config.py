"""Fail-closed configuration checks for the planned Google OIDC login.

This module does not implement OIDC, sessions, or authentication routes. It only
validates deployment configuration so future auth code can refuse to start when
required values are missing or unsafe.
"""
from dataclasses import dataclass
import os
from urllib.parse import urlparse


@dataclass(frozen=True)
class GoogleOIDCConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    allowed_subject: str
    session_secret: str


class AuthConfigurationError(RuntimeError):
    """Raised when private-login configuration is absent or unsafe."""


def load_google_oidc_config(environ: dict[str, str] | None = None) -> GoogleOIDCConfig:
    """Load required secrets from the server environment; never provide defaults."""
    values = os.environ if environ is None else environ
    required = {
        "GOOGLE_OIDC_CLIENT_ID": values.get("GOOGLE_OIDC_CLIENT_ID", "").strip(),
        "GOOGLE_OIDC_CLIENT_SECRET": values.get("GOOGLE_OIDC_CLIENT_SECRET", "").strip(),
        "GOOGLE_OIDC_REDIRECT_URI": values.get("GOOGLE_OIDC_REDIRECT_URI", "").strip(),
        "SALES_ALLOWED_GOOGLE_SUB": values.get("SALES_ALLOWED_GOOGLE_SUB", "").strip(),
        "SALES_SESSION_SECRET": values.get("SALES_SESSION_SECRET", ""),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise AuthConfigurationError(
            "Google OIDC login is not configured; missing: " + ", ".join(missing)
        )

    redirect = urlparse(required["GOOGLE_OIDC_REDIRECT_URI"])
    try:
        redirect_port = redirect.port
    except ValueError:
        redirect_port = -1
    if (
        redirect.scheme != "https"
        or not redirect.hostname
        or redirect_port == -1
        or redirect.username
        or redirect.password
        or redirect.query
        or redirect.fragment
        or any(character.isspace() for character in required["GOOGLE_OIDC_REDIRECT_URI"])
    ):
        raise AuthConfigurationError(
            "GOOGLE_OIDC_REDIRECT_URI must be an absolute HTTPS URL without embedded credentials"
        )

    if len(required["SALES_SESSION_SECRET"].encode("utf-8")) < 32:
        raise AuthConfigurationError(
            "SALES_SESSION_SECRET must contain at least 32 bytes"
        )

    return GoogleOIDCConfig(
        client_id=required["GOOGLE_OIDC_CLIENT_ID"],
        client_secret=required["GOOGLE_OIDC_CLIENT_SECRET"],
        redirect_uri=required["GOOGLE_OIDC_REDIRECT_URI"],
        allowed_subject=required["SALES_ALLOWED_GOOGLE_SUB"],
        session_secret=required["SALES_SESSION_SECRET"],
    )
