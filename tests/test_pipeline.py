"""Coleta nas fixtures -> raw -> staging -> core -> testes de dados -> sinais."""
from __future__ import annotations

import collections
import hashlib
import json
import shutil
from datetime import date

import duckdb
import pytest
from fastapi.testclient import TestClient  # importado antes do conftest trocar o httpx.Client

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


def test_mei_no_formato_novo_conta_como_pessoa_fisica(banco):
    # desde 2023 a Receita monta o nome do MEI como "raiz do CNPJ + nome do dono"
    assert _um(banco, "select tipo_pessoa, pessoa_fisica from core.contrato where sequencial = 5") == ("PJ", True)
    assert _um(banco, "select pessoa_fisica from core.fornecedor where ni = '44555666000177'") == (True,)


def test_pessoa_fisica_vale_para_todos_os_contratos_do_fornecedor(banco):
    # o mesmo MEI num contrato com o CPF no fim e noutro só com o nome: os dois contam como pessoa física
    assert _um(banco, "select bool_and(pessoa_fisica) from core.contrato where sequencial in (6, 7)") == (True,)


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
    assert _um(DB, "select count(*) from core.contrato") == (7,)


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
    assert nomes == {701: "Ana Exemplo", 702: "Beto Exemplo",
                     411: "Comissão de Obras Públicas, Transporte e Habitação"}
    # o pedido 9005 é dos dois vereadores e o 9007, do Beto com a comissão: conta para cada um
    por_vereador = dict(con.execute("select id_vereador, count(*) from core.pedido_autor group by 1").fetchall())
    assert por_vereador == {701: 3, 702: 4, 411: 1}


def test_cargo_de_quem_assina(banco):
    con = duckdb.connect(str(banco), read_only=True)
    cargos = dict(con.execute("select id, cargo from core.vereador").fetchall())
    # o Beto está no cadastro da Câmara (mandato atual); a Ana já saiu e o cargo vem do "Ver.ª" do nome
    assert cargos == {701: "Vereadora", 702: "Vereador", 411: "Comissão"}


def test_cadastro_dos_autores_de_emenda(banco):
    con = duckdb.connect(str(banco), read_only=True)
    linhas = {r[0]: r[1:] for r in con.execute(
        "select codigo_autor, nome, cargo, uf, link from core.parlamentar").fetchall()}
    # "Parlamentar Um" tem homônimo de SP e, no RS, já foi registrada como "Coronel Parlamentar Um" (como o
    # Zucco na Câmara): casa por qualquer grafia, vale o cadastro do RS e o nome que casou
    assert linhas["1234"] == ("Parlamentar Um", "Deputada federal", "RS", "https://www.camara.leg.br/deputados/1002")
    assert linhas["5678"][:3] == ("Parlamentar Dois", "Senadora", "RS")
    assert _um(banco, "select count(distinct cargo_parlamentar) from core.rastro_plano") == (2,)
    assert _um(banco, "select cargo_parlamentar from core.emenda where codigo_emenda = '202412340001'") == (
        "Deputada federal",)


def test_cadastro_de_todas_as_legislaturas(banco):
    """O cadastro vem com ?all: quem já saiu do mandato (Ana) também tem partido e cargo da fonte."""
    con = duckdb.connect(str(banco), read_only=True)
    partidos = dict(con.execute("select id, partido from core.vereador").fetchall())
    assert partidos[701] == "PSOL" and partidos[702] == "MDB"


def test_foto_do_vereador(banco):
    """A foto vai para o raw como veio e para data/fotos reduzida. Foto que sumiu do CDN (Ana) não
    derruba a coleta: o vereador fica sem foto."""
    from PIL import Image

    from slf.config import DATA
    from slf.raw import ultima_coleta_boa

    con = duckdb.connect(str(banco), read_only=True)
    fotos = dict(con.execute("select id, foto from core.vereador").fetchall())
    assert fotos == {701: None, 702: "vereador-702.jpg", 411: None}
    bruta = ultima_coleta_boa("camara") / "fotos" / "vereador-702.jpg"
    assert Image.open(bruta).size == (300, 400)
    assert "fotos/vereador-702.jpg" in (bruta.parent.parent / "manifest.jsonl").read_text(encoding="utf-8")
    reduzida = Image.open(DATA / "fotos" / "vereador-702.jpg")
    assert max(reduzida.size) <= 160 and reduzida.format == "JPEG"

def test_foto_de_deputado_e_senador(banco):
    """Só baixa foto de quem é da UF da cidade (o SP 1001 fica de fora); a que falha (1003, 9002) não
    derruba a coleta. A foto do Senado, grande, também sai reduzida."""
    from PIL import Image

    from slf.config import DATA
    from slf.raw import ultima_coleta_boa

    con = duckdb.connect(str(banco), read_only=True)
    fotos = dict(con.execute("select codigo_autor, foto from core.parlamentar").fetchall())
    assert fotos == {"1234": "camara-1002.jpg", "5678": "senado-9001.jpg"}
    assert sorted(p.name for p in (ultima_coleta_boa("congresso") / "fotos").iterdir()) == [
        "camara-1002.jpg", "senado-9001.jpg"]
    assert max(Image.open(DATA / "fotos" / "senado-9001.jpg").size) <= 160

def test_situacao_do_pedido_na_camara(banco):
    """O último passo de tramitação de cada pedido; sem detalhe na API (9005), fica sem situação."""
    con = duckdb.connect(str(banco), read_only=True)
    situacao = {r[0]: (r[1], str(r[2]) if r[2] else None) for r in con.execute(
        "select id, situacao, situacao_data from core.pedido").fetchall()}
    assert situacao == {
        9001: ("Encaminhado para o Executivo", "2025-03-01"), 9002: ("Arquivado", "2025-12-20"),
        9003: ("Encaminhado à Comissão", "2025-04-01"), 9004: ("Encaminhado para o Executivo", "2026-02-01"),
        9005: (None, None), 9007: ("Encaminha para Pauta da Sessão - Para Leitura", "2026-11-18")}


def test_tramitacao_aos_poucos(api_falsa, monkeypatch):
    """Cada coleta tem um limite de consultas. Começa pelos pedidos mais novos sem situação; depois
    reaproveita da coleta anterior o que já está encaminhado ao Executivo ou arquivado (revê uma vez por
    mês) e consulta de novo só o que ainda anda na Câmara. A emenda (9006) não é pedido: nunca consulta."""
    import time

    import httpx
    from conftest import responder

    import slf.http

    consultados = []

    def contando(request):
        if request.url.path.startswith("/proposicao/"):
            consultados.append(int(request.url.path.rsplit("/", 1)[1]))
        return responder(request)

    monkeypatch.setattr(slf.http.httpx, "Client",
                        lambda **kw: httpx._client.Client(transport=httpx.MockTransport(contando), **kw))

    def coletar_camara():
        consultados.clear()
        assert cli.coletar(["camara"]) == []
        tram = json.loads((ultima_coleta_boa("camara") / "tramitacoes.json").read_text(encoding="utf-8"))
        time.sleep(1.1)  # a pasta da coleta tem o segundo no nome
        return sorted(consultados), sorted(t["id"] for t in tram)

    monkeypatch.setenv("SLF_CAMARA_TRAMITACOES", "3")
    assert coletar_camara() == ([9004, 9005, 9007], [9004, 9007])
    monkeypatch.setenv("SLF_CAMARA_TRAMITACOES", "100")
    # 9004 já está no Executivo e foi visto hoje: fica; 9007 ainda está na pauta: consulta de novo
    assert coletar_camara() == ([9001, 9002, 9003, 9005, 9007], [9001, 9002, 9003, 9004, 9007])
    assert coletar_camara() == ([9003, 9005, 9007], [9001, 9002, 9003, 9004, 9007])

def test_area_de_cada_plano(banco):
    """A área é a função do orçamento que o Transferegov põe no plano, sem o código. Plano com mais de
    uma função vira "Mais de uma área" (a fonte não diz quanto vai para cada); duas subfunções da mesma
    função continuam uma área só; plano sem área fica "Sem área informada"."""
    con = duckdb.connect(str(banco), read_only=True)
    areas = dict(con.execute("select id_plano_acao, area from core.plano_acao").fetchall())
    assert areas == {1001: "Saúde", 1002: "Mais de uma área", 1003: "Desporto e Lazer",
                     1004: "Sem área informada"}

def test_congresso_vazio_nao_apaga_o_cargo(api_falsa, monkeypatch):
    """Cadastro vazio deixa a coleta sem _OK; sem nenhuma coleta boa, o autor fica com o nome do
    Transferegov e sem cargo, e o resto do banco sai igual."""
    import httpx
    from conftest import responder

    import slf.http

    def senado_vazio(request):
        if request.url.host == "legis.senado.leg.br":
            return httpx.Response(200, json={})
        return responder(request)

    monkeypatch.setattr(slf.http.httpx, "Client",
                        lambda **kw: httpx._client.Client(transport=httpx.MockTransport(senado_vazio), **kw))
    assert cli.coletar(cli.COLETORES) == ["congresso"]
    assert ultima_coleta_boa("congresso") is None
    processar.atualizar()
    assert _um(DB, "select count(*) from core.parlamentar where cargo is null") == (2,)
    assert _um(DB, "select nome from core.parlamentar where codigo_autor = '1234'") == ("Parlamentar Um",)
    assert _um(DB, "select count(*) from core.plano_acao") == (4,)


def test_bairro_pela_api_e_pelo_texto(banco):
    con = duckdb.connect(str(banco), read_only=True)
    # 9004 só diz "no bairro Feitoria Seller" na ementa: entra pela ementa, no bairro Feitoria.
    # 9005 cita a "Av. Feitoria" (rua): o bairro vem só da API, não do nome da rua.
    assert sorted(con.execute("select id_pedido, id_bairro, fonte from core.pedido_bairro").fetchall()) == [
        (9001, 1, "camara"), (9002, 1, "camara"), (9003, 2, "camara"), (9004, 2, "ementa"), (9005, 2, "camara")]


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


def test_podar_mantem_as_ultimas_boas(tmp_path, monkeypatch):
    from slf import raw

    monkeypatch.setattr(raw, "RAW", tmp_path)
    fonte = tmp_path / "pncp"
    for nome, ok in [("2026-01-01T000000", True), ("2026-01-02T000000", False), ("2026-01-03T000000", True),
                     ("2026-01-04T000000", True), ("2026-01-05T000000", False)]:
        (fonte / nome).mkdir(parents=True)
        if ok:
            (fonte / nome / "_OK").write_text("ok")
    raw.podar(manter=2)
    # fica: as 2 últimas boas e a incompleta mais nova que elas (pode estar em andamento)
    assert sorted(p.name for p in fonte.iterdir()) == ["2026-01-03T000000", "2026-01-04T000000", "2026-01-05T000000"]


# ===== Resultado repetível (D43) =====

def _exportar_tudo(pasta):
    from slf.exportar import exportar

    exportar(pasta, "publico")
    return {p.relative_to(pasta).as_posix(): p.read_bytes() for p in sorted(pasta.rglob("*")) if p.is_file()}


def test_processar_de_novo_da_o_mesmo_resultado(banco, tmp_path):
    primeira = _exportar_tudo(tmp_path / "a")
    processar.atualizar()
    segunda = _exportar_tudo(tmp_path / "b")
    assert primeira.keys() == segunda.keys()
    assert [arq for arq in primeira if primeira[arq] != segunda[arq]] == []


def _proveniencia(pasta, alterar=None):
    """A proveniência da exportação em `pasta`, opcionalmente alterada, gravada num arquivo à parte."""
    prov = json.loads((pasta / "proveniencia.json").read_text(encoding="utf-8"))
    if alterar:
        alterar(prov)
    destino = pasta.parent / f"proveniencia-{pasta.name}.json"
    destino.write_text(json.dumps(prov, ensure_ascii=False), encoding="utf-8")
    return destino


def _coleta(prov_arquivo, fonte: str) -> str:
    prov = json.loads(prov_arquivo.read_text(encoding="utf-8"))
    return next(f["coleta"] for f in prov["fontes"] if f["fonte"] == fonte)


def test_refazer_pela_proveniencia_da_o_mesmo_resultado(banco, tmp_path, capsys):
    primeira = _exportar_tudo(tmp_path / "a")
    prov = _proveniencia(tmp_path / "a")
    # uma coleta nova e diferente do Transferegov: sem a proveniência, seria ela a usada
    _nova_coleta("transferegov", {"plano_acao_especial": lambda planos: [
        {**p, "valor_investimento_plano_acao": (p["valor_investimento_plano_acao"] or 0) + 1000} for p in planos]})
    capsys.readouterr()

    cli.main(["atualizar", "--proveniencia", str(prov)])
    saida = capsys.readouterr().out
    segunda = _exportar_tudo(tmp_path / "b")
    assert primeira.keys() == segunda.keys()
    assert [arq for arq in primeira if primeira[arq] != segunda[arq]] == []
    assert "commit" not in saida  # mesmo commit: nenhum aviso

    # a coleta fixada não vaza: o atualizar seguinte volta à última boa, que muda o resultado
    assert ultima_coleta_boa("transferegov").name == "2099-01-01T000000"
    processar.atualizar()
    terceira = _exportar_tudo(tmp_path / "c")
    assert [arq for arq in primeira if primeira[arq] != terceira.get(arq)] != []


def test_refazer_para_se_o_arquivo_mudou(banco, tmp_path):
    _exportar_tudo(tmp_path / "a")
    prov = _proveniencia(tmp_path / "a")
    arq = RAW / "transferegov" / _coleta(prov, "transferegov") / "plano_acao_especial.json"
    arq.write_text(arq.read_text(encoding="utf-8").replace("500000.0", "500001.0"), encoding="utf-8")
    antes = DB.read_bytes()

    with pytest.raises(SystemExit) as erro:
        processar.atualizar(proveniencia=prov)
    mensagem = str(erro.value)
    assert "transferegov" in mensagem and "plano_acao_especial.json" in mensagem and "sha256" in mensagem
    assert DB.read_bytes() == antes
    assert not DB_TMP.exists()


def test_refazer_lista_cada_diferenca(banco, tmp_path):
    _exportar_tudo(tmp_path / "a")
    prov = _proveniencia(tmp_path / "a")
    (RAW / "siconfi" / _coleta(prov, "siconfi") / "rreo.json").unlink()
    (RAW / "camara" / _coleta(prov, "camara") / "fotos" / "vereador-99.jpg").write_bytes(b"foto a mais")
    (RAW / "camara" / _coleta(prov, "camara") / ".DS_Store").write_bytes(b"do Finder, nao conta")

    with pytest.raises(SystemExit) as erro:
        processar.atualizar(proveniencia=prov)
    linhas = [linha for linha in str(erro.value).splitlines() if linha.startswith("  - ")]
    assert len(linhas) == 2
    assert any("siconfi" in linha and "rreo.json" in linha for linha in linhas)
    assert any("camara" in linha and "fotos/vereador-99.jpg" in linha for linha in linhas)


def test_refazer_para_se_a_coleta_sumiu(banco, tmp_path):
    _exportar_tudo(tmp_path / "a")

    def coleta_que_nao_existe(p):
        next(f for f in p["fontes"] if f["fonte"] == "pncp")["coleta"] = "2000-01-01T000000"

    prov = _proveniencia(tmp_path / "a", coleta_que_nao_existe)
    antes = DB.read_bytes()

    with pytest.raises(SystemExit) as erro:
        processar.atualizar(proveniencia=prov)
    assert "pncp" in str(erro.value) and "2000-01-01T000000" in str(erro.value)
    assert DB.read_bytes() == antes
    assert not DB_TMP.exists()


def test_refazer_fonte_sem_coleta_fica_sem_coleta(banco, tmp_path):
    _exportar_tudo(tmp_path / "a")

    def sem_tce(p):
        tce = next(f for f in p["fontes"] if f["fonte"] == "tce")
        tce.update(coleta=None, coletado_em=None, arquivos=[])

    processar.atualizar(proveniencia=_proveniencia(tmp_path / "a", sem_tce))
    assert _um(DB, "select coleta from core.fonte where fonte = 'tce'") == (None,)
    assert _um(DB, "select count(*) from staging.tce_operacao") == (0,)
    assert ultima_coleta_boa("tce") is not None  # a coleta continua lá; só não foi usada


def test_refazer_avisa_se_o_commit_e_outro(banco, tmp_path, capsys):
    from slf.consultas import _commit

    _exportar_tudo(tmp_path / "a")
    prov = _proveniencia(tmp_path / "a", lambda p: p.update(commit="0" * 40))
    capsys.readouterr()

    processar.atualizar(proveniencia=prov)  # avisa, mas não para
    saida = capsys.readouterr().out
    assert "aviso" in saida and "0" * 40 in saida and str(_commit()) in saida
    assert "Banco atualizado" in saida


def test_data_de_referencia_e_a_da_coleta_e_nao_a_de_hoje(banco):
    # rodar o processamento outro dia, sobre as mesmas coletas, tem que dar o mesmo resultado
    for manifesto in RAW.rglob("manifest.jsonl"):
        itens = [json.loads(linha) for linha in manifesto.read_text(encoding="utf-8").splitlines() if linha]
        manifesto.write_text("".join(json.dumps({**i, "coletado_em": "2025-12-31T10:00:00"}) + "\n" for i in itens),
                             encoding="utf-8")
    processar.atualizar()
    assert _um(DB, "select data from core.referencia") == (date(2025, 12, 31),)
    assert _um(DB, "select max(ultima_vez) from sinais.ocorrencia where ativo") == (date(2025, 12, 31),)


def test_nome_do_fornecedor_e_o_do_contrato_mais_recente(banco):
    # o mesmo CNPJ com dois nomes: vale o do contrato assinado por último, sempre o mesmo a cada processamento
    assert _um(banco, "select nome from core.fornecedor where ni = '55666777000188'") == ("PEDRO EXEMPLO",)


# ===== Pendências da revisão: reabertura, fuso, Câmara vazia =====

def test_reabertura_vale_tambem_na_api(banco):
    # D17: o descartado volta a "novo" quando o valor muda; a API reaplicava o "descartado" por cima
    from slf import api

    r08_c3 = _id("R08", "89814693000160-2-000003/2024")
    REVISAO.write_text(json.dumps({r08_c3: {"status": "descartado", "nota": "reforma", "valor": 0.3}}),
                       encoding="utf-8")
    processar.atualizar()
    cliente = TestClient(api.app)
    assert cliente.get(f"/api/sinais/{r08_c3}").json()["status"] == "descartado"
    _nova_coleta("pncp", {"contratos": lambda cs: [
        {**c, "valorGlobal": 140_000.0} if c["sequencialContrato"] == 3 else c for c in cs]})
    processar.atualizar()
    assert cliente.get(f"/api/sinais/{r08_c3}").json()["status"] == "novo"


def test_hora_da_coleta_no_fuso_da_cidade():
    # o GitHub roda em UTC; a hora gravada é a da cidade (America/Sao_Paulo), senão uma coleta
    # às 22h vira o dia seguinte
    import os
    import time
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from slf.raw import Coleta

    antes = os.environ.get("TZ")
    os.environ["TZ"] = "UTC"
    time.tzset()
    try:
        col = Coleta("teste-fuso")
        col.salvar("x", [1])
        col.concluir()
        linha = (col.dir / "manifest.jsonl").read_text().splitlines()[0]
        gravada = datetime.fromisoformat(json.loads(linha)["coletado_em"])
        cidade = datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
        assert abs(gravada - cidade) < timedelta(minutes=2)
        assert abs(datetime.strptime(col.dir.name, "%Y-%m-%dT%H%M%S") - cidade) < timedelta(minutes=2)
    finally:
        if antes is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = antes
        time.tzset()


def test_camara_vazia_nao_vira_coleta_boa(banco, api_falsa, monkeypatch):
    # a API respondeu sem nada num ano que tinha pedidos: fica a coleta anterior (e o cache de situação)
    import slf.coletores.camara as camara

    anterior = ultima_coleta_boa("camara")
    original = camara._todas
    monkeypatch.setattr(camara, "_todas", lambda cli, api, params: [] if params.get("ano") == 2026
                        else original(cli, api, params))
    assert cli.coletar(["camara"]) == ["camara"]
    assert ultima_coleta_boa("camara") == anterior


def test_pedido_tem_teste_de_volume():
    assert "pedido" in processar.TABELAS_VOLUME
