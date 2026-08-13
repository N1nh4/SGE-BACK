from sqlalchemy import func, select

from . import models
from .database import SessionLocal

DADOS_OBJETIVOS = [
    {
        "codigo": "OE1",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Integrar, qualificar, desenvolver e valorizar os colaboradores",
        "descricao": (
            "Aumentar a participação de mercado em 10 pontos percentuais nos "
            "próximos 12 meses, com foco nas regiões Norte e Nordeste."
        ),
    },
    {
        "codigo": "OE2",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Promover o bem-estar e o fortalecimento do ambiente organizacional",
        "descricao": (
            "Otimizar processos internos e reduzir custos operacionais em até "
            "15% sem comprometer a qualidade do atendimento."
        ),
    },
    {
        "codigo": "OE3",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Melhorar experiência do cliente",
        "descricao": (
            "Alcançar índice de satisfação (NPS) acima de 80, implementando "
            "melhorias contínuas nos canais de atendimento e no pós-venda."
        ),
    },
    {
        "codigo": "OE4",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Inovação em produtos",
        "descricao": (
            "Lançar pelo menos três novos produtos no portfólio no próximo "
            "ano, investindo em P&D e em parcerias estratégicas."
        ),
    },
    {
        "codigo": "OE5",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Desenvolver talentos",
        "descricao": (
            "Implementar um programa de desenvolvimento de lideranças e de "
            "capacitação técnica para todos os colaboradores."
        ),
    },
    {
        "codigo": "OE6",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Sustentabilidade",
        "descricao": (
            "Adotar práticas sustentáveis e reduzir a pegada de carbono da "
            "operação em 30% até o fim do ano."
        ),
    },
    {
        "codigo": "OE7",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Internacionalização",
        "descricao": (
            "Estruturar a entrada em novos mercados da América Latina, com "
            "metas de receita definidas por país."
        ),
    },
    {
        "codigo": "OE8",
        "ppa": "PPA 2024-2027",
        "loa": "LOA 2025",
        "nome": "Digitalização",
        "descricao": (
            "Digitalizar os principais processos administrativos e "
            "financeiros, reduzindo o tempo de ciclo em 40%."
        ),
    },
]


def seed_objetivos() -> None:
    with SessionLocal() as db:
        total = db.scalar(select(func.count()).select_from(models.Objetivo))
        if total:
            return
        db.add_all(models.Objetivo(**dados) for dados in DADOS_OBJETIVOS)
        db.commit()
