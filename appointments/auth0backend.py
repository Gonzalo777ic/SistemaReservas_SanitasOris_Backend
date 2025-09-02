import requests
from jose import jwt
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework import exceptions
from django.contrib.auth.models import AnonymousUser


class Auth0User:
    """Pequeño wrapper para que DRF trate el payload como usuario válido"""

    def __init__(self, payload):
        self.payload = payload
        self.username = payload.get("sub")  # ID único de Auth0
        self.email = payload.get("email")  # 👈 puede venir en el token
        # mapear roles
        self.role = None
        roles = payload.get("https://sanitasoris.com/claims/roles", [])
        if roles:
            self.role = roles[0]  # si tienes múltiples roles, ajusta según necesidad

    @property
    def is_authenticated(self):
        return True

    def __str__(self):
        return self.username or "Auth0User"


class Auth0JSONWebTokenAuthentication(BaseAuthentication):
    def authenticate(self, request):
        auth = request.headers.get("Authorization", None)
        if not auth:
            return None

        parts = auth.split()
        if parts[0].lower() != "bearer":
            return None
        elif len(parts) == 1:
            raise exceptions.AuthenticationFailed("Token not found")
        elif len(parts) > 2:
            raise exceptions.AuthenticationFailed(
                "Authorization header must be Bearer token"
            )

        token = parts[1]
        try:
            payload = self.decode_jwt(token)
        except Exception as e:
            raise exceptions.AuthenticationFailed(f"Invalid token: {str(e)}")

        user = Auth0User(payload)
        return (user, token)  # ✅ ahora sí DRF lo trata como usuario

    def decode_jwt(self, token):
        jwks_url = f"https://{settings.AUTH0_DOMAIN}/.well-known/jwks.json"
        jwks = requests.get(jwks_url).json()

        unverified_header = jwt.get_unverified_header(token)
        rsa_key = {}
        for key in jwks["keys"]:
            if key["kid"] == unverified_header["kid"]:
                rsa_key = {
                    "kty": key["kty"],
                    "kid": key["kid"],
                    "use": key["use"],
                    "n": key["n"],
                    "e": key["e"],
                }

        if not rsa_key:
            raise exceptions.AuthenticationFailed("No matching JWK found.")

        return jwt.decode(
            token,
            rsa_key,
            algorithms=settings.ALGORITHMS,
            audience=settings.API_IDENTIFIER,
            issuer=f"https://{settings.AUTH0_DOMAIN}/",
        )
