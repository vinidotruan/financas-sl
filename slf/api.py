"""API de leitura. Abre o banco só para leitura a cada pedido; a revisão (status e nota)
fica num arquivo JSON à parte, então a API nunca altera o banco."""
from __future__ import annotations

import json
import re
import threading
from datetime import datetime

import duckdb
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from .config import DB, MODO, REVISAO, WEB
from .sinais import ler_revisao

# 11 dígitos seguidos e isolados = CPF (CNPJ tem 14 e o código da emenda, 12). Aparece no campo
# do fornecedor PF e também no nome de MEI e empresário individual ("FULANO DE TAL 12345678901").
_CPF = re.compile(r"(?<!\d)(\d{3})(\d{3})(\d{3})(\d{2})(?!\d)")


def _sem_cpf(x):
    """CPF nunca aparece inteiro, em nenhum modo (LGPD). Percorre a resposta inteira."""
    if isinstance(x, str):
        return _CPF.sub(lambda m: f"***.{m[2]}.{m[3]}-**", x)
    if isinstance(x, dict):
        return {k: _sem_cpf(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_sem_cpf(v) for v in x]
    return x


class RespostaSemCpf(JSONResponse):
    def render(self, content) -> bytes:
        return super().render(_sem_cpf(content))


app = FastAPI(title="Finanças de São Leopoldo", version="0.1", default_response_class=RespostaSemCpf)
_trava = threading.Lock()

LINKS = {
    "transferegov": "https://api.transferegov.gestao.gov.br/transferenciasespeciais/",
    "siconfi": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
    "pncp": "https://pncp.gov.br/app/contratos",
}
SEVERIDADE = {"alto": 0, "atencao": 1, "baixo": 2}


def _q(sql: str, params: list | None = None) -> list[dict]:
    if not DB.exists():
        raise HTTPException(503, "Banco ainda não foi montado. Rode: slf diario")
    con = duckdb.connect(str(DB), read_only=True)
    try:
        cur = con.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, linha, strict=True)) for linha in cur.fetchall()]
    finally:
        con.close()


def _fontes(nomes) -> list[dict]:
    linhas = {f["fonte"]: f for f in _q("select * from core.fonte")}
    return [{"nome": n, "link": LINKS.get(n), "coletado_em": linhas.get(n, {}).get("coletado_em")}
            for n in nomes]


def _com_revisao(sinais: list[dict]) -> list[dict]:
    """A revisão feita na tela vale na hora, antes da próxima atualização do banco."""
    rev = ler_revisao()
    for s in sinais:
        if s["id"] in rev:
            s["status"], s["nota"] = rev[s["id"]]["status"], rev[s["id"]].get("nota")
    return sinais


def _mascara_cpf(sinal: dict) -> dict:
    """CPF nunca aparece inteiro, em nenhum modo. A resposta inteira também passa por _sem_cpf."""
    return _sem_cpf(sinal)


def _publico(sinal: dict) -> dict:
    """No modo público, pessoa física (inclui MEI e empresário individual) não aparece pelo nome."""
    ev = sinal.get("evidencia") or {}
    if isinstance(ev, str):
        ev = json.loads(ev)
    if ev.get("pessoa_fisica") or ev.get("tipo_pessoa") == "PF":
        ev["fornecedor"] = "pessoa física"
        sinal["titulo"] = "Pessoa física · " + sinal["titulo"].split(" · ", 1)[-1]
    sinal["evidencia"] = ev
    return sinal


@app.get("/api/sinais")
def listar_sinais(area: str | None = None, severidade: str | None = None, status: str | None = None,
                  ativos: bool = True):
    filtros, params = ["(o.ativo or not ?)"], [ativos]
    for campo, valor in (("r.area", area), ("r.severidade", severidade)):
        if valor:
            filtros.append(f"{campo} = ?")
            params.append(valor)
    linhas = _com_revisao(_q(f"""select o.id, o.regra_id, r.nome, r.area, r.severidade, o.titulo,
                    o.valor_observado, o.quando, o.primeira_vez, o.ultima_vez, o.ativo, o.status, o.nota, o.evidencia
                    from sinais.ocorrencia o join sinais.regra r on r.id = o.regra_id
                    where {' and '.join(filtros)}""", params))
    # status filtrado depois da revisão: um sinal revisado depois da última atualização já vale aqui
    if status:
        linhas = [s for s in linhas if s["status"] == status]
    if MODO == "publico":
        linhas = [s for s in linhas if s["status"] in ("confirmado", "encaminhado")]
    linhas.sort(key=lambda s: (SEVERIDADE.get(s["severidade"], 9), s["status"] != "novo",
                               -(s["primeira_vez"].toordinal() if s["primeira_vez"] else 0)))
    for s in linhas:
        s["evidencia"] = json.loads(s["evidencia"]) if isinstance(s["evidencia"], str) else s["evidencia"]
    linhas = [_mascara_cpf(s) for s in linhas]
    return [_publico(s) for s in linhas] if MODO == "publico" else linhas


@app.get("/api/sinais/{oid}")
def detalhe_sinal(oid: str):
    linhas = _q("""select o.*, r.nome, r.area, r.severidade, r.base_legal, r.limiar, r.pode_ser_normal_se,
                   r.como_verificar, r.fontes from sinais.ocorrencia o join sinais.regra r on r.id = o.regra_id
                   where o.id = ?""", [oid])
    if not linhas:
        raise HTTPException(404, "Sinal não encontrado")
    s = _com_revisao(linhas)[0]
    s["evidencia"] = json.loads(s["evidencia"]) if isinstance(s["evidencia"], str) else s["evidencia"]
    s["fontes"] = _fontes(s["fontes"] or [])
    s = _mascara_cpf(s)
    if MODO == "publico":
        if s["status"] not in ("confirmado", "encaminhado"):
            raise HTTPException(404, "Sinal não encontrado")
        s = _publico(s)
    return s


class Revisao(BaseModel):
    status: str
    nota: str | None = None


@app.patch("/api/sinais/{oid}")
def revisar_sinal(oid: str, rev: Revisao):
    if MODO != "privado":
        raise HTTPException(403, "Revisão só no modo privado")
    if rev.status not in ("novo", "em análise", "descartado", "confirmado", "encaminhado"):
        raise HTTPException(422, "Status inválido")
    atual = _q("select valor_observado from sinais.ocorrencia where id = ?", [oid])
    if not atual:
        raise HTTPException(404, "Sinal não encontrado")
    with _trava:
        dados = ler_revisao()
        dados[oid] = {"status": rev.status, "nota": rev.nota, "valor": atual[0]["valor_observado"],
                      "em": datetime.now().isoformat(timespec="seconds")}
        tmp = REVISAO.with_suffix(".tmp")
        tmp.write_text(json.dumps(dados, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(REVISAO)
    # vale na tela agora; no banco, na próxima atualização
    return {"ok": True, **dados[oid]}


@app.get("/api/emendas")
def listar_emendas():
    return _q("""select codigo_emenda, any_value(codigo_formatado) as codigo, any_value(parlamentar) as parlamentar,
                 min(ano) as ano, count(*) as planos, sum(valor_indicado) as indicado,
                 sum(transferido) as transferido, sum(coalesce(executado_relatorio, 0)) as executado_relatorio
                 from core.rastro_plano group by codigo_emenda order by ano desc, transferido desc""")


@app.get("/api/emendas/{codigo:path}/rastro")
def rastro(codigo: str):
    codigo = "".join(ch for ch in codigo if ch.isdigit())
    planos = _q("select * from core.rastro_plano where codigo_emenda = ? order by id_plano_acao", [codigo])
    if not planos:
        raise HTTPException(404, "Emenda não encontrada")
    ids = [p["id_plano_acao"] for p in planos]
    marcadores = ",".join("?" * len(ids))
    return {
        "codigo": codigo,
        "planos": planos,
        "transferencias": _q(f"select * from core.transferencia where id_plano_acao in ({marcadores}) "
                             "order by data_ob", ids),
        "metas": _q(f"select * from core.meta where id_plano_acao in ({marcadores})", ids),
        "fontes": _fontes(["transferegov"]),
    }


@app.get("/api/contratos")
def contratos(q: str | None = None, limite: int = 50):
    if q and MODO == "publico":
        # no modo público a busca é só pelo objeto: buscar pelo nome ou CPF confirmaria quem é a pessoa física
        linhas = _q("select * from core.contrato where objeto ilike ? order by valor_global desc limit ?",
                    [f"%{q}%", limite])
    elif q:
        linhas = _q("""select * from core.contrato where objeto ilike ? or fornecedor_nome ilike ? or fornecedor_ni = ?
                       order by valor_global desc limit ?""", [f"%{q}%", f"%{q}%", q, limite])
    else:
        linhas = _q("select * from core.contrato order by valor_global desc limit ?", [limite])
    if MODO == "publico":
        for c in linhas:
            if c["pessoa_fisica"]:
                c["fornecedor_nome"], c["fornecedor_ni"] = "pessoa física", None
    return linhas


@app.get("/api/fornecedores")
def fornecedores(limite: int = 30):
    linhas = _q("select * from core.fornecedor order by valor_total desc limit ?", [limite])
    for f in linhas:
        if f["pessoa_fisica"]:
            f["ni"] = None
            if MODO == "publico":
                f["nome"] = "pessoa física"
    return linhas


@app.get("/api/contas")
def contas():
    return {
        "limite_pessoal": _q("select * from core.limite_pessoal order by exercicio desc, periodo desc"),
        "pessoal": _q("""select exercicio, periodo, coluna, conta, valor from core.pessoal
                         where conta ilike '%DESPESA TOTAL COM PESSOAL%' or conta ilike '%RECEITA CORRENTE L_QUIDA%'
                         order by exercicio desc, periodo desc, conta, coluna"""),
        "fontes": _fontes(["siconfi"]),
    }


@app.get("/api/fontes")
def fontes():
    return {"modo": MODO, "fontes": _q("select * from core.fonte order by fonte"),
            "erros_de_regra": _q("select * from sinais.erro")}


@app.get("/")
def tela():
    return FileResponse(WEB / "index.html")
