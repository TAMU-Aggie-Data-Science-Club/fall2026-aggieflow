"""Sign-in with Clerk (WHATS_LEFT 3.4).

Off until CLERK_ISSUER is set to the Clerk app's Frontend API URL (Clerk dashboard,
API keys page, e.g. https://<app>.clerk.accounts.dev). Without it the API works as
before, with no sign-in.

When it's on, /chat needs `Authorization: Bearer <Clerk session token>` (the web app
sends it). The token is checked against Clerk's public keys at
<issuer>/.well-known/jwks.json: RS256 signature, expiry, issuer, and its authorized
party (`azp`, the site that asked for it) must be one of ALLOWED_ORIGINS.

The signed-in user becomes a User: their Clerk user id, and the slug of their active
Clerk Organization, or DEFAULT_ORG ("tamu") for anyone without one, which leaves room
for other schools later. Conversations belong to one user: the thread id kept in the
checkpointer is <org>/<user id>/<thread id>, so one user's thread id can't open someone
else's conversation.
"""

import logging
import os
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

DEFAULT_ORG = "tamu"
SIGN_IN = "Sign in to use AggieFlow."
EXPIRED = "Your sign-in has expired. Sign in again."


@dataclass(frozen=True)
class User:
    id: str
    org: str = DEFAULT_ORG


def issuer() -> str | None:
    """The Clerk issuer when sign-in is on, else None."""
    return os.getenv("CLERK_ISSUER", "").strip().rstrip("/") or None


@lru_cache(maxsize=4)
def _jwks(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def signing_key(token: str, iss: str):
    """Clerk's public key for this token (fetched once, then cached)."""
    return _jwks(f"{iss}/.well-known/jwks.json").get_signing_key_from_jwt(token).key


def allowed_parties() -> set[str]:
    origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
    return {o.strip().rstrip("/") for o in origins if o.strip()}


def org_of(claims: dict) -> str:
    """The active Organization's slug: `o.slg` in Clerk's v2 tokens, `org_slug` in v1."""
    o = claims.get("o")
    slug = o.get("slg") if isinstance(o, dict) else claims.get("org_slug")
    return slug if isinstance(slug, str) and slug else DEFAULT_ORG


def verify(token: str) -> User:
    """The user a Clerk session token belongs to. 401 if it isn't valid, 503 if Clerk's
    keys can't be fetched."""
    iss = issuer()
    try:
        claims = jwt.decode(token, signing_key(token, iss), algorithms=["RS256"], issuer=iss,
                            options={"require": ["exp", "iat", "iss", "sub"]}, leeway=5)
    except jwt.PyJWKClientConnectionError:
        logger.exception("Couldn't fetch Clerk's keys")
        raise HTTPException(status_code=503, detail="Sign-in isn't working right now. Try again in a minute.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail=EXPIRED, headers={"WWW-Authenticate": "Bearer"})
    azp = claims.get("azp")
    if azp is not None and str(azp).rstrip("/") not in allowed_parties():
        raise HTTPException(status_code=401, detail=EXPIRED, headers={"WWW-Authenticate": "Bearer"})
    return User(id=claims["sub"], org=org_of(claims))


def current_user(authorization: str | None = Header(default=None)) -> User | None:
    """FastAPI dependency: the signed-in User, or None when sign-in is off."""
    if issuer() is None:
        return None
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail=SIGN_IN, headers={"WWW-Authenticate": "Bearer"})
    return verify(token.strip())


def scoped_thread(thread_id: str, user: User | None) -> str:
    """The checkpointer's thread id: the user's own space when signed in."""
    return thread_id if user is None else f"{user.org}/{user.id}/{thread_id}"
