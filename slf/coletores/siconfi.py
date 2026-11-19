"""SICONFI (Tesouro Nacional): RGF e RREO da prefeitura. API aberta, sem chave."""
from __future__ import annotations

from datetime import date

from ..config import ente
from ..http import Cliente
from ..raw import Coleta

BASE = "https://apidatalake.tesouro.gov.br/ords/siconfi/tt"


def _todas(cli: Cliente, endpoint: str, params: dict) -> list:
    linhas, offset = [], 0
    while True:
        resp = cli.get_json(f"{BASE}/{endpoint}", {**params, "offset": offset}) or {}
        itens = resp.get("items", [])
        linhas.extend(itens)
        if not resp.get("hasMore") or not itens:
            return linhas
        offset += len(itens)


def coletar() -> Coleta:
    cfg = ente()
    col = Coleta("siconfi")
    cli = Cliente(pausa=0.5)
    try:
        rgf, rreo = [], []
        for ano in range(cfg["inicio"].year, date.today().year + 1):
            for periodo in (1, 2, 3):
                rgf += _todas(cli, "rgf", {
                    "an_exercicio": ano, "in_periodicidade": "Q", "nr_periodo": periodo,
                    "co_tipo_demonstrativo": "RGF", "co_poder": "E", "id_ente": cfg["ibge"]})
            for periodo in range(1, 7):
                rreo += _todas(cli, "rreo", {
                    "an_exercicio": ano, "nr_periodo": periodo, "co_tipo_demonstrativo": "RREO",
                    "no_anexo": "RREO-Anexo 01", "id_ente": cfg["ibge"]})
            print(f"  siconfi: {ano} ok")
        col.salvar("rgf", rgf, f"{BASE}/rgf")
        col.salvar("rreo", rreo, f"{BASE}/rreo")
        print(f"  siconfi: {len(rgf)} linhas de RGF, {len(rreo)} de RREO")
        col.concluir()
    finally:
        cli.fechar()
    return col
