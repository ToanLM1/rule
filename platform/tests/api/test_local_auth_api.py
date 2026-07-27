import json
from pathlib import Path

from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from brp.api.app import create_app
from brp.security import LocalAuthConfig, SecuritySettings

ORIGIN = "https://testserver"


def settings(tmp_path: Path) -> SecuritySettings:
    users = tmp_path / "users.json"
    users.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "maker",
                        "passwordHash": PasswordHasher().hash("maker-password-123"),
                        "roles": ["maker"],
                        "sessionVersion": 1,
                    },
                    {
                        "username": "approver",
                        "passwordHash": PasswordHasher().hash("approver-password-123"),
                        "roles": ["checker", "reviewer", "deployer"],
                        "sessionVersion": 1,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    secret = tmp_path / "session-secret"
    secret.write_text("test-session-secret-with-more-than-thirty-two-bytes", encoding="utf-8")
    return SecuritySettings(
        local_auth=LocalAuthConfig(
            users_file=users,
            session_secret_file=secret,
            public_origin=ORIGIN,
        )
    )


def test_local_login_protects_business_api_and_enforces_csrf(tmp_path: Path) -> None:
    api = TestClient(create_app(security=settings(tmp_path)), base_url=ORIGIN)
    assert api.get("/api/v1/context").status_code == 401
    assert api.post(
        "/api/v1/auth/login",
        json={"username": "maker", "password": "wrong"},
    ).status_code == 401

    login = api.post(
        "/api/v1/auth/login",
        json={"username": "maker", "password": "maker-password-123"},
    )
    assert login.status_code == 200
    assert login.json()["roles"] == ["maker"]
    assert login.cookies["brp_session"]
    assert api.get("/api/v1/auth/me").json()["username"] == "maker"
    assert api.get("/api/v1/context").status_code == 200

    without_csrf = api.post("/api/v1/auth/logout", headers={"Origin": ORIGIN})
    assert without_csrf.status_code == 401
    logout = api.post(
        "/api/v1/auth/logout",
        headers={
            "Origin": ORIGIN,
            "X-CSRF-Token": login.json()["csrfToken"],
        },
    )
    assert logout.status_code == 200
    assert api.get("/api/v1/auth/me").status_code == 401
