"""Tradução dos erros de validação do Pydantic para português.

Sem isso o 422 volta como "String should have at most 255 characters", que
não diz nada útil para quem está preenchendo o formulário.
"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Nome do campo na API -> como chamamos no formulário.
CAMPOS_PT = {
    "nome": "nome",
    "meta": "meta",
    "orientacao": "orientação",
    "rotulo_x": "numerador (X)",
    "rotulo_y": "denominador (Y)",
    "prazo": "prazo",
    "prazo_reenvio": "prazo de reenvio",
    "codigo": "código",
    "ppa": "PPA",
    "loa": "LOA",
    "email": "e-mail",
    "senha": "senha",
    "papel": "perfil",
    "status": "status",
    "justificativa": "justificativa",
    "objetivo_id": "objetivo estratégico",
    "planejamento_id": "planejamento",
    "unidade_id": "unidade",
    "unidade_ids": "unidades",
    "etapas": "etapas",
    "indicadores": "indicadores",
    "etapa_id": "etapa",
    "arquivo": "arquivo",
}

# "indicadores.0.nome" vira "indicador 1: nome" em vez de "indicadores.0.nome".
SINGULAR = {
    "indicadores": "indicador",
    "etapas": "etapa",
}

# Erros que não vêm do formulário e só poluem a mensagem.
LOCAIS_IGNORADOS = {"header", "cookie"}


def _rotular(loc: tuple) -> str:
    partes: list[str] = []
    for parte in loc:
        if isinstance(parte, int):
            if partes:
                base = partes[-1]
                partes[-1] = f"{SINGULAR.get(base, base)} {parte + 1}"
            continue
        partes.append(CAMPOS_PT.get(str(parte), str(parte)))
    return ": ".join(partes) if partes else "dados"


def _traduzir(tipo: str, ctx: dict) -> str:
    if tipo in ("string_too_long", "too_long"):
        limite = ctx.get("max_length") or ctx.get("max_length_items")
        if limite:
            return f"deve ter no máximo {limite} caracteres"
        return "é longo demais"
    if tipo in ("string_too_short", "too_short"):
        minimo = ctx.get("min_length")
        if minimo == 1:
            return "não pode ficar em branco"
        return f"precisa de pelo menos {minimo} caracteres"
    if tipo == "missing":
        return "é obrigatório"
    if tipo in ("date_parsing", "date_from_datetime_parsing", "date_type"):
        return "não é uma data válida"
    if tipo in ("int_parsing", "int_type", "float_parsing"):
        return "não é um número válido"
    if tipo == "bool_parsing":
        return "não é um valor válido"
    if tipo == "list_type":
        return "não é uma lista válida"
    if tipo == "dict_type":
        return "não é um conjunto de dados válido"
    if tipo == "string_type":
        return "não é um texto válido"
    if tipo == "value_error":
        return ""
    return ""


async def tratar_validacao(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    mensagens: list[str] = []
    for erro in exc.errors():
        loc = tuple(erro.get("loc", ()))
        # O primeiro item é sempre "body" e não ajuda o usuário.
        if loc and loc[0] in ("body", "query", "path"):
            loc = loc[1:]
        # Autorização ausente não é erro de formulário e não deve aparecer.
        if loc and loc[0] in LOCAIS_IGNORADOS:
            continue

        motivo = _traduzir(str(erro.get("type", "")), dict(erro.get("ctx") or {}))
        if not motivo:
            # Validador customizado: a mensagem já é nossa.
            motivo = str(erro.get("msg", "valor inválido"))

        rotulo = _rotular(loc)
        mensagens.append(f"{rotulo}: {motivo}" if rotulo else motivo)

    # Mesma mensagem repetida em campos diferentes continua aparecendo uma vez
    # por campo, sem duplicar.
    if not mensagens:
        mensagens.append("Dados inválidos.")

    return JSONResponse(
        status_code=422,
        content={"detail": "; ".join(dict.fromkeys(mensagens))},
    )
