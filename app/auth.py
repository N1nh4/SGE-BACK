from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_senha(senha: str) -> str:
    return pwd_context.hash(senha)


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return pwd_context.verify(senha_plana, senha_hash)


def criar_token(usuario_id: int, expires_minutes: int = 60 * 24) -> str:
    expiracao = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": str(usuario_id), "exp": expiracao}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decodificar_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        return None
