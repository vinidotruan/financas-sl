"""Camada raw: grava o que veio de cada fonte, sem alterar, com manifest."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

from .config import RAW


class Coleta:
    """Uma execução de coleta de uma fonte. Só vira 'boa' quando fecha com sucesso."""

    def __init__(self, fonte: str):
        self.fonte = fonte
        self.inicio = datetime.now()
        self.dir = RAW / fonte / self.inicio.strftime("%Y-%m-%dT%H%M%S")
        self.dir.mkdir(parents=True, exist_ok=True)
        self.manifest = self.dir / "manifest.jsonl"

    def salvar(self, nome: str, dados, url: str = "", params: dict | None = None) -> Path:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        destino = self.dir / f"{nome}.json"
        destino.write_bytes(corpo)
        linha = {
            "arquivo": destino.name,
            "url": url,
            "params": params or {},
            "linhas": len(dados) if isinstance(dados, list) else None,
            "bytes": len(corpo),
            "sha256": hashlib.sha256(corpo).hexdigest(),
            "coletado_em": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self.manifest, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        return destino

    def concluir(self) -> None:
        (self.dir / "_OK").write_text(datetime.now().isoformat(timespec="seconds"))


def ultima_coleta_boa(fonte: str) -> Path | None:
    base = RAW / fonte
    if not base.exists():
        return None
    boas = sorted(d for d in base.iterdir() if (d / "_OK").exists())
    return boas[-1] if boas else None
