"""Exportação estática: um arquivo JSON por rota da API, para o front ler sem servidor
(build com VITE_DADOS=estatico). Usa as mesmas consultas da API (consultas.py), no modo pedido, então o
conteúdo de cada arquivo é o mesmo que a API devolveria nesse modo, com os mesmos filtros de privacidade.

A pasta de saída é apagada antes: um sinal que deixou de ser público, ou um fornecedor que passou a
contar como pessoa física, não pode continuar no site por sobra de arquivo antigo.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

from .config import DB, FOTOS
from .consultas import Consulta, sem_cpf
from .sinais import ler_revisao


def exportar(saida: Path, modo: str = "publico") -> dict[str, int]:
    if not DB.exists():
        raise SystemExit("Banco ainda não existe. Rode: slf diario")
    shutil.rmtree(saida, ignore_errors=True)
    saida.mkdir(parents=True)
    contagem: dict[str, int] = {}

    def gravar(caminho: str, dado) -> None:
        if dado is None:
            return
        destino = saida / caminho
        destino.parent.mkdir(parents=True, exist_ok=True)
        # sem_cpf de novo, como a API faz na resposta: segunda barreira
        destino.write_text(json.dumps(sem_cpf(dado), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        pasta = caminho.split("/")[0] if "/" in caminho else "raiz"
        contagem[pasta] = contagem.get(pasta, 0) + 1

    con = duckdb.connect(str(DB), read_only=True)
    try:
        c = Consulta(con, modo, ler_revisao())
        gravar("fontes.json", c.fontes())
        gravar("proveniencia.json", c.proveniencia())
        gravar("regras.json", c.regras())
        sinais = c.sinais()
        gravar("sinais.json", sinais)
        for s in sinais:
            gravar(f"sinais/{s['id']}.json", c.sinal(s["id"]))
        emendas = c.emendas()
        gravar("emendas.json", emendas)
        for e in emendas:
            gravar(f"rastro/{e['codigo_emenda']}.json", c.rastro(e["codigo_emenda"]))
        parlamentares = c.parlamentares()
        gravar("parlamentares.json", parlamentares)
        for p in parlamentares:
            gravar(f"parlamentares/{p['codigo']}.json", c.parlamentar(str(p["codigo"])))
        fornecedores = c.fornecedores()
        gravar("fornecedores.json", fornecedores)
        for f in fornecedores:
            if f["id"]:  # pessoa física no modo público não tem id nem ficha
                gravar(f"fornecedores/{f['id']}.json", c.fornecedor(f["id"]))
        gravar("contas.json", c.contas())
        pedidos = c.pedidos()
        gravar("pedidos.json", pedidos)
        for vid in sorted({v["id"] for v in pedidos["por_vereador"]}):
            gravar(f"vereadores/{vid}.json", c.vereador(str(vid)))
        # fotos: só as que alguma tela usa, já reduzidas
        for arquivo in c.fotos():
            if (FOTOS / arquivo).is_file():
                (saida / "fotos").mkdir(exist_ok=True)
                shutil.copyfile(FOTOS / arquivo, saida / "fotos" / arquivo)
                contagem["fotos"] = contagem.get("fotos", 0) + 1
    finally:
        con.close()
    return contagem


def revisao_publica(origem: Path, destino: Path) -> int:
    """Copia da revisão só o que pode ser público: id e status dos sinais confirmados ou encaminhados,
    sem a nota. É esse arquivo que vai para o repositório e que a publicação no GitHub Actions lê."""
    from .consultas import PUBLICOS

    try:
        rev = json.loads(origem.read_text(encoding="utf-8"))
    except FileNotFoundError:
        rev = {}
    publica = {oid: {"status": r["status"], "valor": r.get("valor")}
               for oid, r in sorted(rev.items()) if r.get("status") in PUBLICOS}
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(publica, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return len(publica)
