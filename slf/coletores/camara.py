"""Câmara de Vereadores: proposições (pedidos de providência, indicações e o resto) pelo JSON público
que o próprio site da Câmara usa, sem login. São Leopoldo usa o sistema Legiflow; o endereço da API
fica em config/ente.yaml (seção camara). Para câmaras com SAPL ou outro sistema, ver docs/replicar.md.

Conferido ao vivo em 19/11/2026: /proposicoes aceita ano, id_bairro, limit e offset; limit acima de
100 faz a API voltar ao padrão de 10; não há filtro por espécie, então vem tudo e o core separa.
/parlamentares lista só quem está no mandato atual; com ?all (o que o próprio site da Câmara usa, fora
da documentação) vem o cadastro de todas as legislaturas, com cargo, partido e url_foto.
"""
from __future__ import annotations

from datetime import date
from pathlib import PurePosixPath
from urllib.parse import urlparse

from ..config import ente
from ..http import Cliente
from ..raw import Coleta

PAGINA = 100


def _todas(cli: Cliente, api: str, params: dict) -> list:
    linhas, offset = [], 0
    while True:
        pagina = cli.get_json(f"{api}/proposicoes", {**params, "limit": PAGINA, "offset": offset}) or []
        linhas.extend(pagina)
        if len(pagina) < PAGINA:
            return linhas
        offset += PAGINA


def _fotos(cli: Cliente, col: Coleta, parlamentares: list) -> int:
    """Baixa a foto de cada vereador como veio. Foto que falha não derruba a coleta: o vereador fica
    sem foto e o painel mostra as iniciais."""
    baixadas = 0
    for p in parlamentares:
        url = (p.get("url_foto") or "").strip()  # a API manda endereço com espaço no começo
        if not url or p.get("ID") is None:
            continue
        ext = PurePosixPath(urlparse(url).path).suffix.lower()
        ext = ext if ext in (".jpg", ".jpeg", ".png", ".webp") else ".jpg"
        try:
            col.salvar_arquivo(f"fotos/vereador-{p['ID']}{ext}", cli.get_bytes(url), url)
            baixadas += 1
        except Exception as erro:  # noqa: BLE001 (qualquer falha numa foto só tira aquela foto)
            print(f"  camara: sem foto de {p.get('nome')} ({type(erro).__name__})")
    return baixadas


def coletar() -> Coleta | None:
    cfg = ente()
    camara = cfg.get("camara") or {}
    if camara.get("sistema") != "legiflow" or not camara.get("api"):
        print("  camara: sem configuração de Câmara com Legiflow em config/ente.yaml, pulando")
        return None
    api = camara["api"].rstrip("/")
    col = Coleta("camara")
    cli = Cliente(pausa=0.3)
    try:
        proposicoes = []
        for ano in range(cfg["inicio"].year, date.today().year + 1):
            lote = _todas(cli, api, {"ano": ano})
            proposicoes += lote
            print(f"  camara: {ano}: {len(lote)} proposições")
        proposicoes = list({p["ID"]: p for p in proposicoes}.values())
        col.salvar("proposicoes", proposicoes, f"{api}/proposicoes")

        # cadastro dos vereadores de todas as legislaturas, com cargo, partido e foto
        parlamentares = cli.get_json(f"{api}/parlamentares", {"all": "true"}) or []
        col.salvar("parlamentares", parlamentares, f"{api}/parlamentares", {"all": "true"})
        fotos = _fotos(cli, col, parlamentares)

        # a API devolve os bairros como objeto {"1": {"ID": 1, "nome": ...}}
        bairros = cli.get_json(f"{api}/bairros") or {}
        bairros = list(bairros.values()) if isinstance(bairros, dict) else bairros
        col.salvar("bairros", bairros, f"{api}/bairros")

        # o bairro não vem na proposição: vem do filtro id_bairro, um bairro por vez
        vinculos = []
        for b in bairros:
            for p in _todas(cli, api, {"id_bairro": b["ID"]}):
                vinculos.append({"id_proposicao": p["ID"], "id_bairro": b["ID"]})
        col.salvar("proposicao_bairro", vinculos, f"{api}/proposicoes?id_bairro=")
        print(f"  camara: {len(proposicoes)} proposições, {len(bairros)} bairros, {len(vinculos)} vínculos com bairro, "
              f"{len(parlamentares)} vereadores no cadastro, {fotos} fotos")
        col.concluir()
    finally:
        cli.fechar()
    return col
