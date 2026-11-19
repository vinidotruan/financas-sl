"""API: privacidade nos dois modos, revisão e as rotas que o front usa."""
from __future__ import annotations

import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from slf.config import REVISAO

CPFS = ("12345678901", "98765432100")  # PF e o CPF no nome do MEI, nas fixtures
R08_PF = hashlib.md5(b"R08|89814693000160-2-000002/2024").hexdigest()
R07 = hashlib.md5(b"R07|89814693000160/2024").hexdigest()


@pytest.fixture
def cliente(banco):
    from slf import api

    return TestClient(api.app)


@pytest.fixture
def publico(monkeypatch):
    import slf.api

    monkeypatch.setattr(slf.api, "MODO", "publico")


def _confirmar(*ids):
    REVISAO.write_text(json.dumps({i: {"status": "confirmado", "nota": None, "valor": None} for i in ids}),
                       encoding="utf-8")


@pytest.mark.parametrize("modo", ["privado", "publico"])
def test_cpf_nunca_aparece_inteiro(cliente, monkeypatch, modo):
    import slf.api

    monkeypatch.setattr(slf.api, "MODO", modo)
    _confirmar(R08_PF)
    for rota in ("/api/sinais", f"/api/sinais/{R08_PF}", "/api/contratos", "/api/fornecedores"):
        corpo = cliente.get(rota).text
        for cpf in CPFS:
            assert cpf not in corpo, f"{rota} ({modo}) mostrou um CPF inteiro"


def test_privado_mostra_nome_com_cpf_mascarado(cliente):
    sinal = cliente.get(f"/api/sinais/{R08_PF}").json()
    assert sinal["titulo"].startswith("FULANO DE TAL")
    assert sinal["evidencia"]["fornecedor"] == "***.456.789-**"
    mei = [c for c in cliente.get("/api/contratos").json() if c["sequencial"] == 4][0]
    assert mei["fornecedor_nome"] == "MARIA EXEMPLO ***.654.321-**"


def test_publico_so_mostra_sinal_revisado(cliente, publico):
    assert cliente.get("/api/sinais").json() == []
    assert cliente.get(f"/api/sinais/{R07}").status_code == 404
    _confirmar(R08_PF, R07)
    assert {s["id"] for s in cliente.get("/api/sinais").json()} == {R08_PF, R07}


def test_publico_esconde_pessoa_fisica_e_mei(cliente, publico):
    _confirmar(R08_PF)
    sinal = cliente.get(f"/api/sinais/{R08_PF}").json()
    assert sinal["titulo"].startswith("Pessoa física · ")
    assert sinal["evidencia"]["fornecedor"] == "pessoa física"
    assert "FULANO" not in json.dumps(sinal)

    contratos = {c["sequencial"]: c for c in cliente.get("/api/contratos").json()}
    for seq in (2, 4):  # PF e MEI
        assert contratos[seq]["fornecedor_nome"] == "pessoa física"
        assert contratos[seq]["fornecedor_ni"] is None
    assert contratos[3]["fornecedor_nome"] == "CONSTRUTORA EXEMPLO SA"
    # buscar pelo nome não confirma quem é a pessoa física
    assert cliente.get("/api/contratos", params={"q": "FULANO"}).json() == []

    nomes = {f["nome"] for f in cliente.get("/api/fornecedores").json()}
    assert "pessoa física" in nomes and not any("MARIA" in n or "FULANO" in n for n in nomes)


def test_publico_nao_edita(cliente, publico):
    assert cliente.patch(f"/api/sinais/{R07}", json={"status": "confirmado"}).status_code == 403


def test_revisao_no_modo_privado(cliente):
    r = cliente.patch(f"/api/sinais/{R07}", json={"status": "em análise", "nota": "ver justificativas"})
    assert r.status_code == 200
    salvo = json.loads(REVISAO.read_text(encoding="utf-8"))[R07]
    assert salvo["status"] == "em análise" and salvo["valor"] == pytest.approx(0.55)
    assert cliente.get(f"/api/sinais/{R07}").json()["status"] == "em análise"
    assert cliente.patch(f"/api/sinais/{R07}", json={"status": "irregular"}).status_code == 422


def test_rastro_da_emenda(cliente):
    rastro = cliente.get("/api/emendas/2024/12340001/rastro").json()
    assert rastro["codigo"] == "202412340001"
    assert [p["id_plano_acao"] for p in rastro["planos"]] == [1001, 1002]
    assert sum(t["valor"] for t in rastro["transferencias"]) == 600_000
    assert len(rastro["metas"]) == 2


def test_contas(cliente):
    linha = cliente.get("/api/contas").json()["limite_pessoal"][0]
    assert (linha["pct_rcl"], linha["limite_maximo"]) == (40.4, 54.0)


def test_regras_com_contagem_e_texto_da_tela(cliente):
    regras = {r["id"]: r for r in cliente.get("/api/regras").json()}
    assert regras["R08"]["ativos"] == 2 and regras["R02"]["ativos"] == 1
    assert regras["R03"]["observado"] == {"rotulo": "Transferido sem prestação de contas", "formato": "brl"}
    assert "{prazo_vencido|data}" in regras["R03"]["resumo"]
    assert "sql" not in regras["R03"]


def test_regras_no_publico_contam_so_os_revisados(cliente, publico):
    _confirmar(R07)
    regras = {r["id"]: r for r in cliente.get("/api/regras").json()}
    assert regras["R07"]["ativos"] == 1 and regras["R08"]["ativos"] == 0


def test_nota_nao_sai_no_publico(cliente, monkeypatch):
    import slf.api

    REVISAO.write_text(json.dumps({R07: {"status": "confirmado", "nota": "conversa com fulano", "valor": 0.55}}),
                       encoding="utf-8")
    assert cliente.get(f"/api/sinais/{R07}").json()["nota"] == "conversa com fulano"
    monkeypatch.setattr(slf.api, "MODO", "publico")
    assert cliente.get(f"/api/sinais/{R07}").json()["nota"] is None


def test_sinal_leva_ao_contrato_e_ao_fornecedor(cliente):
    lig = cliente.get(f"/api/sinais/{R08_PF}").json()["ligacoes"]
    assert [c["id"] for c in lig["contratos"]] == ["89814693000160-2-000002/2024"]
    fid = lig["contratos"][0]["fornecedor_id"]
    assert fid and fid != "12345678901"


def test_ficha_de_fornecedor(cliente, publico):
    pj = [f for f in cliente.get("/api/fornecedores").json() if f["nome"] == "CONSTRUTORA EXEMPLO SA"][0]
    ficha = cliente.get(f"/api/fornecedores/{pj['id']}").json()
    assert ficha["contratos"] == 1 and ficha["contratos_lista"][0]["objeto"] == "Reforma de escola municipal"
    assert ficha["sinais"] == []  # no modo público, só sinais revisados aparecem


def test_ficha_de_pessoa_fisica(cliente, monkeypatch):
    import slf.api

    fornecedores = cliente.get("/api/fornecedores").json()
    ids = {f["nome"]: f["id"] for f in fornecedores}
    pf, mei = ids["FULANO DE TAL"], ids["MARIA EXEMPLO ***.654.321-**"]
    corpo = cliente.get(f"/api/fornecedores/{pf}")
    assert corpo.status_code == 200 and "12345678901" not in corpo.text
    assert len(corpo.json()["sinais"]) == 1  # o R08 do contrato dele
    monkeypatch.setattr(slf.api, "MODO", "publico")
    assert cliente.get(f"/api/fornecedores/{pf}").status_code == 404
    assert cliente.get(f"/api/fornecedores/{mei}").status_code == 404
    assert all(f["id"] is None for f in cliente.get("/api/fornecedores").json() if f["nome"] == "pessoa física")


def test_ficha_de_parlamentar(cliente):
    lista = cliente.get("/api/parlamentares").json()
    assert [(p["nome"], p["emendas"], p["planos"]) for p in lista][0] == ("Parlamentar Um", 1, 2)
    ficha = cliente.get("/api/parlamentares/1234").json()
    assert [e["codigo"] for e in ficha["emendas_lista"]] == ["2024/12340001"]
    assert {s["regra_id"] for s in ficha["sinais"]} == {"R02", "R03"}


def test_rastro_mostra_cada_fonte(cliente):
    valores = {v["etapa"]: v for v in cliente.get("/api/emendas/202412340001/rastro").json()["valores"]}
    assert valores["Indicado"]["valor"] == 600_000 and valores["Transferido"]["valor"] == 600_000
    assert valores["Executado (relatório de gestão)"]["valor"] == 5_000
    assert valores["Pago"]["valor"] is None and "fase 2" in valores["Pago"]["nota"]


def test_cidade_vem_da_configuracao(cliente):
    assert cliente.get("/api/fontes").json()["ente"] == {"nome": "São Leopoldo", "uf": "RS", "ibge": 4318705}
