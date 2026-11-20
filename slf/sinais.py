"""Motor de sinais: cada regra é um YAML com SQL e com o texto que a tela mostra."""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import yaml

from .config import REGRAS, REVISAO, agora

CAMPOS_REGRA = ["id", "nome", "versao", "area", "severidade", "base_legal", "limiar",
                "pode_ser_normal_se", "como_verificar", "fontes", "sql"]
# Opcionais, só para a tela: "observado" diz o que é o valor observado ({rotulo, formato}) e
# "resumo" é a frase do que foi visto, com campos da evidência: "{transferido|brl} em {prazo|data}".
# Formatos: brl, pct (fração vira %), dias, data, int, texto.
CAMPOS_TELA = ["observado", "resumo"]


def carregar_regras() -> list[dict]:
    regras = []
    for arq in sorted(REGRAS.glob("*.yaml")):
        r = yaml.safe_load(arq.read_text(encoding="utf-8"))
        faltando = [c for c in CAMPOS_REGRA if c not in r]
        if faltando:
            raise ValueError(f"{arq.name}: faltam os campos {faltando}")
        regras.append(r)
    return regras


def ler_revisao() -> dict:
    try:
        return json.loads(REVISAO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def status_revisado(rev: dict, valor_agora) -> str:
    """O status que a revisão dá a um sinal: o que a pessoa marcou, menos o descartado cujo valor
    observado mudou desde o descarte, que volta a "novo" (D17). Vale no banco e na API (que aplica a
    revisão na hora, sem esperar o atualizar)."""
    status = rev.get("status", "novo")
    valor_rev = rev.get("valor")
    if status == "descartado" and valor_rev is not None and valor_agora is not None \
            and abs(valor_agora - valor_rev) > max(0.01, abs(valor_rev) * 0.001):
        return "novo"
    return status


def rodar(con, banco_anterior: Path) -> int:
    # a data de referência das coletas (D43); sem ela (banco montado à mão), a de hoje
    try:
        hoje = con.execute("select data from core.referencia").fetchone()[0]
    except duckdb.CatalogException:
        hoje = agora().date()
    con.execute("create schema if not exists sinais")
    con.execute("""create or replace table sinais.regra (id varchar primary key, nome varchar, versao integer,
        area varchar, severidade varchar, base_legal varchar, limiar varchar, pode_ser_normal_se varchar,
        como_verificar varchar, fontes varchar[], sql varchar, observado json, resumo varchar)""")
    con.execute("""create or replace table sinais.ocorrencia (id varchar primary key, regra_id varchar,
        regra_versao integer, chave varchar, titulo varchar, valor_observado double, evidencia json,
        quando date, primeira_vez date, ultima_vez date, ativo boolean, status varchar, nota varchar)""")
    con.execute("create or replace table sinais.erro (regra_id varchar, mensagem varchar)")

    for r in carregar_regras():
        con.execute("insert into sinais.regra values (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [r[c] for c in CAMPOS_REGRA]
                    + [json.dumps(r["observado"], ensure_ascii=False) if r.get("observado") else None,
                       r.get("resumo")])
        try:
            con.execute(f"create or replace temp table _r as {r['sql']}")
            con.execute("""insert into sinais.ocorrencia
                select md5(? || '|' || cast(chave as varchar)), ?, ?, cast(chave as varchar), titulo,
                       try_cast(valor_observado as double), to_json(evidencia), try_cast(quando as date),
                       ?, ?, true, 'novo', null
                from _r""", [r["id"], r["id"], r["versao"], hoje, hoje])
        except duckdb.Error as e:
            con.execute("insert into sinais.erro values (?, ?)", [r["id"], str(e)])
            print(f"  regra {r['id']} falhou: {e}")

    # histórico: mantém a data da primeira vez e guarda as que sumiram como inativas
    if banco_anterior.exists():
        con.execute(f"attach '{banco_anterior}' as anterior (read_only)")
        try:
            con.execute("""update sinais.ocorrencia o set primeira_vez = a.primeira_vez
                           from anterior.sinais.ocorrencia a where a.id = o.id""")
            con.execute("""insert into sinais.ocorrencia
                           select a.* replace (false as ativo)
                           from anterior.sinais.ocorrencia a
                           where a.id not in (select id from sinais.ocorrencia)
                             and a.regra_id in (select id from sinais.regra)""")
        except duckdb.Error:
            pass  # banco anterior sem sinais
        con.execute("detach anterior")

    # revisão feita na tela: status e nota. Descartado volta a "novo" se o valor mudar.
    for oid, rev in ler_revisao().items():
        atual = con.execute("select valor_observado from sinais.ocorrencia where id = ?", [oid]).fetchone()
        if not atual:
            continue
        status = status_revisado(rev, atual[0])
        con.execute("update sinais.ocorrencia set status = ?, nota = ? where id = ?",
                    [status, rev.get("nota"), oid])

    return con.execute("select count(*) from sinais.ocorrencia where ativo").fetchone()[0]
