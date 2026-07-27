"""Fail-closed OIDC/JWT authentication with explicit local-development headers."""

from __future__ import annotations

import os
import secrets
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from pydantic import Field, model_validator

from brp.ir.models import StrictModel

ALL_ROLES = frozenset({"maker", "checker", "reviewer", "deployer"})
SESSION_ALGORITHM = "HS256"
SESSION_COOKIE = "brp_session"


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


class LocalAuthConfig(StrictModel):
    users_file: Path
    session_secret_file: Path
    public_origin: str = Field(min_length=1)
    session_ttl_seconds: int = Field(default=28_800, ge=300, le=86_400)


class LocalUser(StrictModel):
    username: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9._-]+$")
    password_hash: str = Field(alias="passwordHash", min_length=20)
    roles: tuple[str, ...]
    session_version: int = Field(default=1, alias="sessionVersion", ge=1)

    @model_validator(mode="after")
    def safe_roles(self) -> LocalUser:
        if not self.roles or any(role not in ALL_ROLES for role in self.roles):
            raise ValueError("local user roles must be non-empty known roles")
        return self


class LocalUserFile(StrictModel):
    users: tuple[LocalUser, ...]

    @model_validator(mode="after")
    def unique_users(self) -> LocalUserFile:
        names = [user.username for user in self.users]
        if not names or len(names) != len(set(names)):
            raise ValueError("local users must be non-empty and unique")
        return self


class SecuritySettings(StrictModel):
    local_development_headers: bool = False
    oidc: OidcConfig | None = None
    local_auth: LocalAuthConfig | None = None

    @classmethod
    def local_development(cls) -> SecuritySettings:
        return cls(local_development_headers=True)

    @classmethod
    def from_environment(cls) -> SecuritySettings:
        mode = os.getenv("BRP_AUTH_MODE", "").strip().lower()
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
        local_auth = None
        if mode == "local":
            users_file = os.getenv("BRP_LOCAL_USERS_FILE")
            secret_file = os.getenv("BRP_SESSION_SECRET_FILE")
            public_origin = os.getenv("BRP_PUBLIC_ORIGIN")
            if not users_file or not secret_file or not public_origin:
                raise ValueError(
                    "local auth requires BRP_LOCAL_USERS_FILE, "
                    "BRP_SESSION_SECRET_FILE and BRP_PUBLIC_ORIGIN"
                )
            local_auth = LocalAuthConfig(
                users_file=Path(users_file),
                session_secret_file=Path(secret_file),
                public_origin=public_origin.rstrip("/"),
                session_ttl_seconds=int(os.getenv("BRP_SESSION_TTL_SECONDS", "28800")),
            )
        if mode == "development":
            local = True
        if mode == "oidc" and oidc is None:
            raise ValueError("BRP_AUTH_MODE=oidc requires complete OIDC configuration")
        if mode not in {"", "development", "local", "oidc"}:
            raise ValueError("BRP_AUTH_MODE must be development, local, or oidc")
        if sum((local, local_auth is not None, oidc is not None)) > 1:
            raise ValueError("development, local and OIDC auth modes are mutually exclusive")
        return cls(local_development_headers=local, oidc=oidc, local_auth=local_auth)


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]
    csrf_token: str | None = None


@dataclass(frozen=True)
class LocalLogin:
    principal: Principal
    session_token: str
    expires_at: datetime


class LocalSessionAuthenticator:
    def __init__(self, config: LocalAuthConfig) -> None:
        self.config = config
        try:
            document = LocalUserFile.model_validate_json(config.users_file.read_text("utf-8"))
            secret = config.session_secret_file.read_text("utf-8").strip()
        except (OSError, ValueError) as exc:
            raise ValueError("local authentication configuration is unavailable") from exc
        if len(secret.encode("utf-8")) < 32:
            raise ValueError("session secret must contain at least 32 UTF-8 bytes")
        self._users = {user.username: user for user in document.users}
        self._secret = secret
        self._hasher = PasswordHasher()

    def login(self, username: str, password: str) -> LocalLogin:
        user = self._users.get(username.strip())
        if user is None:
            self._burn_password_time(password)
            raise AuthenticationError("invalid username or password")
        try:
            self._hasher.verify(user.password_hash, password)
        except (InvalidHashError, VerifyMismatchError) as exc:
            raise AuthenticationError("invalid username or password") from exc
        now = datetime.now(UTC)
        expires_at = now + timedelta(seconds=self.config.session_ttl_seconds)
        csrf_token = secrets.token_urlsafe(32)
        token = jwt.encode(
            {
                "sub": user.username,
                "sv": user.session_version,
                "csrf": csrf_token,
                "iat": now,
                "exp": expires_at,
            },
            self._secret,
            algorithm=SESSION_ALGORITHM,
        )
        return LocalLogin(
            principal=Principal(user.username, frozenset(user.roles), csrf_token),
            session_token=token,
            expires_at=expires_at,
        )

    def authenticate(self, token: str | None) -> Principal:
        if not token:
            raise AuthenticationError("session is required")
        try:
            claims = jwt.decode(
                token,
                self._secret,
                algorithms=[SESSION_ALGORITHM],
                options={"require": ["sub", "sv", "csrf", "iat", "exp"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError("session is invalid or expired") from exc
        username = claims.get("sub")
        user = self._users.get(username) if isinstance(username, str) else None
        if user is None or claims.get("sv") != user.session_version:
            raise AuthenticationError("session is invalid or expired")
        csrf_token = claims.get("csrf")
        if not isinstance(csrf_token, str) or not csrf_token:
            raise AuthenticationError("session is invalid or expired")
        return Principal(user.username, frozenset(user.roles), csrf_token)

    def verify_request(
        self, principal: Principal, *, csrf_token: str | None, origin: str | None
    ) -> None:
        if origin != self.config.public_origin:
            raise AuthenticationError("request origin is not allowed")
        if not csrf_token or not secrets.compare_digest(csrf_token, principal.csrf_token or ""):
            raise AuthenticationError("CSRF token is invalid")

    def _burn_password_time(self, password: str) -> None:
        dummy = (
            "$argon2id$v=19$m=65536,t=3,p=4$"
            "MDEyMzQ1Njc4OWFiY2RlZg$"
            "8mM5YJq8aHJF+XK3J6n6vGgmV8rPPPb7uV2LTpZ1V0U"
        )
        with suppress(InvalidHashError, VerifyMismatchError):
            self._hasher.verify(dummy, password)


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
        self._local = (
            LocalSessionAuthenticator(settings.local_auth)
            if settings.local_auth is not None
            else None
        )

    @property
    def protects_all_requests(self) -> bool:
        return self._local is not None or self.settings.oidc is not None

    @property
    def local_sessions_enabled(self) -> bool:
        return self._local is not None

    def login(self, username: str, password: str) -> LocalLogin:
        if self._local is None:
            raise AuthenticationError("local login is not configured")
        return self._local.login(username, password)

    def verify_unsafe_request(
        self, principal: Principal, *, csrf_token: str | None, origin: str | None
    ) -> None:
        if self._local is not None:
            self._local.verify_request(principal, csrf_token=csrf_token, origin=origin)

    def authenticate(
        self,
        *,
        authorization: str | None,
        development_actor: str | None,
        development_roles: str | None = None,
        session_cookie: str | None = None,
    ) -> Principal:
        if self._local is not None:
            if (
                authorization is not None
                or development_actor is not None
                or development_roles is not None
            ):
                raise AuthenticationError("header-based identities are disabled")
            return self._local.authenticate(session_cookie)
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
