"""Ambiente de teste: SLF_HOME numa pasta temporária e as APIs respondidas por fixtures.

As fixtures em tests/fixtures/{fonte}/ têm o formato das respostas reais (nomes de campo
conferidos ao vivo em 18/11/2026), com valores inventados. Nenhum teste usa a rede.
"""
from __future__ import annotations

import collections
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

# Precisa vir antes de qualquer import de slf: config.py lê SLF_HOME ao ser importado.
HOME = Path(tempfile.mkdtemp(prefix="slf-teste-"))
os.environ["SLF_HOME"] = str(HOME)
os.environ["SLF_MODO"] = "privado"
(HOME / "config").mkdir()
(HOME / "config" / "ente.yaml").write_text(
    'nome: São Leopoldo\nuf: RS\nibge: 4318705\ncnpj_municipio: "89814693000160"\ninicio: 2024-01-01\n'
    'camara:\n  sistema: legiflow\n  api: https://api.camara.exemplo\n  site: https://www.camara.exemplo\n'
    'orgaos_pncp:\n  - cnpj: "89814693000160"\n    nome: Prefeitura Municipal de São Leopoldo\n'
    'tce_rs:\n  orgaos:\n    - codigo: 58700\n      nome: Prefeitura\n    - codigo: 58701\n      nome: Câmara\n'
    '    - codigo: 58702\n      nome: SEMAE\n',
    encoding="utf-8",
)

import httpx  # noqa: E402
import pytest  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures"


def _fixture(fonte: str, nome: str):
    return json.loads((FIXTURES / fonte / f"{nome}.json").read_text(encoding="utf-8"))


def _postgrest(tabela: str, params: dict) -> httpx.Response:
    """Imita o PostgREST do Transferegov: filtros eq./in.(), limit e offset (máximo de 1000 linhas)."""
    linhas = _fixture("transferegov", tabela)
    for coluna, valor in params.items():
        if coluna in ("limit", "offset"):
            continue
        if valor.startswith("eq."):
            linhas = [x for x in linhas if str(x.get(coluna)) == valor[3:]]
        elif valor.startswith("in.("):
            ids = set(valor[4:-1].split(","))
            linhas = [x for x in linhas if str(x.get(coluna)) in ids]
    inicio = int(params.get("offset", 0))
    limite = min(int(params.get("limit", 1000)), 1000)
    return httpx.Response(200, json=linhas[inicio:inicio + limite])


def _siconfi(relatorio: str, params: dict) -> httpx.Response:
    linhas = [x for x in _fixture("siconfi", relatorio)
              if str(x["exercicio"]) == params["an_exercicio"] and str(x["periodo"]) == params["nr_periodo"]]
    if "no_anexo" in params:
        linhas = [x for x in linhas if x["anexo"] == params["no_anexo"]]
    return httpx.Response(200, json={"items": linhas, "hasMore": False, "count": len(linhas)})


def _pncp_contratos(params: dict) -> httpx.Response:
    if int(params["tamanhoPagina"]) > 500:
        return httpx.Response(400, json={"message": "Tamanho de página inválido"})
    ini, fim = params["dataInicial"], params["dataFinal"]
    linhas = [c for c in _fixture("pncp", "contratos")
              if ini <= c["dataPublicacaoPncp"][:10].replace("-", "") <= fim]
    if not linhas:
        return httpx.Response(204)  # a API real responde 204 quando o período não tem contrato
    return httpx.Response(200, json={"data": linhas, "totalRegistros": len(linhas), "totalPaginas": 1,
                                     "numeroPagina": 1, "paginasRestantes": 0, "empty": False})


# Último passo de tramitação de cada pedido, como /proposicao/{id} devolve. 9005 não tem detalhe (404).
TRAMITACAO = {
    9001: ("Encaminhado para o Executivo", "2025-03-01"),
    9002: ("Arquivado", "2025-12-20"),
    9003: ("Encaminhado à Comissão", "2025-04-01"),
    9004: ("Encaminhado para o Executivo", "2026-02-01"),
    9006: ("Aprovado", "2026-03-01"),
    9007: ("Encaminha para Pauta da Sessão - Para Leitura", "2026-11-18"),
}


def _camara(caminho: str, params: dict) -> httpx.Response:
    """Imita a API do Legiflow: filtros ano e id_bairro; limit acima de 100 volta ao padrão de 10."""
    m = re.fullmatch(r"/proposicao/(\d+)", caminho)
    if m:
        if int(m[1]) not in TRAMITACAO:
            return httpx.Response(404)
        nome, data = TRAMITACAO[int(m[1])]
        proposicao = next(p for p in _fixture("camara", "proposicoes") if p["ID"] == int(m[1]))
        return httpx.Response(200, json={**{k: v for k, v in proposicao.items() if k != "_bairros"},
                                         "ultima_tramitacao": {"nome_tramitacao": nome, "data_tramitacao": data}})
    if caminho == "/bairros":
        return httpx.Response(200, json=_fixture("camara", "bairros"))
    if caminho == "/parlamentares":
        # sem ?all a API real só devolve quem está no mandato atual
        linhas = _fixture("camara", "parlamentares")
        return httpx.Response(200, json=linhas if "all" in params else
                              [x for x in linhas if x["situacao"] == "Em Atividade"])
    linhas = _fixture("camara", "proposicoes")
    if "ano" in params:
        linhas = [p for p in linhas if str(p["ano"]) == params["ano"]]
    if "id_bairro" in params:
        linhas = [p for p in linhas if int(params["id_bairro"]) in p["_bairros"]]
    limite = int(params.get("limit", 10))
    limite = limite if limite <= 100 else 10
    inicio = int(params.get("offset", 0))
    return httpx.Response(200, json=[{k: v for k, v in p.items() if k != "_bairros"}
                                     for p in linhas[inicio:inicio + limite]])


def _congresso(host: str, caminho: str, params: dict) -> httpx.Response:
    """Câmara dos Deputados (filtro siglaSexo, páginas de até 1000) e lista de senadores do Senado."""
    if host == "dadosabertos.camara.leg.br" and caminho == "/api/v2/deputados":
        linhas = [d for d in _fixture("congresso", "deputados")
                  if params.get("siglaSexo") in (None, d["_sexo"])]
        itens, pagina = int(params.get("itens", 15)), int(params.get("pagina", 1))
        pedaco = linhas[(pagina - 1) * itens:pagina * itens]
        return httpx.Response(200, json={"dados": [{k: v for k, v in d.items() if k != "_sexo"} for d in pedaco],
                                         "links": []})
    if host == "legis.senado.leg.br" and re.fullmatch(r"/dadosabertos/senador/lista/legislatura/\d+/\d+\.json",
                                                      caminho):
        return httpx.Response(200, json=_fixture("congresso", "senadores"))
    return httpx.Response(404)


def _jpeg(largura: int, altura: int) -> bytes:
    from io import BytesIO

    from PIL import Image

    saida = BytesIO()
    Image.new("RGB", (largura, altura), (40, 110, 90)).save(saida, "JPEG")
    return saida.getvalue()


# TCE-RS: um zip por órgão e ano, com o CSV da fixture dentro; o que não tem fixture dá 404.
# PEDIDOS_TCE conta os pedidos por caminho (o teste de reaproveitar ano fechado olha isso).
PEDIDOS_TCE: collections.Counter = collections.Counter()


def _tce(caminho: str) -> httpx.Response:
    PEDIDOS_TCE[caminho] += 1
    m = re.fullmatch(r"/dados/municipal/empenhos/(\d{4})/(\d+)\.csv\.zip", caminho)
    arq = FIXTURES / "tce" / f"{m[2]}-{m[1]}.csv" if m else None
    if not arq or not arq.exists():
        return httpx.Response(404)
    saida = io.BytesIO()
    with zipfile.ZipFile(saida, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo(f"{m[2]}.csv", date_time=(2026, 1, 1, 0, 0, 0)), arq.read_bytes())
    return httpx.Response(200, content=saida.getvalue(), headers={"Content-Type": "application/zip"})


def responder(request: httpx.Request) -> httpx.Response:
    caminho, params = request.url.path, dict(request.url.params)
    if request.url.host == "dados.tce.rs.gov.br":
        return _tce(caminho)
    if request.url.host == "cdn.exemplo":  # fotos da Câmara: só a do Beto existe
        if caminho == "/2.jpg":
            return httpx.Response(200, content=_jpeg(300, 400), headers={"Content-Type": "image/jpeg"})
        return httpx.Response(404)
    # fotos do Congresso: só a da deputada 1002 e a da senadora 9001 existem (a do Senado vem grande)
    if request.url.host == "www.camara.leg.br":
        if caminho == "/internet/deputado/bandep/1002.jpg":
            return httpx.Response(200, content=_jpeg(200, 250), headers={"Content-Type": "image/jpeg"})
        return httpx.Response(404)
    if request.url.host == "www.senado.leg.br":
        if caminho == "/senadores/img/fotos-oficiais/senador9001.jpg":
            return httpx.Response(200, content=_jpeg(900, 1200), headers={"Content-Type": "image/jpeg"})
        return httpx.Response(404)
    if request.url.host == "api.camara.exemplo":
        return _camara(caminho, params)
    if request.url.host in ("dadosabertos.camara.leg.br", "legis.senado.leg.br"):
        return _congresso(request.url.host, caminho, params)
    if caminho.startswith("/transferenciasespeciais/"):
        return _postgrest(caminho.rsplit("/", 1)[1], params)
    if caminho.startswith("/ords/siconfi/tt/"):
        return _siconfi(caminho.rsplit("/", 1)[1], params)
    if caminho == "/api/consulta/v1/contratos":
        return _pncp_contratos(params)
    m = re.fullmatch(r"/api/consulta/v1/orgaos/(\d+)/compras/(\d+)/(\d+)", caminho)
    if m:
        chave = f"{m[1]}-1-{int(m[3]):06d}/{m[2]}"
        achada = [c for c in _fixture("pncp", "compras") if c["numeroControlePNCP"] == chave]
        return httpx.Response(200, json=achada[0]) if achada else httpx.Response(404)
    m = re.fullmatch(r"/api/pncp/v1/orgaos/(\d+)/contratos/(\d+)/(\d+)/termos", caminho)
    if m:
        termos = _fixture("pncp", "termos").get(f"{m[1]}-2-{int(m[3]):06d}/{m[2]}")
        return httpx.Response(200, json=termos) if termos else httpx.Response(204)
    return httpx.Response(404)


@pytest.fixture(autouse=True)
def pasta_limpa():
    """Cada teste começa sem data/ (raw, banco e revisão)."""
    shutil.rmtree(HOME / "data", ignore_errors=True)
    PEDIDOS_TCE.clear()
    yield


@pytest.fixture
def api_falsa(monkeypatch):
    """Troca a rede pelas fixtures e tira a pausa entre chamadas."""
    import slf.http

    cliente_real = httpx.Client
    monkeypatch.setattr(slf.http.httpx, "Client",
                        lambda **kw: cliente_real(transport=httpx.MockTransport(responder), **kw))
    monkeypatch.setattr(slf.http.time, "sleep", lambda s: None)


@pytest.fixture
def banco(api_falsa):
    """Coleta todas as fontes nas fixtures e monta o banco."""
    from slf import cli, processar
    from slf.config import DB

    assert cli.coletar(cli.COLETORES) == []
    processar.atualizar()
    return DB


@pytest.fixture
def pedidos_tce():
    """Quantas vezes cada arquivo do TCE-RS foi pedido no teste."""
    return PEDIDOS_TCE
