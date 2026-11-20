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
