"""PNCP: contratos, a compra de origem de cada um e os termos aditivos. API aberta."""
from __future__ import annotations

from datetime import date, timedelta

from ..config import ente
from ..http import Cliente
from ..raw import Coleta

CONSULTA = "https://pncp.gov.br/api/consulta/v1"
PNCP = "https://pncp.gov.br/api/pncp/v1"


def _meses(inicio: date, fim: date):
    atual = inicio.replace(day=1)
    while atual <= fim:
        prox = (atual + timedelta(days=32)).replace(day=1)
        yield atual, min(prox - timedelta(days=1), fim)
        atual = prox


# Limites conferidos ao vivo em 18/11/2026: tamanhoPagina vai até 500 (1000 dá 400) e a janela
# entre dataInicial e dataFinal é de no máximo 365 dias (mais que isso dá 422). Mês sem contrato dá 204.
TAMANHO_PAGINA = 500


def _contratos(cli: Cliente, cnpj: str, ini: date, fim: date) -> list:
    linhas, pagina = [], 1
    while True:
        resp = cli.get_json(f"{CONSULTA}/contratos", {
            "dataInicial": ini.strftime("%Y%m%d"), "dataFinal": fim.strftime("%Y%m%d"),
            "cnpjOrgao": cnpj, "pagina": pagina, "tamanhoPagina": TAMANHO_PAGINA}) or {}
        linhas.extend(resp.get("data") or [])
        if not resp.get("paginasRestantes"):
            return linhas
        pagina += 1


def _partes(numero_controle: str):
    """'89814693000160-1-000172/2026' -> ('89814693000160', 2026, 172)"""
    try:
        cnpj, _, resto = numero_controle.split("-", 2)
        seq, ano = resto.split("/")
        return cnpj, int(ano), int(seq)
    except (ValueError, AttributeError):
        return None


def coletar() -> Coleta:
    cfg = ente()
    col = Coleta("pncp")
    cli = Cliente(pausa=0.3)
    try:
        contratos = []
        for orgao in cfg["orgaos_pncp"]:
            for ini, fim in _meses(cfg["inicio"], date.today()):
                contratos += _contratos(cli, orgao["cnpj"], ini, fim)
            print(f"  pncp: {orgao['nome']}: {len(contratos)} contratos até agora")
        # a consulta por data de publicação pode repetir o mesmo contrato
        contratos = list({c["numeroControlePNCP"]: c for c in contratos}.values())
        col.salvar("contratos", contratos, f"{CONSULTA}/contratos")

        compras, falhas = [], 0
        for chave in sorted({c.get("numeroControlePncpCompra") for c in contratos} - {None}):
            partes = _partes(chave)
            if not partes:
                continue
            cnpj, ano, seq = partes
            try:
                compra = cli.get_json(f"{CONSULTA}/orgaos/{cnpj}/compras/{ano}/{seq}")
                if compra:
                    compras.append(compra)
            except Exception:
                falhas += 1
        col.salvar("compras", compras, f"{CONSULTA}/orgaos/{{cnpj}}/compras/{{ano}}/{{seq}}")
        print(f"  pncp: {len(compras)} compras ({falhas} falhas)")

        termos, falhas = [], 0
        for c in contratos:
            # ano e sequencial do registro no PNCP, que podem diferir do anoContrato
            partes = _partes(c.get("numeroControlePNCP"))
            if not partes:
                continue
            cnpj, ano, seq = partes
            url = f"{PNCP}/orgaos/{cnpj}/contratos/{ano}/{seq}/termos"
            try:
                for t in cli.get_json(url) or []:
                    t["contrato_id"] = c["numeroControlePNCP"]
                    termos.append(t)
            except Exception:
                falhas += 1
        col.salvar("termos", termos, f"{PNCP}/orgaos/{{cnpj}}/contratos/{{ano}}/{{seq}}/termos")
        print(f"  pncp: {len(termos)} termos aditivos ({falhas} falhas)")
        col.concluir()
    finally:
        cli.fechar()
    return col
