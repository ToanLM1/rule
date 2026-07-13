from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from brp.security import (
    AuthenticationError,
    AuthorizationError,
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
