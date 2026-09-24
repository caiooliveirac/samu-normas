"""Federação com o escala — lado do DESTINO (mesmo contrato do Huddle e do plantões).

Fluxo:
  /painel/entrar/  -> 302 {ESCALA_URL}/api/auth/handoff?para=samu-normas
  escala (com sessão) -> 302 {url deste serviço}/api/auth/sso?token=<jwt>
  /api/auth/sso    valida o token e abre a sessão Django local.

Token: JWT HS256 de 60 s assinado com o AUTH_SECRET do escala (aqui chamado
ESCALA_FEDERACAO_SECRET). Claims: tipo="escala-handoff", sub=e-mail,
aud=id do destino, exp, e opcionais nome/perfil/usuarioId.

Stdlib em vez de PyJWT: verificar um HS256 são poucas linhas e não vale uma
dependência a mais.
"""
import base64
import hashlib
import hmac
import json
import time

TIPO_HANDOFF = "escala-handoff"


def _b64d(parte: str) -> bytes:
    return base64.urlsafe_b64decode(parte + "=" * (-len(parte) % 4))


def ler_token_handoff(token: str, segredo: str, meu_id: str, agora: float | None = None) -> dict | None:
    """Claims do token se assinatura, tipo, aud e exp conferem; senão None."""
    if not token or not segredo:
        return None
    try:
        cab, corpo, assinatura = token.split(".")
        if json.loads(_b64d(cab)).get("alg") != "HS256":
            return None
        esperado = hmac.new(segredo.encode(), f"{cab}.{corpo}".encode(), hashlib.sha256).digest()
        if not hmac.compare_digest(esperado, _b64d(assinatura)):
            return None
        claims = json.loads(_b64d(corpo))
    except (ValueError, TypeError, AttributeError):
        return None
    if not isinstance(claims, dict):
        return None
    aud = claims.get("aud")
    if meu_id not in (aud if isinstance(aud, list) else [aud]):
        return None
    exp = claims.get("exp")
    if not isinstance(exp, (int, float)) or exp <= (time.time() if agora is None else agora):
        return None
    if claims.get("tipo") != TIPO_HANDOFF or not isinstance(claims.get("sub"), str) or "@" not in claims["sub"]:
        return None
    return claims
