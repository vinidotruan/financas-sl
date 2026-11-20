"""TCE-RS, despesa orçamentária por empenhos (D44): coleta, pagamentos no core e o que sai no público."""
from __future__ import annotations

import hashlib
import json
import zipfile
from datetime import date
from pathlib import Path

from slf import cli
from slf.raw import ultima_coleta_boa

FIXTURES = Path(__file__).parent / "fixtures" / "tce"
ANOS = list(range(2024, date.today().year + 1))  # o ente de teste começa em 2024
TEM_FIXTURE = {(58700, 2024), (58700, 2025), (58700, 2026), (58701, 2025)}


def _manifesto(pasta: Path) -> dict:
    linhas = (pasta / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    return {i["arquivo"]: i for i in map(json.loads, linhas)}


# ===== Coleta =====

def test_coleta_tce_guarda_um_zip_por_orgao_e_ano(api_falsa):
    assert cli.coletar(["tce"]) == []
    pasta = ultima_coleta_boa("tce")
    zips = sorted(p.name for p in (pasta / "empenhos").glob("*.zip"))
    assert zips == sorted(f"{o}-{a}.csv.zip" for o, a in TEM_FIXTURE if a in ANOS)
    manifesto = _manifesto(pasta)
    for nome in zips:
        conteudo = (pasta / "empenhos" / nome).read_bytes()
        assert manifesto[f"empenhos/{nome}"]["sha256"] == hashlib.sha256(conteudo).hexdigest()
    with zipfile.ZipFile(pasta / "empenhos" / "58700-2025.csv.zip") as z:
        assert z.read("58700.csv") == (FIXTURES / "58700-2025.csv").read_bytes()


def test_arquivo_ausente_nao_derruba_a_coleta(api_falsa):
    # o SEMAE não tem arquivo nenhum e a Câmara só tem 2025: 404 vira "ausente", não falha
    assert cli.coletar(["tce"]) == []
    pasta = ultima_coleta_boa("tce")
    assert (pasta / "_OK").exists()
    ausentes = {(a["orgao"], a["ano"]) for a in json.loads((pasta / "ausentes.json").read_text(encoding="utf-8"))}
    assert ausentes == {(o, a) for o in (58700, 58701, 58702) for a in ANOS} - TEM_FIXTURE


def test_ano_fechado_vem_da_coleta_anterior(api_falsa, pedidos_tce):
    # o ano corrente e o anterior mudam (o município manda dados atrasados); os mais velhos, não
    assert cli.coletar(["tce"]) == []
    # a pasta da coleta tem precisão de segundo e os testes não esperam: a primeira vira uma coleta antiga
    primeira = ultima_coleta_boa("tce").rename(ultima_coleta_boa("tce").with_name("2000-01-01T000000"))
    assert cli.coletar(["tce"]) == []
    segunda = ultima_coleta_boa("tce")
    assert segunda != primeira
    hoje = date.today().year
    for ano in ANOS:
        caminho = f"/dados/municipal/empenhos/{ano}/58700.csv.zip"
        assert pedidos_tce[caminho] == (2 if ano >= hoje - 1 else 1), ano
    a, b = _manifesto(primeira), _manifesto(segunda)
    assert b["empenhos/58700-2024.csv.zip"]["sha256"] == a["empenhos/58700-2024.csv.zip"]["sha256"]


# ===== Pagamentos no core =====

def _um(sql: str):
    import duckdb

    from slf.config import DB

    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(sql).fetchone()
    finally:
        con.close()


def test_pagamento_conta_no_ano_da_data(banco):
    # o arquivo de 2025 traz também o pagamento de 2024-11-20: conta só em 2024, uma vez
    assert _um("select sum(pago) from core.despesa_mes where orgao = 58700 and ano = 2025") == (1928000,)
    assert _um("select sum(pago) from core.despesa_mes where orgao = 58700 and ano = 2024") == (1009999,)
    assert _um("select count(*) from core.despesa where orgao = 58700 and ano = 2024") == (2,)


def test_estorno_entra_na_soma(banco):
    assert _um("select pago, pagamentos from core.credor_ano "
               "where orgao = 58700 and ano = 2025 and nome = 'CONSTRUTORA EXEMPLO SA'") == (200000, 2)


def test_cnpj_sem_zeros_a_esquerda(banco):
    assert _um("select ni, repasse from core.credor_ano where nome = 'CAIXA ECONOMICA FEDERAL'") == (
        "00360305000104", True)


def test_mei_do_tce_e_pessoa_fisica(banco):
    # o TCE-RS manda o MEI como PJ; o nome no formato novo denuncia o dono (D40)
    assert _um("select pessoa_fisica, ni from core.credor_ano where nome = '12.345.678 JOANA EXEMPLO'") == (
        True, "12345678000190")
    assert _um("select pessoa_fisica, ni from core.credor_ano where nome = 'FULANA EXEMPLO'") == (True, "04567890123")


def test_repasse_e_empresa(banco):
    repasse = dict(_um_todos("select nome, repasse from core.credor_ano where orgao = 58700 and ano = 2025"))
    assert repasse["CAIXA ECONOMICA FEDERAL"] and repasse["INSTITUTO APOSENT PENSOES SERVIDORES MUNICIPAIS DE SL"]
    assert not repasse["GREEN EXEMPLO REFEICOES LTDA"] and not repasse["CONSTRUTORA EXEMPLO SA"]


def test_historico_nao_entra_no_banco(banco):
    # o histórico do empenho pode trazer nome e CPF de pessoa física: fica no raw
    assert _um("select count(*) from information_schema.columns where column_name = 'historico'") == (0,)


def _um_todos(sql: str):
    import duckdb

    from slf.config import DB

    con = duckdb.connect(str(DB), read_only=True)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def test_padroes_de_repasse_com_nomes_reais():
    # nomes como vêm do TCE-RS (19/11/2026): repasse e tributo retido não são empresa
    import re

    import yaml

    dados = yaml.safe_load((Path(__file__).parents[1] / "slf" / "repasses.yaml").read_text(encoding="utf-8"))
    eh_repasse = lambda nome: any(re.search(p, nome, re.I) for p in dados["padroes"])  # noqa: E731
    for nome in ("INST. NACIONAL SEGURO SOCIAL", "RIO GRANDE DO SUL PODER JUDICIARIO", "BANCO DO BRASIL S/A",
                 "CAIXA ECONOMICA FEDERAL", "FUNDACAO MUNICIPAL DE SAUDE DE SAO LEOPOLDO", "PASEP",
                 "BANRISUL SOLUCOES EM PAGAMENTOS S.A. - INSTITUICAO DE PAGAME"):
        assert eh_repasse(nome), nome
    for nome in ("GREEN CARD S/A REFEICOES COMERCIO E SERVICOS",
                 "INSTITUTO DESENVOLVIMENTO E ASSISTENCIA A SAUDE - IDEAS", "INSTALADORA ELETRICA MERCURIO",
                 "RGE SUL DISTRIBUIDORA DE ENERGIA S.A.", "ONCOLOGIA CENTENARIO LTDA"):
        assert not eh_repasse(nome), nome


def test_credor_sem_documento_fica_fora_da_lista(banco):
    # sem CNPJ nem CPF não dá para saber quem é: entra no total do mês, não vira credor (nem soma com outro)
    assert _um("select count(*) from core.despesa where nome like 'CREDOR SEM DOCUMENTO%' and ni is null") == (2,)
    assert _um("select count(*) from core.credor_ano where ni is null or nome like 'CREDOR SEM DOCUMENTO%'") == (0,)
    assert _um("select count(*) from core.fornecedor where ni is null or nome like 'CREDOR SEM DOCUMENTO%'") == (0,)


def test_resposta_que_nao_e_zip_derruba_so_a_coleta_do_tce(api_falsa, monkeypatch):
    # uma página HTML com status 200 (desafio do Cloudflare) não pode virar coleta boa
    import slf.http

    assert cli.coletar(["tce"]) == []
    boa = ultima_coleta_boa("tce").rename(ultima_coleta_boa("tce").with_name("2000-01-01T000000"))
    original = slf.http.Cliente.get_bytes

    def html_em_2025(self, url):
        return b"<html>verificando seu navegador</html>" if "/2025/58700" in url else original(self, url)

    monkeypatch.setattr(slf.http.Cliente, "get_bytes", html_em_2025)
    assert cli.coletar(["tce"]) == ["tce"]
    assert ultima_coleta_boa("tce") == boa
