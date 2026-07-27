import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
import pytest
from argon2 import PasswordHasher
from cryptography.hazmat.primitives.asymmetric import rsa

from brp.security import (
    AuthenticationError,
    AuthorizationError,
    LocalAuthConfig,
    OidcConfig,
    RequestAuthenticator,
    SecuritySettings,
)

ISSUER = "https://idp.example.test"
AUDIENCE = "brp-api"


@pytest.fixture
def keys() -> tuple[object, object]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private, private.public_key()


def authenticator(public_key: object) -> RequestAuthenticator:
    return RequestAuthenticator(
        SecuritySettings(
            oidc=OidcConfig(
                issuer=ISSUER,
                audience=AUDIENCE,
                jwks_url="https://idp.example.test/.well-known/jwks.json",
                leeway_seconds=0,
            )
        ),
        key_resolver=lambda token: public_key,
    )


def token(private_key: object, **updates: object) -> str:
    now = datetime.now(UTC)
    claims: dict[str, object] = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-123",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "roles": ["maker", "deployer"],
    }
    claims.update(updates)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "test-key"})


def authenticate(auth: RequestAuthenticator, value: str):
    return auth.authenticate(
        authorization=f"Bearer {value}",
        development_actor=None,
    )


def test_valid_signature_claims_and_roles(keys: tuple[object, object]) -> None:
    private, public = keys
    auth = authenticator(public)
    principal = authenticate(auth, token(private))
    assert principal.subject == "user-123"
    assert principal.roles == {"maker", "deployer"}
    assert auth.require_role(principal, "deployer") == "user-123"
    with pytest.raises(AuthorizationError, match="checker"):
        auth.require_role(principal, "checker")


@pytest.mark.parametrize(
    ("updates", "key_kind"),
    [
        ({"iss": "https://attacker.invalid"}, "valid"),
        ({"aud": "different-api"}, "valid"),
        ({"exp": datetime.now(UTC) - timedelta(seconds=1)}, "valid"),
        ({}, "wrong"),
    ],
)
def test_invalid_issuer_audience_expiry_and_signature_are_rejected(
    keys: tuple[object, object], updates: dict[str, object], key_kind: str
) -> None:
    private, public = keys
    signing_key = private
    if key_kind == "wrong":
        signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthenticationError, match="validation failed"):
        authenticate(authenticator(public), token(signing_key, **updates))


def test_development_headers_require_explicit_flag_and_are_rejected_in_production() -> None:
    locked = RequestAuthenticator(SecuritySettings())
    with pytest.raises(AuthenticationError, match="headers are disabled"):
        locked.authenticate(authorization=None, development_actor="maker")
    local = RequestAuthenticator(SecuritySettings.local_development())
    principal = local.authenticate(authorization=None, development_actor="maker")
    assert principal.subject == "maker"
    assert principal.roles == {"maker", "checker", "reviewer", "deployer"}


def local_authenticator(tmp_path: Path) -> RequestAuthenticator:
    users = tmp_path / "users.json"
    users.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "maker",
                        "passwordHash": PasswordHasher().hash("correct horse battery staple"),
                        "roles": ["maker"],
                        "sessionVersion": 3,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    secret = tmp_path / "session-secret"
    secret.write_text("a-session-secret-with-at-least-thirty-two-bytes", encoding="utf-8")
    return RequestAuthenticator(
        SecuritySettings(
            local_auth=LocalAuthConfig(
                users_file=users,
                session_secret_file=secret,
                public_origin="https://rule.example.test",
            )
        )
    )


def test_local_login_session_csrf_and_header_rejection(tmp_path: Path) -> None:
    auth = local_authenticator(tmp_path)
    with pytest.raises(AuthenticationError, match="invalid username or password"):
        auth.login("maker", "wrong password")

    login = auth.login("maker", "correct horse battery staple")
    principal = auth.authenticate(
        authorization=None,
        development_actor=None,
        session_cookie=login.session_token,
    )
    assert principal.subject == "maker"
    assert principal.roles == {"maker"}
    auth.verify_unsafe_request(
        principal,
        csrf_token=principal.csrf_token,
        origin="https://rule.example.test",
    )
    with pytest.raises(AuthenticationError, match="CSRF"):
        auth.verify_unsafe_request(
            principal,
            csrf_token="wrong",
            origin="https://rule.example.test",
        )
    with pytest.raises(AuthenticationError, match="origin"):
        auth.verify_unsafe_request(
            principal,
            csrf_token=principal.csrf_token,
            origin="https://attacker.invalid",
        )
    with pytest.raises(AuthenticationError, match="header-based"):
        auth.authenticate(
            authorization=None,
            development_actor="impersonated",
            session_cookie=login.session_token,
        )
