"""Pacote de dados abertos (D43): as tabelas tratadas em Parquet, em modo público, para refazer as contas."""
from __future__ import annotations

import json

import duckdb
import pytest

from slf.pacote import montar_pacote
from slf.sensivel import conferir

DONOS = ("FULANO", "MARIA EXEMPLO", "JOANA EXEMPLO", "PEDRO EXEMPLO", "Fulana Exemplo")
CPFS = ("12345678901", "98765432100", "22233344455")


def _tabela(pasta, nome):
    con = duckdb.connect()
    try:
        cur = con.execute(f"select * from read_parquet('{pasta / 'tabelas' / (nome + '.parquet')}')")
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, linha, strict=True)) for linha in cur.fetchall()]
    finally:
        con.close()


@pytest.fixture
def pacote(banco, tmp_path):
    montar_pacote(tmp_path / "pacote")
    return tmp_path / "pacote"


def test_pacote_traz_as_tabelas_e_a_proveniencia(pacote):
    nomes = {p.stem for p in (pacote / "tabelas").glob("*.parquet")}
    assert {"core.contrato", "core.fornecedor", "core.emenda", "core.pedido", "sinais.regra"} <= nomes
    assert "core.proposicao" not in nomes  # outras proposições da Câmara não passaram pelo D40
    assert json.loads((pacote / "proveniencia.json").read_text(encoding="utf-8"))["modo"] == "publico"
    assert (pacote / "LEIAME.md").exists()


def test_pacote_esconde_pessoa_fisica(pacote):
    contratos = {c["sequencial"]: c for c in _tabela(pacote, "core.contrato")}
    for seq in (2, 4, 5, 6, 7):
        assert contratos[seq]["fornecedor_nome"] == "pessoa física"
        assert contratos[seq]["fornecedor_ni"] is None
        assert contratos[seq]["objeto"] == "objeto omitido (pessoa física)"
    assert contratos[3]["fornecedor_nome"] == "CONSTRUTORA EXEMPLO SA"
    pf = [f for f in _tabela(pacote, "core.fornecedor") if f["pessoa_fisica"]]
    assert pf and all(f["nome"] == "pessoa física" and f["ni"] is None and f["id"] is None for f in pf)


def test_pacote_limpa_o_texto_dos_pedidos(pacote):
    pedidos = {p["id"]: p["ementa"] for p in _tabela(pacote, "core.pedido")}
    assert pedidos[9007].endswith("Solicitante: [nome omitido]. Contato: [contato omitido].")


def test_pacote_so_traz_sinal_revisado(pacote):
    assert _tabela(pacote, "sinais.ocorrencia") == []  # nas fixtures, nenhum sinal foi revisado


def test_pacote_passa_na_conferencia_e_nao_tem_nome_nem_cpf(pacote):
    assert conferir(pacote) == []
    corpo = b"".join(p.read_bytes() for p in pacote.rglob("*") if p.is_file())
    for dado in DONOS + CPFS:
        assert dado.encode() not in corpo, dado


def test_conferencia_le_parquet(tmp_path):
    (tmp_path / "tabelas").mkdir()
    con = duckdb.connect()
    con.execute(f"copy (select 'Contato: (51) 99999-1234.' as ementa) to '{tmp_path / 'tabelas' / 'x.parquet'}'")
    con.close()
    assert {a.regra for a in conferir(tmp_path)} == {"contato de quem pediu", "telefone"}


def test_pacote_igual_a_cada_vez(banco, tmp_path):
    montar_pacote(tmp_path / "a")
    montar_pacote(tmp_path / "b")
    a = {p.relative_to(tmp_path / "a"): p.read_bytes() for p in (tmp_path / "a").rglob("*") if p.is_file()}
    b = {p.relative_to(tmp_path / "b"): p.read_bytes() for p in (tmp_path / "b").rglob("*") if p.is_file()}
    assert a.keys() == b.keys() and [k for k in a if a[k] != b[k]] == []


def test_pacote_tira_cpf_mesmo_mascarado(pacote):
    # o representante da empresa aparece com o CPF no texto do aditivo; no pacote, nem mascarado
    objetos = [a["objeto"] for a in _tabela(pacote, "core.aditivo") if "Sicrano" in (a["objeto"] or "")]
    assert objetos and objetos[0].endswith("inscrito no CPF sob o nº [CPF omitido].")


def test_regras_refeitas_sobre_o_pacote_dao_os_mesmos_casos(banco, pacote):
    # é o que a metodologia ensina: carregar as tabelas abertas e rodar o SQL de cada regra
    con = duckdb.connect()
    for p in sorted((pacote / "tabelas").glob("*.parquet")):
        esquema, tabela = p.stem.split(".")
        con.execute(f"create schema if not exists {esquema}")
        con.execute(f"create view {esquema}.{tabela} as select * from '{p}'")
    con.execute("create macro hoje() as (select data from core.referencia)")
    regras = con.execute("select id, sql from sinais.regra").fetchall()
    refeito = {r: len(con.execute(sql).fetchall()) for r, sql in regras}
    con.close()
    db = duckdb.connect(str(banco), read_only=True)
    no_banco = dict(db.execute("select regra_id, count(*) from sinais.ocorrencia where ativo group by 1").fetchall())
    db.close()
    assert {r: n for r, n in refeito.items() if n} == no_banco


def test_metodologia_cobre_cada_regra_na_versao_atual():
    from pathlib import Path

    import yaml

    texto = (Path(__file__).parents[1] / "docs" / "metodologia.md").read_text(encoding="utf-8")
    for arq in sorted((Path(__file__).parents[1] / "slf" / "regras").glob("*.yaml")):
        r = yaml.safe_load(arq.read_text(encoding="utf-8"))
        assert f"### {r['id']} · {r['nome']} · versão {r['versao']}" in texto, r["id"]
