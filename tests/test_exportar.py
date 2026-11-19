"""Exportação estática: cada arquivo é o que a API devolve no mesmo modo, com os mesmos filtros."""
from __future__ import annotations

import hashlib
import json
import re

import pytest
from fastapi.testclient import TestClient

from slf.config import DATA, REVISAO
from slf.exportar import exportar, revisao_publica

R07 = hashlib.md5(b"R07|89814693000160/2024").hexdigest()
R08_PF = hashlib.md5(b"R08|89814693000160-2-000002/2024").hexdigest()

# arquivo exportado -> rota da API
ROTAS = {
    "fontes.json": "/api/fontes", "regras.json": "/api/regras", "sinais.json": "/api/sinais",
    "emendas.json": "/api/emendas", "parlamentares.json": "/api/parlamentares",
    "fornecedores.json": "/api/fornecedores", "contas.json": "/api/contas", "pedidos.json": "/api/pedidos",
}


def _rota_de(caminho: str) -> str:
    if caminho in ROTAS:
        return ROTAS[caminho]
    pasta, nome = caminho.split("/")
    chave = nome.removesuffix(".json")
    return {"sinais": f"/api/sinais/{chave}", "rastro": f"/api/emendas/{chave}/rastro",
            "parlamentares": f"/api/parlamentares/{chave}", "fornecedores": f"/api/fornecedores/{chave}",
            "vereadores": f"/api/vereadores/{chave}"}[pasta]


@pytest.mark.parametrize("modo", ["privado", "publico"])
def test_exportacao_igual_a_api(banco, tmp_path, monkeypatch, modo):
    import slf.api

    monkeypatch.setattr(slf.api, "MODO", modo)
    REVISAO.write_text(json.dumps({R07: {"status": "confirmado", "nota": "nota privada", "valor": 0.55}}),
                       encoding="utf-8")
    exportar(tmp_path, modo)
    cliente = TestClient(slf.api.app)
    arquivos = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*.json"))
    assert len(arquivos) > 10
    for arq in arquivos:
        esperado = cliente.get(_rota_de(arq)).json()
        assert json.loads((tmp_path / arq).read_text(encoding="utf-8")) == esperado, arq
    corpo = "".join((tmp_path / a).read_text(encoding="utf-8") for a in arquivos)
    assert not re.search(r"(?<![0-9A-Za-z])(12345678901|98765432100|22233344455)(?![0-9A-Za-z])", corpo)
    if modo == "publico":
        assert "nota privada" not in corpo
        assert [a for a in arquivos if a.startswith("sinais/")] == [f"sinais/{R07}.json"]
        for dono in ("FULANO", "MARIA EXEMPLO", "JOANA EXEMPLO", "PEDRO EXEMPLO"):
            assert dono not in corpo, dono


def test_exportacao_apaga_o_que_sobrou(banco, tmp_path):
    velho = tmp_path / "sinais" / "sinal-que-saiu.json"
    velho.parent.mkdir(parents=True)
    velho.write_text("{}")
    exportar(tmp_path, "publico")
    assert not velho.exists()


def test_revisao_publica_sem_nota(tmp_path):
    origem = DATA / "revisao.json"
    DATA.mkdir(parents=True, exist_ok=True)
    origem.write_text(json.dumps({
        R07: {"status": "confirmado", "nota": "conversa com fulano", "valor": 0.55},
        R08_PF: {"status": "em análise", "nota": "ver contrato", "valor": 0.33},
    }), encoding="utf-8")
    destino = tmp_path / "revisao-publica.json"
    assert revisao_publica(origem, destino) == 1
    assert json.loads(destino.read_text(encoding="utf-8")) == {R07: {"status": "confirmado", "valor": 0.55}}


def test_exportacao_leva_as_fotos(banco, tmp_path):
    exportar(tmp_path, "publico")
    assert sorted(p.name for p in (tmp_path / "fotos").iterdir()) == [
        "camara-1002.jpg", "senado-9001.jpg", "vereador-702.jpg"]
