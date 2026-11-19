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
