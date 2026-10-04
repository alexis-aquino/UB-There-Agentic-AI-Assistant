import uuid

import pytest
from fastapi.testclient import TestClient

from app.auth.google import GoogleIdentity, GoogleTokenError, check_claims
from app.main import app
from app.routers import auth

client = TestClient(app)
DEFAULT = "12345678"


CLIENT = "test-client.apps.googleusercontent.com"


def unique_email():
    """A guest address — anything outside the university domain."""
    return f"guest-{uuid.uuid4().hex[:8]}@example.com"


def ub_email():
    return f"student-{uuid.uuid4().hex[:8]}@ub.edu.ph"


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_config_exposes_google_client_and_default_password():
    body = client.get("/api/auth/config").json()
    assert body["google_client_id"] == CLIENT
    assert body["google_domain"] == "ub.edu.ph"
    assert body["default_password"] == DEFAULT


def test_signup_without_password_uses_the_default():
    email = unique_email()
    created = client.post("/api/auth/signup", json={"name": "Ana", "email": email})
    assert created.status_code == 201
    assert created.json()["user"]["default_password"] is True
    assert created.json()["user"]["guest"] is True

    login = client.post("/api/auth/login", json={"email": email, "password": DEFAULT})
    assert login.status_code == 200
    assert login.json()["user"]["name"] == "Ana"


def test_login_is_case_insensitive_on_email_and_rejects_wrong_password():
    email = unique_email()
    client.post("/api/auth/signup", json={"name": "Ben", "email": email})
    assert client.post("/api/auth/login", json={"email": email.upper(), "password": DEFAULT}).is_success
    wrong = client.post("/api/auth/login", json={"email": email, "password": "nope-nope"})
    assert wrong.status_code == 401


def test_duplicate_signup_is_rejected():
    email = unique_email()
    client.post("/api/auth/signup", json={"name": "Cy", "email": email})
    assert client.post("/api/auth/signup", json={"name": "Cy", "email": email}).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "", "email": "a@b.co"},
        {"name": "A", "email": "not-an-email"},
        {"name": "A", "email": "a@b.co", "password": "short"},
        {"name": "   ", "email": "a@b.co"},
        {"name": "A", "email": "   "},
        {"name": "A"},
        {"email": "a@b.co"},
    ],
)
def test_signup_validates_input(payload):
    assert client.post("/api/auth/signup", json=payload).status_code == 422


def test_me_requires_a_valid_token():
    assert client.get("/api/auth/me").status_code == 401
    assert client.get("/api/auth/me", headers=bearer("1.9999999999.forged")).status_code == 401

    token = client.post("/api/auth/signup", json={"name": "Di", "email": unique_email()}).json()["token"]
    assert client.get("/api/auth/me", headers=bearer(token)).json()["name"] == "Di"


def test_change_password_clears_the_default_flag():
    email = unique_email()
    token = client.post("/api/auth/signup", json={"name": "Ed", "email": email}).json()["token"]

    bad = client.post(
        "/api/auth/password",
        json={"current_password": "wrong-one", "new_password": "a-better-one"},
        headers=bearer(token),
    )
    assert bad.status_code == 400

    good = client.post(
        "/api/auth/password",
        json={"current_password": DEFAULT, "new_password": "a-better-one"},
        headers=bearer(token),
    )
    assert good.json()["default_password"] is False
    assert client.post("/api/auth/login", json={"email": email, "password": "a-better-one"}).is_success


@pytest.fixture
def fake_google(monkeypatch):
    identities = {}

    def verify(credential, client_id, domain):
        if credential not in identities:
            raise GoogleTokenError("Google rejected the sign-in token.")
        return identities[credential]

    monkeypatch.setattr(auth, "verify_id_token", verify)
    return identities


def test_guests_cannot_sign_up_with_a_university_address():
    """With Google on, @ub.edu.ph identities only come through Google."""
    response = client.post("/api/auth/signup", json={"name": "Fake", "email": ub_email()})
    assert response.status_code == 400
    assert "Google" in response.json()["detail"]


def test_google_signup_creates_account_with_default_password(fake_google):
    email = ub_email()
    fake_google["x" * 30] = GoogleIdentity(sub=uuid.uuid4().hex, email=email, name="Fe", picture=None)

    first = client.post("/api/auth/google", json={"credential": "x" * 30}).json()
    assert first["created"] is True
    assert first["user"]["google_linked"] is True
    assert first["user"]["guest"] is False

    again = client.post("/api/auth/google", json={"credential": "x" * 30}).json()
    assert again["created"] is False
    assert again["user"]["id"] == first["user"]["id"]

    # The same account also works with email + the default password.
    assert client.post("/api/auth/login", json={"email": email, "password": DEFAULT}).is_success


def test_google_links_to_existing_email_account(fake_google):
    """e.g. the seeded student@ub.edu.ph account, made before Google sign-in was on."""
    email = ub_email()
    existing = auth.get_store().create(email, "Gi")
    fake_google["y" * 30] = GoogleIdentity(sub=uuid.uuid4().hex, email=email, name="Gi", picture=None)

    body = client.post("/api/auth/google", json={"credential": "y" * 30}).json()
    assert body["created"] is False
    assert body["user"]["id"] == existing.id


def test_google_rejects_bad_token(fake_google):
    assert client.post("/api/auth/google", json={"credential": "z" * 30}).status_code == 401


def claims(**overrides):
    base = {
        "aud": CLIENT,
        "iss": "https://accounts.google.com",
        "email_verified": "true",
        "email": "juan@ub.edu.ph",
        "hd": "ub.edu.ph",
        "sub": "123",
        "name": "Juan",
    }
    return {**base, **overrides}


def test_claims_from_the_university_domain_are_accepted():
    assert check_claims(claims(), CLIENT, "ub.edu.ph").email == "juan@ub.edu.ph"


@pytest.mark.parametrize(
    "overrides",
    [
        {"email": "juan@gmail.com", "hd": None},  # personal Google account
        {"hd": None},  # a non-Workspace account can't just claim the address
        {"email": "juan@other.edu.ph", "hd": "other.edu.ph"},  # another school's Workspace
        {"aud": "someone-elses-client"},
        {"email_verified": "false"},
    ],
)
def test_claims_outside_the_rules_are_refused(overrides):
    with pytest.raises(GoogleTokenError):
        check_claims(claims(**overrides), CLIENT, "ub.edu.ph")
