"""TCE-RS, dados abertos: despesa orçamentária por empenhos, um arquivo por órgão e ano (D44).

Cada arquivo é um zip com um CSV: empenhos (E), liquidações (L) e pagamentos (P), com o credor, o CNPJ
ou CPF, o histórico e a licitação. Vale para todos os municípios do RS; os órgãos de cada cidade e o
código deles no TCE-RS ficam em `config/ente.yaml` (`tce_rs.orgaos`).

O zip é guardado como veio (raw imutável). O ano corrente e o anterior são baixados a cada coleta,
porque o município manda os dados ao Tribunal com meses de atraso; os anos mais velhos vêm da coleta
boa anterior quando estão lá. Arquivo que o TCE-RS não tem (404: órgão sem dado naquele ano) fica em
`ausentes.json` e não derruba a coleta.
"""
from __future__ import annotations

import json
from datetime import date

import httpx

from ..config import ente
from ..http import Cliente
from ..raw import Coleta, ultima_coleta_boa

URL = "https://dados.tce.rs.gov.br/dados/municipal/empenhos/{ano}/{codigo}.csv.zip"


def coletar() -> Coleta:
    cfg = ente()
    orgaos = [int(o["codigo"]) for o in (cfg.get("tce_rs") or {}).get("orgaos") or []]
    anterior = ultima_coleta_boa("tce")
    col = Coleta("tce")
    cli = Cliente(pausa=0.5, timeout=120)
    hoje = date.today().year
    ausentes = []
    try:
        for codigo in orgaos:
            baixados = reaproveitados = tamanho = 0
            for ano in range(cfg["inicio"].year, hoje + 1):
                nome = f"empenhos/{codigo}-{ano}.csv.zip"
                url = URL.format(ano=ano, codigo=codigo)
                velho = anterior / nome if anterior else None
                if ano < hoje - 1 and velho is not None and velho.exists():
                    conteudo = velho.read_bytes()
                    reaproveitados += 1
                else:
                    try:
                        conteudo = cli.get_bytes(url)
                    except httpx.HTTPStatusError as erro:
                        if erro.response.status_code != 404:
                            raise
                        ausentes.append({"orgao": codigo, "ano": ano})
                        continue
                    baixados += 1
                col.salvar_arquivo(nome, conteudo, url)
                tamanho += len(conteudo)
            print(f"  tce: órgão {codigo}: {baixados} baixados, {reaproveitados} da coleta anterior, "
                  f"{tamanho / 1e6:.1f} MB")
        col.salvar("ausentes", ausentes, URL)
        print(f"  tce: {len(ausentes)} arquivos que o TCE-RS não tem ({json.dumps(ausentes)[:120]})")
        col.concluir()
    finally:
        cli.fechar()
    return col
