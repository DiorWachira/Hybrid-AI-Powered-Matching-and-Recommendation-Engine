"""Verify the ID token that Google Identity Services hands the browser after "Sign in with Google"."""
import jwt

GOOGLE_CERTS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# Caches Google's signing keys between requests; an unknown key ID triggers one refetch (key rotation).
_keys = jwt.PyJWKClient(GOOGLE_CERTS_URL, cache_keys=True, lifespan=3600, timeout=10)


class GoogleUnavailable(Exception):
    """Google's signing keys could not be fetched, so no token can be checked right now."""


def verified_email(credential: str, client_id: str) -> str:
    """The lower-cased email of a valid token issued to this app; ValueError for any token that fails a check."""
    try:
        key = _keys.get_signing_key_from_jwt(credential)
    except jwt.PyJWKClientConnectionError as error:
        raise GoogleUnavailable from error
    except jwt.PyJWKClientError as error:
        raise ValueError("unknown signing key") from error
    except jwt.InvalidTokenError as error:
        raise ValueError("malformed token") from error
    try:
        claims = jwt.decode(credential, key.key, algorithms=["RS256"], audience=client_id, issuer=GOOGLE_ISSUERS, options={"require": ["exp", "iat", "iss", "aud", "sub", "email"]}, leeway=30)
    except jwt.InvalidTokenError as error:
        raise ValueError("invalid token") from error
    if claims.get("email_verified") is not True:
        raise ValueError("Google has not verified this email address")
    return str(claims["email"]).strip().lower()
