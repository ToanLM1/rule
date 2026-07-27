"""OIDC authentication and role authorization."""

from brp.security.auth import (
    ALL_ROLES,
    AuthenticationError,
    AuthorizationError,
    LocalAuthConfig,
    LocalLogin,
    OidcConfig,
    Principal,
    RequestAuthenticator,
    SecuritySettings,
)

__all__ = [
    "ALL_ROLES",
    "AuthenticationError",
    "AuthorizationError",
    "LocalAuthConfig",
    "LocalLogin",
    "OidcConfig",
    "Principal",
    "RequestAuthenticator",
    "SecuritySettings",
]
