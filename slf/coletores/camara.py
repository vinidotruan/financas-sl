"""Câmara de Vereadores: proposições (pedidos de providência, indicações e o resto) pelo JSON público
que o próprio site da Câmara usa, sem login. São Leopoldo usa o sistema Legiflow; o endereço da API
fica em config/ente.yaml (seção camara). Para câmaras com SAPL ou outro sistema, ver docs/replicar.md.

Conferido ao vivo em 19/11/2026: /proposicoes aceita ano, id_bairro, limit e offset; limit acima de
100 faz a API voltar ao padrão de 10; não há filtro por espécie, então vem tudo e o core separa.
/parlamentares lista só quem está no mandato atual; com ?all (o que o próprio site da Câmara usa, fora
da documentação) vem o cadastro de todas as legislaturas, com cargo, partido e url_foto.
/proposicao/{id} traz o último passo de tramitação na Câmara ("Encaminhado para o Executivo",
"Arquivado", "Encaminhado à Comissão"...). Não diz se a prefeitura atendeu. A lista não traz esse passo
e o updated_at da proposição não muda quando entra tramitação nova, então é uma consulta por pedido.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import PurePosixPath
from urllib.parse import urlparse

from ..config import ente
from ..http import Cliente
from ..raw import Coleta, ultima_coleta_boa

PAGINA = 100
PEDIDOS = ("Pedido de Providência", "Indicação")  # as espécies que o painel mostra (core.pedido)
# passos depois dos quais o pedido quase nunca muda: revistos uma vez por mês, não a cada coleta
PARADOS = ("Encaminhado para o Executivo", "Arquivado")
REVER_DIAS = 30
LIMITE_PADRAO = 2000  # consultas por coleta (meio segundo cada); SLF_CAMARA_TRAMITACOES muda


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


def _anteriores() -> dict:
    """Tramitações da última coleta boa, por id do pedido."""
    pasta = ultima_coleta_boa("camara")
    arq = pasta / "tramitacoes.json" if pasta else None
    if not arq or not arq.exists():
        return {}
    return {t["id"]: t for t in json.loads(arq.read_text(encoding="utf-8"))}


def _tramitacoes(cli: Cliente, api: str, proposicoes: list, anteriores: dict, limite: int) -> tuple[list, int]:
    """Último passo de tramitação de cada pedido, aos poucos: até `limite` consultas por coleta. Primeiro os
    pedidos sem situação, do mais novo ao mais antigo; depois os que ainda andam na Câmara; por último os
    parados (no Executivo ou arquivados) vistos há mais de um mês. O resto vem da coleta anterior."""
    hoje = date.today()
    pedidos = [p for p in proposicoes if p.get("especie") in PEDIDOS and p.get("ID") is not None]

    def fila(p):
        t = anteriores.get(p["ID"])
        if t is None:
            return (0, -(p.get("ano") or 0), -(p.get("numero") or 0))
        return (1 if t.get("nome") not in PARADOS else 2, t.get("verificado_em") or "")

    def precisa(p):
        t = anteriores.get(p["ID"])
        if t is None or t.get("nome") not in PARADOS:
            return True
        return (hoje - date.fromisoformat(t["verificado_em"])).days >= REVER_DIAS

    novos, falhas_seguidas = {}, 0
    for p in sorted(filter(precisa, pedidos), key=fila)[:limite]:
        try:
            det = cli.get_json(f"{api}/proposicao/{p['ID']}")
            falhas_seguidas = 0
        except Exception:  # noqa: BLE001 (sem detalhe, o pedido fica sem situação nesta coleta)
            falhas_seguidas += 1
            if falhas_seguidas >= 5:
                print("  camara: 5 falhas seguidas no detalhe dos pedidos, parando as consultas desta coleta")
                break
            continue
        det = det[0] if isinstance(det, list) and det else det if isinstance(det, dict) else {}
        u = det.get("ultima_tramitacao") or {}
        novos[p["ID"]] = {"id": p["ID"], "nome": u.get("nome_tramitacao"), "data": u.get("data_tramitacao"),
                          "verificado_em": hoje.isoformat()}
    ids = sorted({p["ID"] for p in pedidos})
    return [novos.get(i) or anteriores[i] for i in ids if i in novos or i in anteriores], len(novos)


def _conferir_volume(proposicoes: list) -> None:
    """Resposta vazia não é "a Câmara apagou os pedidos": se um ano que tinha proposições na coleta boa
    anterior veio vazio, ou o total caiu à metade, a coleta falha e vale a anterior (com o cache de
    situação dos pedidos, que levaria dias para refazer). O mesmo cuidado do coletor do Congresso."""
    pasta = ultima_coleta_boa("camara")
    arq = pasta / "proposicoes.json" if pasta else None
    if not arq or not arq.exists():
        return
    antes = json.loads(arq.read_text(encoding="utf-8"))
    por_ano = lambda lista: {p.get("ano") for p in lista}  # noqa: E731
    sumiram = sorted(a for a in por_ano(antes) - por_ano(proposicoes) if a is not None)
    if sumiram or len(proposicoes) < len(antes) / 2:
        raise RuntimeError(f"a Câmara devolveu {len(proposicoes)} proposições (eram {len(antes)}); "
                           f"anos sem nenhuma: {sumiram or 'nenhum'}. Fica a coleta anterior.")


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
        _conferir_volume(proposicoes)
        col.salvar("proposicoes", proposicoes, f"{api}/proposicoes")

        # situação de cada pedido na Câmara, aos poucos (o que já se sabe vem da coleta anterior)
        limite = int(os.environ.get("SLF_CAMARA_TRAMITACOES", LIMITE_PADRAO))
        tramitacoes, consultadas = _tramitacoes(cli, api, proposicoes, _anteriores(), limite)
        col.salvar("tramitacoes", tramitacoes, f"{api}/proposicao/{{id}}",
                   {"consultadas_nesta_coleta": consultadas, "limite": limite})
        print(f"  camara: situação de {len(tramitacoes)} pedidos ({consultadas} consultados agora)")

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
