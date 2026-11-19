"""Caminhos e configuração do projeto."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(os.environ.get("SLF_HOME", Path(__file__).resolve().parent.parent))
DATA = ROOT / "data"
RAW = DATA / "raw"
DB = DATA / "slf.duckdb"
FOTOS = DATA / "fotos"  # fotos reduzidas, derivadas do raw a cada atualizar
DB_TMP = DATA / "slf.novo.duckdb"
# status e nota de cada sinal. No GitHub Actions aponta para config/revisao-publica.json
# (só id e status dos confirmados e encaminhados, sem nota), gerado por `slf revisao-publica`.
REVISAO = Path(os.environ.get("SLF_REVISAO", DATA / "revisao.json"))
REGRAS = Path(__file__).resolve().parent / "regras"
WEB = Path(__file__).resolve().parent / "web"
# front buildado (npm run build em front/); fica junto do código, não de SLF_HOME
SITE = Path(os.environ.get("SLF_SITE", Path(__file__).resolve().parent.parent / "site"))

# "privado" mostra tudo e permite marcar status; "publico" mascara pessoa física
# e só mostra sinais revisados.
MODO = os.environ.get("SLF_MODO", "privado")


def ente() -> dict:
    with open(ROOT / "config" / "ente.yaml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if isinstance(cfg.get("inicio"), str):
        cfg["inicio"] = date.fromisoformat(cfg["inicio"])
    return cfg
