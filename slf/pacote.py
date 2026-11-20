"""Pacote de dados abertos (D43): as tabelas tratadas, em Parquet e em modo público, para quem quiser
refazer as contas, testar outra regra ou comparar com outra cidade.

Entra o que o site usa, com as mesmas regras de dados sensíveis (sensivel.py, D40):
- contrato, fornecedor, aditivo e compra de pessoa física (inclui MEI) sem nome, sem CPF e sem objeto;
- texto dos pedidos sem o contato de quem pediu nem o número da casa de morador;
- só os sinais revisados (confirmado ou encaminhado), sem a nota de revisão;
- em toda coluna de texto, CPF nenhum, nem mascarado (vira "[CPF omitido]").
Fica de fora `core.proposicao` (as outras proposições da Câmara, que o site não mostra e o D40 não trata).

Cada tabela sai ordenada por todas as colunas: o mesmo banco dá os mesmos arquivos, byte a byte.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import duckdb

from .config import DB
from .consultas import PUBLICOS, Consulta
from .sensivel import OBJETO_OMITIDO, PESSOA_FISICA, limpar_pedido, sem_documento, titulo_pessoa_fisica
from .sinais import ler_revisao

_PF_CONTRATO = "select 1 from core.contrato c where c.pessoa_fisica"

# tabela -> consulta em modo público (sem tratamento: a tabela inteira)
TABELAS: dict[str, str | None] = {
    "core.aditivo": f"""select a.* replace (case when c.pessoa_fisica then '{OBJETO_OMITIDO}' else a.objeto end
                                             as objeto)
                        from core.aditivo a left join core.contrato c on c.id = a.contrato_id""",
    "core.arquivo_coleta": None,
    "core.bairro": None,
    "core.compra": f"""select k.* replace (case when exists ({_PF_CONTRATO} and c.compra_id = k.id)
                                               then '{OBJETO_OMITIDO}' else k.objeto end as objeto)
                       from core.compra k""",
    "core.credor_ano": f"""select * replace (
                             case when pessoa_fisica then null else ni end as ni,
                             case when pessoa_fisica then '{PESSOA_FISICA}' else nome end as nome)
                           from core.credor_ano""",
    "core.despesa_mes": None,
    "core.contrato": f"""select * replace (
                           case when pessoa_fisica then '{PESSOA_FISICA}' else fornecedor_nome end as fornecedor_nome,
                           case when pessoa_fisica then null else fornecedor_ni end as fornecedor_ni,
                           case when pessoa_fisica then '{OBJETO_OMITIDO}' else objeto end as objeto)
                         from core.contrato""",
    "core.emenda": None,
    "core.fonte": None,
    "core.fornecedor": f"""select * replace (
                             case when pessoa_fisica then null else id end as id,
                             case when pessoa_fisica then null else ni end as ni,
                             case when pessoa_fisica then '{PESSOA_FISICA}' else nome end as nome)
                           from core.fornecedor""",
    "core.limite_pessoal": None,
    "core.meta": None,
    "core.parlamentar": None,
    "core.pedido": None,  # o texto passa por limpar_pedido em _ajustar
    "core.pedido_autor": None,
    "core.pedido_bairro": None,
    "core.pessoal": None,
    "core.plano_acao": None,
    "core.prazo_plano": None,
    "core.rastro_plano": None,
    "core.receita": None,
    "core.referencia": None,
    "core.relatorio_gestao": None,
    "core.resultado_anual": None,
    "core.tema": None,
    "core.transferencia": None,
    "core.vereador": None,
    "sinais.regra": None,
    "sinais.ocorrencia": f"""select id, regra_id, regra_versao, chave, pf as pessoa_fisica, titulo,
                               valor_observado,
                               case when pf then json_merge_patch(evidencia, '{{"fornecedor": "{PESSOA_FISICA}"}}')
                                    else evidencia end as evidencia,
                               quando, primeira_vez, ultima_vez, status
                             from (select *, coalesce(json_extract_string(evidencia, '$.pessoa_fisica') = 'true'
                                                      or json_extract_string(evidencia, '$.tipo_pessoa') = 'PF',
                                                      false) as pf
                                   from sinais.ocorrencia)
                             where ativo and status in ({", ".join(f"'{s}'" for s in PUBLICOS)})""",
}

LEIAME = """# Pacote de dados abertos · Finanças de {ente}

Dados públicos de {ente}/{uf} tratados pelo projeto https://github.com/vinidotruan/financas-sl.
Data de referência: {referencia}. Código: commit {commit}.

- `tabelas/*.parquet`: as tabelas tratadas (`core.*`) e as regras e sinais revisados (`sinais.*`), em modo
  público. Leia com DuckDB (`select * from 'tabelas/core.contrato.parquet'`), pandas, R ou Polars.
- `proveniencia.json`: de onde veio cada número: o commit do código, a data de referência, a versão de
  cada regra e, de cada fonte, a coleta usada e o sha256, a URL e os parâmetros de cada arquivo bruto.

Modo público (D40): pessoa física (inclusive MEI) aparece como "pessoa física", sem CPF, sem nome e sem o
objeto do contrato; o texto dos pedidos sai sem o contato de quem pediu e sem o número da casa de morador;
só entram os sinais revisados. Os dados brutos não são publicados porque trazem CPF.

As regras estão em `sinais.regra` (coluna `sql`) e em `slf/regras/` no repositório: rodá-las sobre estas
tabelas refaz os valores observados. Sinal é ponto de atenção calculado a partir de dados públicos, não
acusação. Metodologia: `docs/metodologia.md` no repositório.
"""


def _ajustar(tabela: str, linha: dict) -> dict:
    """O que o SQL não faz: a limpeza do texto dos pedidos, o título do sinal de pessoa física e, em
    toda coluna de texto, nenhum CPF, nem mascarado (o do representante da empresa no aditivo, por exemplo)."""
    if tabela == "core.pedido":
        linha["ementa"] = limpar_pedido(linha["ementa"])
    if tabela == "sinais.ocorrencia" and linha["pessoa_fisica"]:
        linha["titulo"] = titulo_pessoa_fisica(linha["chave"])
    return sem_documento(linha)


def _gravar(con, tabela: str, consulta: str, destino: Path) -> int:
    cur = con.execute(f"select * from ({consulta})")
    colunas = [c[0] for c in cur.description]
    linhas = [_ajustar(tabela, dict(zip(colunas, linha, strict=True))) for linha in cur.fetchall()]
    con.execute(f"create or replace temp table _pacote as select * from ({consulta}) limit 0")
    if linhas:
        marcas = ", ".join("?" * len(colunas))
        con.executemany(f"insert into _pacote values ({marcas})", [[li[c] for c in colunas] for li in linhas])
    con.execute(f"copy (select * from _pacote order by all) to '{destino}' (format parquet)")
    return len(linhas)


def montar_pacote(saida: Path) -> dict[str, int]:
    """Grava o pacote em `saida` (apaga antes). Devolve as linhas de cada tabela."""
    if not DB.exists():
        raise SystemExit("Banco ainda não existe. Rode: slf atualizar")
    shutil.rmtree(saida, ignore_errors=True)
    (saida / "tabelas").mkdir(parents=True)
    linhas: dict[str, int] = {}
    # banco anexado só para leitura numa conexão em memória: a tabela de trabalho fica fora dele
    con = duckdb.connect()
    try:
        con.execute(f"attach '{DB}' as banco (read_only)")
        con.execute("use banco")
        for tabela, consulta in TABELAS.items():
            linhas[tabela] = _gravar(con, tabela, consulta or f"select * from {tabela}",
                                     saida / "tabelas" / f"{tabela}.parquet")
        prov = Consulta(con, "publico", ler_revisao()).proveniencia()
    finally:
        con.close()
    (saida / "proveniencia.json").write_text(json.dumps(prov, ensure_ascii=False, indent=1) + "\n",
                                             encoding="utf-8")
    (saida / "LEIAME.md").write_text(LEIAME.format(
        ente=prov["ente"]["nome"] or "a cidade", uf=prov["ente"]["uf"] or "", referencia=prov["data_referencia"],
        commit=(prov["commit"] or "desconhecido")[:12]), encoding="utf-8")
    return linhas
