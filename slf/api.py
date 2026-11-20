"""API de leitura. Abre o banco só para leitura a cada pedido; a revisão (status e nota) fica num
arquivo JSON à parte, então a API nunca altera o banco. O conteúdo vem de consultas.py, o mesmo
módulo que a exportação estática usa. Em "/" serve o front já buildado em site/."""
from __future__ import annotations

import json
import threading
from contextlib import contextmanager

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import DB, FOTOS, MODO, REVISAO, SITE, WEB, agora
from .consultas import STATUS, Consulta, sem_cpf
from .sinais import ler_revisao


class RespostaSemCpf(JSONResponse):
    """Segunda barreira: mesmo o que não passou por consultas.py sai sem CPF inteiro."""

    def render(self, content) -> bytes:
        return super().render(sem_cpf(content))


app = FastAPI(title="Finanças municipais", version="0.2", default_response_class=RespostaSemCpf)
_trava = threading.Lock()


def _mascara_cpf(x):
    return sem_cpf(x)


@contextmanager
def _consulta():
    if not DB.exists():
        raise HTTPException(503, "Banco ainda não foi montado. Rode: slf diario")
    con = duckdb.connect(str(DB), read_only=True)
    try:
        yield Consulta(con, MODO, ler_revisao())
    finally:
        con.close()


def _ou_404(valor, mensagem: str):
    if valor is None:
        raise HTTPException(404, mensagem)
    return valor


@app.get("/api/fontes")
def fontes():
    with _consulta() as c:
        return c.fontes()


@app.get("/api/inicio")
def inicio():
    with _consulta() as c:
        return c.inicio()


@app.get("/api/proveniencia")
def proveniencia():
    with _consulta() as c:
        return c.proveniencia()


@app.get("/api/regras")
def regras():
    with _consulta() as c:
        return c.regras()


@app.get("/api/sinais")
def listar_sinais(area: str | None = None, severidade: str | None = None, status: str | None = None,
                  ativos: bool = True):
    with _consulta() as c:
        return c.sinais(area, severidade, status, ativos)


@app.get("/api/sinais/{oid}")
def detalhe_sinal(oid: str):
    with _consulta() as c:
        return _ou_404(c.sinal(oid), "Sinal não encontrado")


class Revisao(BaseModel):
    status: str
    nota: str | None = None


@app.patch("/api/sinais/{oid}")
def revisar_sinal(oid: str, rev: Revisao):
    if MODO != "privado":
        raise HTTPException(403, "Revisão só no modo privado")
    if rev.status not in STATUS:
        raise HTTPException(422, "Status inválido")
    with _consulta() as c:
        atual = c._q("select valor_observado from sinais.ocorrencia where id = ?", [oid])
    if not atual:
        raise HTTPException(404, "Sinal não encontrado")
    with _trava:
        dados = ler_revisao()
        dados[oid] = {"status": rev.status, "nota": rev.nota, "valor": atual[0]["valor_observado"],
                      "em": agora().isoformat(timespec="seconds")}
        tmp = REVISAO.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(REVISAO)
    # vale na tela agora; no banco, na próxima atualização
    return {"ok": True, **dados[oid]}


@app.get("/api/emendas")
def listar_emendas():
    with _consulta() as c:
        return c.emendas()


@app.get("/api/emendas/{codigo:path}/rastro")
def rastro(codigo: str):
    with _consulta() as c:
        return _ou_404(c.rastro(codigo), "Emenda não encontrada")


@app.get("/api/parlamentares")
def parlamentares():
    with _consulta() as c:
        return c.parlamentares()


@app.get("/api/parlamentares/{codigo}")
def parlamentar(codigo: str):
    with _consulta() as c:
        return _ou_404(c.parlamentar(codigo), "Parlamentar não encontrado")


@app.get("/api/fornecedores")
def fornecedores(limite: int | None = None):
    with _consulta() as c:
        return c.fornecedores(limite)


@app.get("/api/fornecedores/{fid}")
def fornecedor(fid: str):
    with _consulta() as c:
        return _ou_404(c.fornecedor(fid), "Fornecedor não encontrado")


@app.get("/api/contratos")
def contratos(q: str | None = None, limite: int = 50):
    with _consulta() as c:
        return c.contratos(q, limite)


@app.get("/api/pedidos")
def pedidos():
    with _consulta() as c:
        return c.pedidos()


@app.get("/api/vereadores/{vid}")
def vereador(vid: str):
    with _consulta() as c:
        return _ou_404(c.vereador(vid), "Vereador não encontrado")


@app.get("/api/fotos/{arquivo}")
def foto(arquivo: str):
    """Só serve foto que alguma tela usa; o nome vem da lista, nunca vira caminho por conta própria."""
    with _consulta() as c:
        if arquivo not in c.fotos() or not (FOTOS / arquivo).is_file():
            raise HTTPException(404, "Foto não encontrada")
    return FileResponse(FOTOS / arquivo, media_type="image/jpeg")


@app.get("/api/contas")
def contas():
    with _consulta() as c:
        return c.contas()


# O front buildado (front/ -> site/). Sem build, cai na tela provisória antiga.
if (SITE / "index.html").exists():
    app.mount("/", StaticFiles(directory=SITE, html=True), name="site")
else:
    @app.get("/")
    def tela():
        return FileResponse(WEB / "index.html")
