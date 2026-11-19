"""Congresso Nacional: o cadastro de deputados federais (Câmara dos Deputados) e de senadores (Senado
Federal), pelas APIs de dados abertos de cada casa, sem chave. Serve para dar nome oficial e cargo ao
autor de cada emenda, que o Transferegov identifica só pelo nome e por um código próprio.

Conferido ao vivo em 19/11/2026:
- Câmara: /deputados aceita idLegislatura repetido, siglaSexo e até 1000 itens por página; devolve uma
  linha por deputado, legislatura e partido (quem trocou de partido aparece mais de uma vez).
- Senado: /senador/lista/legislatura/{inicio}/{fim}.json devolve cada senador uma vez, com os mandatos
  dentro; inclui o suplente que assumiu.
"""
from __future__ import annotations

from datetime import date

from ..config import ente
from ..http import Cliente
from ..raw import Coleta

CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
SENADO = "https://legis.senado.leg.br/dadosabertos"
ITENS = 1000


def legislatura(ano: int) -> int:
    """Número da legislatura em curso no ano (a 57ª vai de fevereiro de 2023 a janeiro de 2027)."""
    return 57 + (ano - 2023) // 4


def _deputados(cli: Cliente, legislaturas: range, filtro: dict) -> list:
    linhas, pagina = [], 1
    while True:
        resp = cli.get_json(f"{CAMARA}/deputados", {
            "idLegislatura": list(legislaturas), **filtro, "itens": ITENS, "pagina": pagina,
            "ordem": "ASC", "ordenarPor": "nome"}) or {}
        dados = resp.get("dados") or []
        linhas.extend(dados)
        if len(dados) < ITENS:
            return linhas
        pagina += 1


def coletar() -> Coleta:
    cfg = ente()
    # a emenda de um ano é apresentada no ano anterior, então a primeira legislatura é a de antes do início
    legislaturas = range(legislatura(cfg["inicio"].year - 1), legislatura(date.today().year) + 1)
    col = Coleta("congresso")
    cli = Cliente(pausa=0.3)
    try:
        deputados = _deputados(cli, legislaturas, {})
        col.salvar("deputados", deputados, f"{CAMARA}/deputados", {"idLegislatura": list(legislaturas)})
        # a lista não traz o sexo; a mesma consulta filtrada por siglaSexo=F diz quem é deputada
        deputadas = _deputados(cli, legislaturas, {"siglaSexo": "F"})
        col.salvar("deputadas", deputadas, f"{CAMARA}/deputados", {"siglaSexo": "F"})
        url = f"{SENADO}/senador/lista/legislatura/{legislaturas[0]}/{legislaturas[-1]}.json"
        senado = cli.get_json(url) or {}
        col.salvar("senadores", senado, url)
        # cadastro vazio não é "ninguém no Congresso": a coleta fica sem _OK e vale a anterior
        if not deputados or not senado.get("ListaParlamentarLegislatura"):
            raise RuntimeError("cadastro de deputados ou de senadores veio vazio")
        print(f"  congresso: legislaturas {legislaturas[0]} a {legislaturas[-1]}: "
              f"{len({d['id'] for d in deputados})} deputados, {len({d['id'] for d in deputadas})} deputadas")
        col.concluir()
    finally:
        cli.fechar()
    return col
