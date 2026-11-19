"""Congresso Nacional: o cadastro de deputados federais (Câmara dos Deputados) e de senadores (Senado
Federal), pelas APIs de dados abertos de cada casa, sem chave. Serve para dar nome oficial e cargo ao
autor de cada emenda, que o Transferegov identifica só pelo nome e por um código próprio.

Conferido ao vivo em 19/11/2026:
- Câmara: /deputados aceita idLegislatura repetido, siglaSexo e até 1000 itens por página; devolve uma
  linha por deputado, legislatura e partido (quem trocou de partido aparece mais de uma vez).
- Senado: /senador/lista/legislatura/{inicio}/{fim}.json devolve cada senador uma vez, com os mandatos
  dentro; inclui o suplente que assumiu. A lista não traz a foto; a oficial fica em
  senadores/img/fotos-oficiais/senador{codigo}.jpg.

Fotos: só de deputados e senadores da UF da cidade (os autores de emenda daqui são quase todos de lá),
para não baixar as quase mil fotos da Câmara a cada coleta. Autor de outra UF aparece com as iniciais.
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


FOTO_SENADO = "https://www.senado.leg.br/senadores/img/fotos-oficiais/senador{codigo}.jpg"


def _lista(x) -> list:
    return x if isinstance(x, list) else [x] if x else []


def _ufs_senador(p: dict) -> set:
    ident = p.get("IdentificacaoParlamentar") or {}
    mandatos = _lista((p.get("Mandatos") or {}).get("Mandato"))
    return {ident.get("UfParlamentar")} | {m.get("UfParlamentar") for m in mandatos}


def _fotos(cli: Cliente, col: Coleta, deputados: list, senado: dict, uf: str) -> int:
    """Foto de cada deputado e senador da UF, como veio. Foto que falha não derruba a coleta."""
    alvos = {}
    for d in deputados:
        if d.get("siglaUf") == uf and d.get("id") is not None and (d.get("urlFoto") or "").strip():
            alvos[f"camara-{d['id']}"] = d["urlFoto"].strip()
    lista = ((senado.get("ListaParlamentarLegislatura") or {}).get("Parlamentares") or {}).get("Parlamentar")
    for p in _lista(lista):
        ident = p.get("IdentificacaoParlamentar") or {}
        codigo = ident.get("CodigoParlamentar")
        if codigo and uf in _ufs_senador(p):
            url = (ident.get("UrlFotoParlamentar") or "").strip()
            alvos[f"senado-{codigo}"] = url or FOTO_SENADO.format(codigo=codigo)
    baixadas = 0
    for chave, url in sorted(alvos.items()):
        try:
            col.salvar_arquivo(f"fotos/{chave}.jpg", cli.get_bytes(url), url)
            baixadas += 1
        except Exception as erro:  # noqa: BLE001 (qualquer falha numa foto só tira aquela foto)
            print(f"  congresso: sem foto {chave} ({type(erro).__name__})")
    return baixadas


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
        fotos = _fotos(cli, col, deputados, senado, cfg.get("uf"))
        print(f"  congresso: legislaturas {legislaturas[0]} a {legislaturas[-1]}: "
              f"{len({d['id'] for d in deputados})} deputados, {len({d['id'] for d in deputadas})} deputadas, "
              f"{fotos} fotos ({cfg.get('uf')})")
        col.concluir()
    finally:
        cli.fechar()
    return col
