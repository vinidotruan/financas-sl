"""Ambiente de teste: SLF_HOME numa pasta temporária e as três APIs respondidas por fixtures.

As fixtures em tests/fixtures/{fonte}/ têm o formato das respostas reais (nomes de campo
conferidos ao vivo em 18/11/2026), com valores inventados. Nenhum teste usa a rede.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

# Precisa vir antes de qualquer import de slf: config.py lê SLF_HOME ao ser importado.
HOME = Path(tempfile.mkdtemp(prefix="slf-teste-"))
os.environ["SLF_HOME"] = str(HOME)
os.environ["SLF_MODO"] = "privado"
(HOME / "config").mkdir()
(HOME / "config" / "ente.yaml").write_text(
    'nome: São Leopoldo\nuf: RS\nibge: 4318705\ncnpj_municipio: "89814693000160"\ninicio: 2024-01-01\n'
    'camara:\n  sistema: legiflow\n  api: https://api.camara.exemplo\n  site: https://www.camara.exemplo\n'
    'orgaos_pncp:\n  - cnpj: "89814693000160"\n    nome: Prefeitura Municipal de São Leopoldo\n',
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


def _camara(caminho: str, params: dict) -> httpx.Response:
    """Imita a API do Legiflow: filtros ano e id_bairro; limit acima de 100 volta ao padrão de 10."""
    if caminho == "/bairros":
        return httpx.Response(200, json=_fixture("camara", "bairros"))
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


def responder(request: httpx.Request) -> httpx.Response:
    caminho, params = request.url.path, dict(request.url.params)
    if request.url.host == "api.camara.exemplo":
        return _camara(caminho, params)
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
    """Coleta as três fontes nas fixtures e monta o banco."""
    from slf import cli, processar
    from slf.config import DB

    assert cli.coletar(cli.COLETORES) == []
    processar.atualizar()
    return DB
