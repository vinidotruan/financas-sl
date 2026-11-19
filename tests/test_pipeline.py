"""Coleta nas fixtures -> raw -> staging -> core -> testes de dados -> sinais."""
from __future__ import annotations

import collections
import hashlib
import json
import shutil

import duckdb
import pytest

from slf import cli, processar
from slf.config import DB, DB_TMP, RAW, REVISAO
from slf.raw import ultima_coleta_boa


def _um(db, sql, params=None):
    con = duckdb.connect(str(db), read_only=True)
    try:
        return con.execute(sql, params or []).fetchone()
    finally:
        con.close()


def _ocorrencias(db, regra: str) -> dict:
    con = duckdb.connect(str(db), read_only=True)
    try:
        linhas = con.execute("select chave, valor_observado, evidencia, ativo, status, primeira_vez "
                             "from sinais.ocorrencia where regra_id = ?", [regra]).fetchall()
    finally:
        con.close()
    return {c: {"valor": v, "evidencia": json.loads(e), "ativo": a, "status": s, "primeira_vez": p}
            for c, v, e, a, s, p in linhas}


def _id(regra: str, chave: str) -> str:
    return hashlib.md5(f"{regra}|{chave}".encode()).hexdigest()


def _nova_coleta(fonte: str, alteracoes: dict) -> None:
    """Copia a última coleta boa como se fosse uma coleta nova, com alguns arquivos alterados."""
    destino = RAW / fonte / "2099-01-01T000000"
    shutil.copytree(ultima_coleta_boa(fonte), destino)
    for nome, alterar in alteracoes.items():
        arq = destino / f"{nome}.json"
        arq.write_text(json.dumps(alterar(json.loads(arq.read_text(encoding="utf-8"))), ensure_ascii=False),
                       encoding="utf-8")


# ===== Transferegov =====

def test_numeros_das_emendas(banco):
    assert _um(banco, "select count(*), sum(valor_indicado) from core.plano_acao") == (4, 1_100_000)
    # o documento hábil sem ordem bancária (R$ 50 mil) não conta como transferido
    assert _um(banco, "select sum(valor) from core.transferencia") == (900_000,)
    assert _um(banco, "select planos, codigo_formatado from core.emenda where codigo_emenda = '202412340001'") \
        == (2, "2024/12340001")


def test_r02_so_mede_com_relatorio_entregue(banco):
    r02 = _ocorrencias(banco, "R02")
    # 1001 não tem relatório: sem relatório não é 0% executado, então fica de fora
    assert set(r02) == {"202412340001/1002"}
    assert r02["202412340001/1002"]["valor"] == pytest.approx(0.05)


def test_r03_relatorio_ausente(banco):
    r03 = _ocorrencias(banco, "R03")
    assert set(r03) == {"202412340001/1001", "202556780002/1003"}
    # relatório em elaboração não conta como entregue, mas aparece na evidência
    assert r03["202556780002/1003"]["evidencia"]["relatorios_em_elaboracao"] == 1
    assert r03["202412340001/1001"]["evidencia"]["prazo_vencido"] == "2025-06-30"
    # valor observado estável (não muda a cada dia, senão um descartado voltaria todo dia)
    assert r03["202412340001/1001"]["valor"] == 500_000


# ===== PNCP =====

def test_r05_conta_aditivo_e_ignora_apostilamento(banco):
    assert set(_ocorrencias(banco, "R05")) == {"89814693000160-2-000001/2024"}


def test_r06_publicacao_depois_de_fechar(banco):
    r06 = _ocorrencias(banco, "R06")
    assert set(r06) == {"89814693000160-1-000012/2024"}
    assert r06["89814693000160-1-000012/2024"]["valor"] == 11


def test_r07_contratacao_direta(banco):
    r07 = _ocorrencias(banco, "R07")
    assert set(r07) == {"89814693000160/2024"}
    assert r07["89814693000160/2024"]["valor"] == pytest.approx(220_000 / 400_000)


def test_r08_aditivo_acima_do_teto(banco):
    r08 = _ocorrencias(banco, "R08")
    assert set(r08) == {"89814693000160-2-000002/2024", "89814693000160-2-000003/2024"}
    assert r08["89814693000160-2-000002/2024"]["evidencia"]["pessoa_fisica"] is True


def test_mei_conta_como_pessoa_fisica(banco):
    assert _um(banco, "select tipo_pessoa, pessoa_fisica from core.contrato where sequencial = 4") == ("PJ", True)
    assert _um(banco, "select pessoa_fisica from core.contrato where sequencial = 3") == (False,)


# ===== SICONFI =====

def test_contas(banco):
    assert _um(banco, "select exercicio, periodo, pct_rcl, limite_alerta, limite_prudencial, limite_maximo "
                      "from core.limite_pessoal") == (2024, 3, 40.4, 48.6, 51.3, 54.0)
    # o coletor pede só o RREO Anexo 01
    assert _um(banco, "select count(*), count(distinct anexo) from core.receita") == (4, 1)
    assert _um(banco, "select exercicio, bimestre, receita_realizada, despesa_paga from core.resultado_anual") \
        == (2024, 6, 1_500_000_000, 1_400_000_000)


def test_nenhuma_regra_falhou(banco):
    assert _um(banco, "select count(*) from sinais.erro") == (0,)


# ===== Robustez =====

def test_staging_tolerante_sem_nenhuma_coleta():
    processar.atualizar()
    assert _um(DB, "select count(*) from core.contrato") == (0,)
    assert _um(DB, "select count(*) from sinais.ocorrencia") == (0,)
    assert _um(DB, "select count(*) from sinais.erro") == (0,)


def test_uma_fonte_falhar_nao_para_as_outras(api_falsa, monkeypatch):
    from slf.coletores import siconfi

    def quebrar():
        raise RuntimeError("SICONFI fora do ar")

    monkeypatch.setattr(siconfi, "coletar", quebrar)
    assert cli.coletar(cli.COLETORES) == ["siconfi"]
    assert ultima_coleta_boa("transferegov") and ultima_coleta_boa("pncp")
    assert ultima_coleta_boa("siconfi") is None
    processar.atualizar()
    assert _um(DB, "select coleta from core.fonte where fonte = 'siconfi'") == (None,)
    assert _um(DB, "select count(*) from core.plano_acao") == (4,)


def test_pncp_tenta_de_novo_e_registra_o_que_falhou(api_falsa, monkeypatch):
    import httpx
    from conftest import responder

    import slf.http
    from slf.coletores import pncp

    monkeypatch.setattr(pncp.time, "sleep", lambda s: None)
    vezes = collections.Counter()

    def instavel(request):
        caminho = request.url.path
        vezes[caminho] += 1
        if caminho.endswith("/compras/2024/13") and vezes[caminho] == 1:
            return httpx.Response(404)  # falha uma vez e volta na segunda tentativa
        if caminho.endswith("/compras/2024/12"):
            return httpx.Response(404)  # falha sempre
        return responder(request)

    monkeypatch.setattr(slf.http.httpx, "Client",
                        lambda **kw: httpx._client.Client(transport=httpx.MockTransport(instavel), **kw))
    col = pncp.coletar()
    compras = json.loads((col.dir / "compras.json").read_text(encoding="utf-8"))
    assert {c["sequencialCompra"] for c in compras} == {10, 11, 13}
    falhas = json.loads((col.dir / "falhas.json").read_text(encoding="utf-8"))
    assert [(f["etapa"], f["chave"]) for f in falhas] == [("compra", "89814693000160-1-000012/2024")]
    assert falhas[0]["erro"].startswith("HTTPStatusError")
    assert (col.dir / "_OK").exists()


def test_coleta_sem_ok_e_ignorada(banco):
    pasta = RAW / "pncp" / "2099-01-01T000000"
    pasta.mkdir()
    (pasta / "contratos.json").write_text("[]")
    processar.atualizar()
    assert _um(DB, "select count(*) from core.contrato") == (4,)


def test_teste_duro_barra_a_troca_do_banco(banco):
    antes = banco.stat().st_mtime_ns
    _nova_coleta("transferegov", {"plano_acao_especial": lambda planos: planos + planos[:1]})
    with pytest.raises(SystemExit):
        processar.atualizar()
    assert banco.stat().st_mtime_ns == antes
    assert not DB_TMP.exists()


def test_historico_e_revisao(banco):
    r08_c3 = _id("R08", "89814693000160-2-000003/2024")
    r03_1003 = _id("R03", "202556780002/1003")
    con = duckdb.connect(str(banco))
    con.execute("update sinais.ocorrencia set primeira_vez = date '2025-01-01' where id = ?", [r03_1003])
    con.close()
    REVISAO.write_text(json.dumps({r08_c3: {"status": "descartado", "nota": "reforma, teto de 50%",
                                            "valor": 0.3}}), encoding="utf-8")

    processar.atualizar()  # mesma coleta: o descarte vale
    assert _ocorrencias(DB, "R08")["89814693000160-2-000003/2024"]["status"] == "descartado"

    # nova coleta: o plano 1003 entregou o relatório e o contrato 3 recebeu mais um acréscimo
    _nova_coleta("transferegov", {"relatorio_gestao_novo_especial": lambda rs: [
        {**r, "situacao_relatorio_gestao_novo": "DISPONIBILIZADO"} for r in rs]})
    _nova_coleta("pncp", {"contratos": lambda cs: [
        {**c, "valorGlobal": 140_000.0} if c["sequencialContrato"] == 3 else c for c in cs]})
    processar.atualizar()

    r03 = _ocorrencias(DB, "R03")["202556780002/1003"]
    assert r03["ativo"] is False                       # sumiu: fica no histórico como inativo
    assert str(r03["primeira_vez"]) == "2025-01-01"    # e guarda quando apareceu
    # descartado volta a novo quando o valor observado muda
    assert _ocorrencias(DB, "R08")["89814693000160-2-000003/2024"]["status"] == "novo"


# ===== Câmara =====

def test_pedidos_dos_vereadores(banco):
    # a emenda não é pedido; os outros 6 são pedidos de providência ou indicações
    assert _um(banco, "select count(*) from core.pedido") == (6,)
    assert dict(duckdb.connect(str(banco), read_only=True).execute(
        "select id, tema from core.pedido").fetchall()) == {
        9001: "Iluminação pública", 9002: "Sinalização e trânsito", 9003: "Limpeza e capina",
        9004: "Pavimentação e buracos", 9005: "Transporte coletivo", 9007: "Outros"}


def test_vereador_sem_tratamento_e_coautoria(banco):
    con = duckdb.connect(str(banco), read_only=True)
    nomes = dict(con.execute("select id, nome from core.vereador").fetchall())
    assert nomes == {701: "Ana Exemplo", 702: "Beto Exemplo"}
    # o pedido 9005 é dos dois: conta para cada um
    por_vereador = dict(con.execute("select id_vereador, count(*) from core.pedido_autor group by 1").fetchall())
    assert por_vereador == {701: 3, 702: 4}


def test_bairro_vem_do_filtro_da_api(banco):
    con = duckdb.connect(str(banco), read_only=True)
    assert sorted(con.execute("select id_pedido, id_bairro from core.pedido_bairro").fetchall()) == [
        (9001, 1), (9002, 1), (9003, 2), (9005, 2)]


def test_camara_pagina_de_verdade(api_falsa, monkeypatch):
    from slf.coletores import camara

    monkeypatch.setattr(camara, "PAGINA", 2)  # força várias páginas com a fixture pequena
    col = camara.coletar()
    proposicoes = json.loads((col.dir / "proposicoes.json").read_text(encoding="utf-8"))
    assert len(proposicoes) == 7 and "_bairros" not in proposicoes[0]


def test_cidade_sem_camara_configurada_pula(api_falsa, monkeypatch):
    from slf.coletores import camara

    monkeypatch.setattr(camara, "ente", lambda: {"inicio": None})
    assert camara.coletar() is None
