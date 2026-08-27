"""Catálogo de ações permitidas por página.

Define, para cada página (chave), o conjunto de ações (funcionalidades) que
ela *pode* ter. O configurador usa esse catálogo para exibir apenas as ações
relevantes de cada página, em vez de um conjunto fixo global
(ver/criar/editar/excluir).

Ações de escrita são aplicadas nos endpoints pelos decoradores
``require_permission(pagina, acao)``; a ação ``ver`` garante acesso de leitura.
"""

ACAO_LABELS: dict[str, str] = {
    "ver": "Ver",
    "criar": "Criar",
    "editar": "Editar",
    "excluir": "Excluir",
    "aprovar": "Aprovar",
    "relatorio": "Gerar relatório",
    "ler": "Marcar como lida",
}

# Ordem de exibição padrão das ações no configurador.
ORDEM_ACOES: list[str] = ["ver", "criar", "editar", "excluir", "aprovar", "relatorio", "ler"]

CATALOGO: dict[str, list[str]] = {
    "/indicadores": ["ver"],
    "/objetivos": ["ver", "criar", "editar", "excluir"],
    "/planejamento": ["ver", "criar", "editar", "excluir", "relatorio"],
    "/comprovacoes": ["ver", "criar", "excluir"],
    "/unidades": ["ver", "criar", "editar", "excluir"],
    "/validacao": ["ver", "aprovar"],
    "/notificacoes": ["ver", "ler"],
    "/configurador": ["ver", "criar", "editar", "excluir"],
}


def acoes_de_pagina(chave: str | None) -> list[str]:
    if chave is None:
        return []
    return list(CATALOGO.get(chave, []))


def acoes_ordenadas(chave: str | None) -> list[str]:
    acoes = set(acoes_de_pagina(chave))
    return [a for a in ORDEM_ACOES if a in acoes]
