"""Transferegov, transferências especiais (emendas Pix). API PostgREST aberta, sem chave."""
from __future__ import annotations

from ..config import ente
from ..http import Cliente
from ..raw import Coleta

BASE = "https://api.transferegov.gestao.gov.br/transferenciasespeciais"
PAGINA = 1000
LOTE = 80  # ids por filtro "in.(...)"


def _todas(cli: Cliente, tabela: str, filtro: dict) -> list:
    linhas, offset = [], 0
    while True:
        params = {**filtro, "limit": PAGINA, "offset": offset}
        pagina = cli.get_json(f"{BASE}/{tabela}", params) or []
        linhas.extend(pagina)
        if len(pagina) < PAGINA:
            return linhas
        offset += PAGINA


def _por_ids(cli: Cliente, tabela: str, coluna: str, ids: list) -> list:
    linhas = []
    ids = sorted({i for i in ids if i is not None})
    for i in range(0, len(ids), LOTE):
        lote = ",".join(str(x) for x in ids[i:i + LOTE])
        linhas.extend(_todas(cli, tabela, {coluna: f"in.({lote})"}))
    return linhas


def coletar() -> Coleta:
    cfg = ente()
    col = Coleta("transferegov")
    cli = Cliente()
    try:
        planos = _todas(cli, "plano_acao_especial",
                        {"cnpj_beneficiario_plano_acao": f"eq.{cfg['cnpj_municipio']}"})
        col.salvar("plano_acao_especial", planos, f"{BASE}/plano_acao_especial")
        ids_plano = [p["id_plano_acao"] for p in planos]
        print(f"  transferegov: {len(planos)} planos de ação")

        por_plano = {}
        for tabela in ("empenho_especial", "plano_trabalho_especial", "executor_especial",
                       "relatorio_gestao_especial", "relatorio_gestao_novo_especial"):
            por_plano[tabela] = _por_ids(cli, tabela, "id_plano_acao", ids_plano)
            col.salvar(tabela, por_plano[tabela], f"{BASE}/{tabela}")
            print(f"  transferegov: {tabela} {len(por_plano[tabela])}")

        dh = _por_ids(cli, "documento_habil_especial", "id_empenho",
                      [e["id_empenho"] for e in por_plano["empenho_especial"]])
        col.salvar("documento_habil_especial", dh, f"{BASE}/documento_habil_especial")
        ob = _por_ids(cli, "ordem_pagamento_ordem_bancaria_especial", "id_dh",
                      [d["id_dh"] for d in dh])
        col.salvar("ordem_pagamento_ordem_bancaria_especial", ob,
                   f"{BASE}/ordem_pagamento_ordem_bancaria_especial")
        metas = _por_ids(cli, "meta_especial", "id_executor",
                         [e["id_executor"] for e in por_plano["executor_especial"]])
        col.salvar("meta_especial", metas, f"{BASE}/meta_especial")
        print(f"  transferegov: {len(dh)} documentos hábeis, {len(ob)} ordens, {len(metas)} metas")
        col.concluir()
    finally:
        cli.fechar()
    return col
