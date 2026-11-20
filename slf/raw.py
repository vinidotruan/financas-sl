"""Camada raw: grava o que veio de cada fonte, sem alterar, com manifest."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
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

    def salvar_arquivo(self, caminho: str, conteudo: bytes, url: str = "") -> Path:
        """Arquivo binário (uma foto, por exemplo) dentro da coleta, com linha no manifest."""
        destino = self.dir / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(conteudo)
        linha = {
            "arquivo": caminho,
            "url": url,
            "params": {},
            "linhas": None,
            "bytes": len(conteudo),
            "sha256": hashlib.sha256(conteudo).hexdigest(),
            "coletado_em": datetime.now().isoformat(timespec="seconds"),
        }
        with open(self.manifest, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
        return destino

    def concluir(self) -> None:
        (self.dir / "_OK").write_text(datetime.now().isoformat(timespec="seconds"))


# Coletas fixadas por fonte enquanto se refaz uma publicação pela proveniência dela (D43). Fora do
# `coletas_fixadas`, None: vale a última coleta boa.
_FIXADAS: ContextVar[dict[str, str | None] | None] = ContextVar("coletas_fixadas", default=None)


@contextmanager
def coletas_fixadas(coletas: dict[str, str | None]) -> Iterator[None]:
    """Dentro do bloco, ultima_coleta_boa devolve a coleta indicada de cada fonte; fonte fora do mapa ou
    com None fica sem coleta. Ao sair, mesmo com erro, volta a valer a última coleta boa."""
    token = _FIXADAS.set(dict(coletas))
    try:
        yield
    finally:
        _FIXADAS.reset(token)


def ultima_coleta_boa(fonte: str) -> Path | None:
    fixadas = _FIXADAS.get()
    if fixadas is not None:
        coleta = fixadas.get(fonte)
        return RAW / fonte / coleta if coleta else None
    base = RAW / fonte
    if not base.exists():
        return None
    boas = sorted(d for d in base.iterdir() if (d / "_OK").exists())
    return boas[-1] if boas else None


def diferencas(fontes: list[dict]) -> list[str]:
    """Confere as coletas de uma proveniência (D43) contra data/raw, antes de refazer a publicação: a pasta
    de cada coleta existe, cada arquivo listado existe com o mesmo sha256 e não sobra arquivo fora da lista
    (as fotos são lidas da pasta inteira; arquivo oculto, como o .DS_Store do Mac, não conta). Devolve uma
    linha por diferença; vazia, as coletas são as mesmas."""
    saida = []
    for f in fontes:
        fonte, coleta = f["fonte"], f.get("coleta")
        if not coleta:
            continue
        pasta = RAW / fonte / coleta
        if not pasta.is_dir():
            saida.append(f"{fonte} · {coleta}: pasta não encontrada ({pasta})")
            continue
        listados = set()
        for a in f.get("arquivos") or []:
            listados.add(a["arquivo"])
            arq = pasta / a["arquivo"]
            if not arq.is_file():
                saida.append(f"{fonte} · {coleta} · {a['arquivo']}: arquivo não encontrado")
                continue
            with open(arq, "rb") as aberto:
                achado = hashlib.file_digest(aberto, "sha256").hexdigest()
            if achado != a["sha256"]:
                saida.append(f"{fonte} · {coleta} · {a['arquivo']}: sha256 esperado {a['sha256']}, achado {achado}")
        for arq in sorted(p for p in pasta.rglob("*") if p.is_file() and not p.name.startswith(".")):
            nome = arq.relative_to(pasta).as_posix()
            if nome not in listados and nome not in ("manifest.jsonl", "_OK"):
                saida.append(f"{fonte} · {coleta} · {nome}: arquivo a mais, que a proveniência não lista")
    return saida


def podar(manter: int = 3) -> list[Path]:
    """Apaga coletas antigas de data/raw: mantém as `manter` últimas boas de cada fonte e apaga as
    incompletas mais velhas que a última boa (tentativas que falharam). Uma incompleta mais nova que a
    última boa fica, porque pode estar em andamento. Serve para o cache do GitHub Actions não crescer
    todo dia; nada é editado, só coletas inteiras saem."""
    import shutil

    removidas: list[Path] = []
    if not RAW.exists():
        return removidas
    for base in sorted(p for p in RAW.iterdir() if p.is_dir()):
        coletas = sorted(d for d in base.iterdir() if d.is_dir())
        boas = [d for d in coletas if (d / "_OK").exists()]
        if not boas:
            continue
        ficam = set(boas[-max(manter, 1):])
        for d in coletas:
            if d not in ficam and d.name < boas[-1].name:
                shutil.rmtree(d)
                removidas.append(d)
    return removidas
