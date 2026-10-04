"""Verifies a Google Identity Services ID token (the "credential" the sign-in button returns).

Google's tokeninfo endpoint checks the signature and expiry for us; we then check the token
was issued to *our* client ID, that Google has verified the email address, and that the
account belongs to the university's Google Workspace domain (e.g. ub.edu.ph). Guests sign
up with email and password instead.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


class GoogleTokenError(Exception):
    pass


@dataclass
class GoogleIdentity:
    sub: str
    email: str
    name: str
    picture: str | None


def check_claims(claims: dict, client_id: str, domain: str) -> GoogleIdentity:
    """Turn verified token claims into an identity, or refuse them."""
    if claims.get("aud") != client_id:
        raise GoogleTokenError("This sign-in token was issued for a different app.")
    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise GoogleTokenError("This sign-in token was not issued by Google.")
    if str(claims.get("email_verified")).lower() != "true":
        raise GoogleTokenError("Your Google email address is not verified.")

    email = str(claims.get("email", ""))
    if domain:
        # `hd` is set by Google only for Workspace accounts, so a personal Gmail account
        # renamed to look like the university cannot pass.
        in_domain = claims.get("hd") == domain and email.lower().endswith(f"@{domain}")
        if not in_domain:
            raise GoogleTokenError(
                f"Google sign-in is only for @{domain} accounts. "
                "Guests can create an account with their email instead."
            )

    return GoogleIdentity(
        sub=claims["sub"],
        email=email,
        name=claims.get("name") or email.split("@")[0],
        picture=claims.get("picture"),
    )


def verify_id_token(credential: str, client_id: str, domain: str) -> GoogleIdentity:
    if not client_id:
        raise GoogleTokenError("Google sign-in is not configured on the server.")

    url = f"{TOKENINFO_URL}?{urllib.parse.urlencode({'id_token': credential})}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            claims = json.load(response)
    except urllib.error.HTTPError as exc:
        raise GoogleTokenError("Google rejected the sign-in token.") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GoogleTokenError("Could not reach Google to verify the sign-in.") from exc

    return check_claims(claims, client_id, domain)
