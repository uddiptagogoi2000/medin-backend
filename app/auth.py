from fastapi import Request, HTTPException
from jose import jwt
import requests

CLERK_JWKS_URL = "https://adapted-turtle-21.clerk.accounts.dev/.well-known/jwks.json"
CLERK_ISSUER = "https://adapted-turtle-21.clerk.accounts.dev"

jwks = requests.get(CLERK_JWKS_URL).json()

def verify_token(request: Request):
    auth_header = request.headers.get("Authorization")
    print("AUTH HEADER:", auth_header)
    if not auth_header:
        raise HTTPException(status_code=401, detail="No token")

    token = auth_header.split(" ")[1]
    print("TOKEN:", token[:30])
    try:
        payload = jwt.decode(
            token,
            jwks,
            algorithms=["RS256"],
            audience=None,
            issuer=CLERK_ISSUER,
        )
        return payload
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")
