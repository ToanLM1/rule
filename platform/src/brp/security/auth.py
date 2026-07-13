"""Fail-closed OIDC/JWT authentication with explicit local-development headers."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import jwt
from pydantic import Field, model_validator

from brp.ir.models import StrictModel

ALL_ROLES = frozenset({"maker", "checker", "reviewer", "deployer"})


class AuthenticationError(PermissionError):
    pass


class AuthorizationError(PermissionError):
    pass


class OidcConfig(StrictModel):
    issuer: str = Field(min_length=1)
    audience: str = Field(min_length=1)
    jwks_url: str = Field(min_length=1)
    algorithms: tuple[str, ...] = ("RS256",)
    roles_claim: str = "roles"
    leeway_seconds: int = Field(default=30, ge=0, le=300)

    @model_validator(mode="after")
    def safe_algorithms(self) -> OidcConfig:
        if not self.algorithms or any(
            algorithm == "none" or algorithm.startswith("HS") for algorithm in self.algorithms
        ):
            raise ValueError("OIDC algorithms must be fixed asymmetric algorithms")
        return self


class SecuritySettings(StrictModel):
    local_development_headers: bool = False
    oidc: OidcConfig | None = None

    @classmethod
    def local_development(cls) -> SecuritySettings:
        return cls(local_development_headers=True)

    @classmethod
    def from_environment(cls) -> SecuritySettings:
        local = os.getenv("BRP_LOCAL_DEVELOPMENT_HEADERS", "").lower() == "true"
        values = {
            "issuer": os.getenv("BRP_OIDC_ISSUER"),
            "audience": os.getenv("BRP_OIDC_AUDIENCE"),
            "jwks_url": os.getenv("BRP_OIDC_JWKS_URL"),
        }
        configured = [value is not None for value in values.values()]
        if any(configured) and not all(configured):
            raise ValueError("issuer, audience, and JWKS URL must be configured together")
        oidc = None
        if all(configured):
            oidc = OidcConfig(
                issuer=str(values["issuer"]),
                audience=str(values["audience"]),
                jwks_url=str(values["jwks_url"]),
                algorithms=tuple(
                    item.strip()
                    for item in os.getenv("BRP_OIDC_ALGORITHMS", "RS256").split(",")
                    if item.strip()
                ),
                roles_claim=os.getenv("BRP_OIDC_ROLES_CLAIM", "roles"),
            )
        return cls(local_development_headers=local, oidc=oidc)


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]


class RequestAuthenticator:
    def __init__(
        self,
        settings: SecuritySettings,
        *,
        key_resolver: Callable[[str], Any] | None = None,
    ) -> None:
        self.settings = settings
        self._key_resolver = key_resolver
        self._jwks_client = (
            jwt.PyJWKClient(settings.oidc.jwks_url)
            if settings.oidc is not None and key_resolver is None
            else None
        )

    def authenticate(
        self,
        *,
        authorization: str | None,
        development_actor: str | None,
        development_roles: str | None = None,
    ) -> Principal:
        if self.settings.local_development_headers:
            if not development_actor or not development_actor.strip():
                raise AuthenticationError("X-BRP-Actor is required in local-development mode")
            roles = (
                frozenset(role.strip() for role in development_roles.split(",") if role.strip())
                if development_roles
                else ALL_ROLES
            )
            return Principal(development_actor.strip(), roles)
        if development_actor is not None or development_roles is not None:
            raise AuthenticationError("development identity headers are disabled")
        config = self.settings.oidc
        if config is None:
            raise AuthenticationError("OIDC authentication is not configured")
        if authorization is None or not authorization.startswith("Bearer "):
            raise AuthenticationError("Bearer token is required")
        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            raise AuthenticationError("Bearer token is required")
        try:
            if self._key_resolver is not None:
                key = self._key_resolver(token)
            else:
                assert self._jwks_client is not None
                key = self._jwks_client.get_signing_key_from_jwt(token).key
            claims = jwt.decode(
                token,
                key,
                algorithms=list(config.algorithms),
                audience=config.audience,
                issuer=config.issuer,
                leeway=config.leeway_seconds,
                options={"require": ["exp", "iat", "sub", "iss", "aud"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("token validation failed") from exc
        subject = claims.get("sub")
        raw_roles = claims.get(config.roles_claim, [])
        if not isinstance(subject, str) or not subject.strip():
            raise AuthenticationError("validated token has no subject")
        if not isinstance(raw_roles, list) or any(not isinstance(role, str) for role in raw_roles):
            raise AuthenticationError("roles claim must be an array of strings")
        return Principal(subject.strip(), frozenset(raw_roles))

    @staticmethod
    def require_role(principal: Principal, role: str) -> str:
        if role not in principal.roles:
            raise AuthorizationError(f"role '{role}' is required")
        return principal.subject
