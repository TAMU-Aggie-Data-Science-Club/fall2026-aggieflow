"""Tests for api/auth.py (Clerk sign-in). Tokens are signed here with a test RSA key, so
no Clerk account or network is needed."""

import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

import api.auth
import api.main

ISSUER = "https://aggieflow-test.clerk.accounts.dev"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(key=KEY, alg="RS256", **claims):
    now = int(time.time())
    body = {"iss": ISSUER, "sub": "user_1", "iat": now, "exp": now + 60,
            "azp": "http://localhost:5173", "v": 2, **claims}
    return jwt.encode({k: v for k, v in body.items() if v is not None}, key, algorithm=alg)


def bearer(t):
    return {"Authorization": f"Bearer {t}"}


@pytest.fixture
def seen(monkeypatch):
    """Sign-in on, Clerk's key replaced by the test key; records what answer() got."""
    monkeypatch.setenv("CLERK_ISSUER", ISSUER + "/")  # a trailing slash is fine
    monkeypatch.setenv("ALLOWED_ORIGINS", "http://localhost:5173,https://aggieflow.example")
    monkeypatch.setattr(api.auth, "signing_key", lambda t, iss: KEY.public_key())
    calls = []

    def fake_answer(question, **kwargs):
        calls.append(kwargs)
        return {"answer": "Four.", "sources": [], "documents": [], "trace": [], "calls": []}

    monkeypatch.setattr(api.main, "answer", fake_answer)
    return calls


@pytest.fixture
def client():
    return TestClient(api.main.app)


def test_sign_in_is_off_without_clerk_issuer(client, monkeypatch):
    monkeypatch.delenv("CLERK_ISSUER", raising=False)
    monkeypatch.setattr(api.main, "answer", lambda q, **kw: {"answer": "Four.", "sources": [], "calls": []})
    assert client.post("/chat", json={"question": "q drops?"}).status_code == 200
    assert api.auth.scoped_thread("t1", None) == "t1"


def test_chat_needs_a_sign_in_when_it_is_on(client, seen):
    r = client.post("/chat", json={"question": "q drops?"})
    assert r.status_code == 401 and r.json()["detail"] == "Sign in to use AggieFlow."
    assert client.post("/chat", json={"question": "q drops?"}, headers={"Authorization": "Basic abc"}).status_code == 401
    assert seen == []


def test_a_signed_in_user_gets_their_own_thread_under_tamu(client, seen):
    thread = str(uuid.uuid4())
    r = client.post("/chat", json={"question": "q drops?", "thread_id": thread}, headers=bearer(token()))
    assert r.status_code == 200
    assert r.json()["thread_id"] == thread  # the client keeps using its own id
    assert seen[0]["thread_id"] == f"tamu/user_1/{thread}"
    assert seen[0]["metadata"] == {"via": "api", "user": "user_1", "org": "tamu"}


def test_two_users_with_the_same_thread_id_get_different_threads(client, seen):
    thread = str(uuid.uuid4())
    for user in ("user_1", "user_2"):
        client.post("/chat", json={"question": "hi", "thread_id": thread}, headers=bearer(token(sub=user)))
    assert seen[0]["thread_id"] != seen[1]["thread_id"]


@pytest.mark.parametrize("claims, org", [
    ({"o": {"id": "org_1", "slg": "blinn", "rol": "member"}}, "blinn"),  # v2 tokens
    ({"org_id": "org_1", "org_slug": "blinn", "v": None}, "blinn"),  # v1 tokens
    ({"o": {"id": "org_1"}}, "tamu"),  # no slug
])
def test_the_org_comes_from_the_active_organization(client, seen, claims, org):
    client.post("/chat", json={"question": "hi"}, headers=bearer(token(**claims)))
    assert seen[0]["metadata"]["org"] == org
    assert seen[0]["thread_id"].startswith(f"{org}/user_1/")


@pytest.mark.parametrize("bad", [
    token(exp=int(time.time()) - 60, iat=int(time.time()) - 120),  # expired
    token(iss="https://someone-else.clerk.accounts.dev"),  # another Clerk app
    token(azp="https://evil.example"),  # asked for by a site that isn't ours
    token(key=OTHER_KEY),  # not signed by Clerk
    token(key="a-shared-secret-long-enough-for-hs256-ok", alg="HS256"),  # algorithm swap
    token(sub=None),  # no user
    "not-a-token",
])
def test_bad_tokens_are_refused(client, seen, bad):
    r = client.post("/chat", json={"question": "hi"}, headers=bearer(bad))
    assert r.status_code == 401 and r.json()["detail"] == api.auth.EXPIRED
    assert seen == []


def test_a_token_from_another_allowed_origin_is_accepted(client, seen):
    r = client.post("/chat", json={"question": "hi"}, headers=bearer(token(azp="https://aggieflow.example/")))
    assert r.status_code == 200


def test_clerk_keys_unreachable_is_a_503_not_a_401(client, seen, monkeypatch):
    def down(t, iss):
        raise jwt.PyJWKClientConnectionError("timed out")

    monkeypatch.setattr(api.auth, "signing_key", down)
    r = client.post("/chat", json={"question": "hi"}, headers=bearer(token()))
    assert r.status_code == 503 and seen == []


def test_signing_key_reads_the_issuers_jwks(monkeypatch):
    urls = []

    class FakeJWKS:
        def __init__(self, url, **kwargs):
            urls.append(url)

        def get_signing_key_from_jwt(self, t):
            return type("K", (), {"key": KEY.public_key()})()

    monkeypatch.setattr(api.auth.jwt, "PyJWKClient", FakeJWKS)
    api.auth._jwks.cache_clear()
    try:
        assert api.auth.signing_key(token(), ISSUER) is not None
        api.auth.signing_key(token(), ISSUER)  # the client is reused
    finally:
        api.auth._jwks.cache_clear()
    assert urls == [f"{ISSUER}/.well-known/jwks.json"]
