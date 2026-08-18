from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from .auth import decodificar_token
from .database import get_db
from .models import Usuario


def get_usuario_atual(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
) -> Usuario:
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Formato de token inválido",
        )

    token = authorization.removeprefix("Bearer ")
    usuario_id = decodificar_token(token)

    if usuario_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

    usuario = db.get(Usuario, usuario_id)

    if usuario is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado",
        )

    return usuario


def require_role(*papeis: str):
    def _verificar(
        usuario: Usuario = Depends(get_usuario_atual),
    ):
        if usuario.papel not in papeis:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sem permissão para acessar este recurso",
            )
        return usuario

    return Depends(_verificar)
