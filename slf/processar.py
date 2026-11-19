"""Monta o banco: raw -> staging -> core -> testes -> sinais. Escreve num arquivo novo e
só troca pelo atual se os testes passarem, então a API nunca lê um banco pela metade."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import duckdb
import yaml

from . import sinais
from .config import DB, DB_TMP
from .raw import ultima_coleta_boa

# Colunas que o core usa. Se a fonte vier vazia ou sem a coluna, ela é criada como nula.
COLUNAS = {
    "tg_plano_acao_especial": ["id_plano_acao", "codigo_plano_acao", "ano_plano_acao", "situacao_plano_acao",
                               "nome_parlamentar_emenda_plano_acao", "codigo_parlamentar_emenda_plano_acao",
                               "numero_emenda_parlamentar_plano_acao",
                               "codigo_emenda_parlamentar_formatado_plano_acao", "motivo_impedimento_plano_acao",
                               "valor_custeio_plano_acao", "valor_investimento_plano_acao"],
    "tg_empenho_especial": ["id_empenho", "id_plano_acao", "numero_empenho", "data_emissao_empenho",
                            "valor_empenho", "situacao_empenho"],
    "tg_documento_habil_especial": ["id_dh", "id_empenho", "valor_dh", "data_emissao_dh"],
    "tg_ordem_pagamento_ordem_bancaria_especial": ["id_op_ob", "id_dh", "numero_ordem_bancaria",
                                                   "data_emissao_ob"],
    "tg_plano_trabalho_especial": ["id_plano_trabalho", "id_plano_acao", "situacao_plano_trabalho",
                                   "data_inicio_execucao_plano_trabalho", "data_fim_execucao_plano_trabalho"],
    "tg_relatorio_gestao_novo_especial": ["id_relatorio_gestao_novo", "id_plano_acao",
                                          "data_e_hora_relatorio_gestao_novo", "tipo_relatorio_gestao_novo",
                                          "valor_executado_relatorio_gestao_novo",
                                          "situacao_relatorio_gestao_novo"],
    "tg_relatorio_gestao_especial": ["id_relatorio_gestao", "id_plano_acao", "situacao_relatorio_gestao"],
    "tg_executor_especial": ["id_executor", "id_plano_acao", "cnpj_executor", "nome_executor", "objeto_executor"],
    "tg_meta_especial": ["id_meta", "id_executor", "nome_meta", "desc_meta"],
    "sc_rgf": ["exercicio", "periodo", "anexo", "coluna", "cod_conta", "conta", "valor"],
    "sc_rreo": ["exercicio", "periodo", "anexo", "coluna", "cod_conta", "conta", "valor"],
}

def _pega(d, ks):
    for k in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


# PNCP vem aninhado; achatamos só o que o core usa (o arquivo completo fica no raw).
def _achatar_pncp(nome: str, linhas: list) -> list:
    def g(d, *ks):
        return _pega(d, ks)

    if nome == "contratos":
        return [{
            "id": g(c, "numeroControlePNCP"), "compra_id": g(c, "numeroControlePncpCompra"),
            "orgao_cnpj": g(c, "orgaoEntidade", "cnpj"), "orgao_nome": g(c, "orgaoEntidade", "razaoSocial"),
            "unidade": g(c, "unidadeOrgao", "nomeUnidade"), "ano": g(c, "anoContrato"),
            "sequencial": g(c, "sequencialContrato"), "tipo": g(c, "tipoContrato", "nome"),
            "categoria": g(c, "categoriaProcesso", "nome"), "processo": g(c, "processo"),
            "tipo_pessoa": g(c, "tipoPessoa"), "fornecedor_ni": g(c, "niFornecedor"),
            "fornecedor_nome": g(c, "nomeRazaoSocialFornecedor"), "objeto": g(c, "objetoContrato"),
            "valor_inicial": g(c, "valorInicial"), "valor_global": g(c, "valorGlobal"),
            "data_assinatura": g(c, "dataAssinatura"), "vigencia_inicio": g(c, "dataVigenciaInicio"),
            "vigencia_fim": g(c, "dataVigenciaFim"), "publicado_em": g(c, "dataPublicacaoPncp"),
        } for c in linhas]
    if nome == "compras":
        return [{
            "id": g(c, "numeroControlePNCP"), "orgao_cnpj": g(c, "orgaoEntidade", "cnpj"),
            "ano": g(c, "anoCompra"), "sequencial": g(c, "sequencialCompra"),
            "modalidade": g(c, "modalidadeNome"), "modo_disputa": g(c, "modoDisputaNome"),
            "amparo": g(c, "amparoLegal", "nome"), "objeto": g(c, "objetoCompra"),
            "valor_estimado": g(c, "valorTotalEstimado"), "valor_homologado": g(c, "valorTotalHomologado"),
            "abertura_propostas": g(c, "dataAberturaProposta"),
            "encerramento_propostas": g(c, "dataEncerramentoProposta"),
            "publicado_em": g(c, "dataPublicacaoPncp"), "situacao": g(c, "situacaoCompraNome"),
        } for c in linhas]
    if nome == "termos":
        return [{
            "contrato_id": g(t, "contrato_id"), "tipo": g(t, "tipoTermoContratoNome"),
            "numero": g(t, "numeroTermoContrato"), "sequencial": g(t, "sequencialTermoContrato"),
            "data_assinatura": g(t, "dataAssinatura"), "publicado_em": g(t, "dataPublicacaoPncp"),
            "vigencia_fim": g(t, "dataVigenciaFim"), "prazo_aditado_dias": g(t, "prazoAditadoDias"),
            "qualif_vigencia": g(t, "qualificacaoVigencia"),
            "qualif_acrescimo": g(t, "qualificacaoAcrescimoSupressao"),
            "valor_acrescido": g(t, "valorAcrescido"), "valor_global": g(t, "valorGlobal"),
            "objeto": g(t, "objetoTermoContrato"), "fundamento": g(t, "fundamentoLegal"),
        } for t in linhas]
    return linhas


COLUNAS["pn_contratos"] = list(_achatar_pncp("contratos", [{}])[0].keys())
COLUNAS["pn_compras"] = list(_achatar_pncp("compras", [{}])[0].keys())
COLUNAS["pn_termos"] = list(_achatar_pncp("termos", [{}])[0].keys())


# Câmara: a proposição vem com a lista de proponentes dentro; achatamos em duas tabelas.
def _achatar_camara(nome: str, linhas: list) -> list:
    if nome == "proposicoes":
        return [{
            "id": p.get("ID"), "ano": p.get("ano"), "numero": p.get("numero"), "especie": p.get("especie"),
            "sigla_especie": p.get("sigla_especie"), "ementa": p.get("ementa"), "url": p.get("url"),
            "destinatario": p.get("destinatario"), "atualizado_em": p.get("updated_at"),
        } for p in linhas]
    if nome == "autores":
        return [{"id_proposicao": p.get("ID"), "id_autor": a.get("ID"), "nome": a.get("nome"),
                 "partido": a.get("partido")}
                for p in linhas for a in (p.get("proponente") or []) if isinstance(a, dict)]
    return linhas


COLUNAS["cm_proposicoes"] = list(_achatar_camara("proposicoes", [{}])[0].keys())
COLUNAS["cm_autores"] = ["id_proposicao", "id_autor", "nome", "partido"]
COLUNAS["cm_bairros"] = ["ID", "nome"]
COLUNAS["cm_proposicao_bairro"] = ["id_proposicao", "id_bairro"]

PREFIXO = {"transferegov": "tg", "siconfi": "sc", "pncp": "pn", "camara": "cm"}
ORIGEM_ARQUIVO = {("camara", "autores"): "proposicoes"}  # tabela de staging que sai de outro arquivo


def _carregar_tabela(con, tabela: str, arquivo: Path | None, linhas: list | None = None):
    if linhas is None and arquivo is not None:
        linhas = json.loads(arquivo.read_text(encoding="utf-8"))
    linhas = linhas or []
    if linhas:
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tmp:
            json.dump(linhas, tmp, ensure_ascii=False)
        con.execute(f"create or replace table staging.{tabela} as select * from "
                    f"read_json('{tmp.name}', format='array', sample_size=-1, "
                    f"maximum_object_size=104857600, union_by_name=true)")
        os.unlink(tmp.name)
    else:
        cols = ", ".join(f'"{c}" varchar' for c in COLUNAS.get(tabela, ["vazio"]))
        con.execute(f"create or replace table staging.{tabela} ({cols})")
    existentes = {r[0] for r in con.execute(
        "select column_name from information_schema.columns where table_schema='staging' and table_name=?",
        [tabela]).fetchall()}
    for c in COLUNAS.get(tabela, []):
        if c not in existentes:
            con.execute(f'alter table staging.{tabela} add column "{c}" varchar')


def carregar_staging(con) -> dict:
    con.execute("create schema if not exists staging")
    origem = {}
    for fonte, prefixo in PREFIXO.items():
        pasta = ultima_coleta_boa(fonte)
        origem[fonte] = pasta.name if pasta else None
        arquivos = {p.stem: p for p in pasta.glob("*.json")} if pasta else {}
        for tabela in [t for t in COLUNAS if t.startswith(prefixo + "_")]:
            nome = tabela[len(prefixo) + 1:]
            arq = arquivos.get(ORIGEM_ARQUIVO.get((fonte, nome), nome))
            if fonte in ("pncp", "camara"):
                bruto = json.loads(arq.read_text(encoding="utf-8")) if arq else []
                achatar = _achatar_pncp if fonte == "pncp" else _achatar_camara
                _carregar_tabela(con, tabela, None, achatar(nome, bruto))
            else:
                _carregar_tabela(con, tabela, arq)
    _carregar_temas(con)
    return origem


def _carregar_temas(con):
    """Regras de tema dos pedidos (slf/temas.yaml): configuração versionada, não dado coletado."""
    temas = yaml.safe_load((Path(__file__).parent / "temas.yaml").read_text(encoding="utf-8"))
    con.execute("create or replace table staging.cm_temas (ordem integer, tema varchar, padrao varchar)")
    for i, r in enumerate(temas):
        con.execute("insert into staging.cm_temas values (?, ?, ?)", [i, r["tema"], r["padrao"]])
    # apelidos de bairro (slf/bairros.yaml); o nome oficial de cada bairro entra no core
    apelidos = yaml.safe_load((Path(__file__).parent / "bairros.yaml").read_text(encoding="utf-8")) or {}
    con.execute("create or replace table staging.cm_bairro_apelido (bairro varchar, padrao varchar)")
    for bairro, padroes in apelidos.items():
        for padrao in padroes:
            con.execute("insert into staging.cm_bairro_apelido values (?, ?)", [bairro, padrao])


def _status_fontes(con, origem: dict):
    con.execute("create or replace table core.fonte (fonte varchar, coleta varchar, coletado_em varchar, "
                "arquivos integer, linhas bigint)")
    for fonte, coleta in origem.items():
        if not coleta:
            con.execute("insert into core.fonte values (?, null, null, 0, 0)", [fonte])
            continue
        pasta = ultima_coleta_boa(fonte)
        texto = (pasta / "manifest.jsonl").read_text(encoding="utf-8")
        itens = [json.loads(linha) for linha in texto.splitlines() if linha]
        con.execute("insert into core.fonte values (?, ?, ?, ?, ?)", [
            fonte, coleta, max(i["coletado_em"] for i in itens) if itens else None,
            len(itens), sum(i.get("linhas") or 0 for i in itens)])


TESTES_DUROS = [
    ("plano de ação com id repetido",
     "select count(*) - count(distinct id_plano_acao) from core.plano_acao"),
    ("contrato com id repetido", "select count(*) - count(distinct id) from core.contrato"),
    ("código de emenda fora do padrão de 12 dígitos",
     "select count(*) from core.plano_acao where codigo_emenda is not null "
     "and not regexp_full_match(codigo_emenda, '[0-9]{12}')"),
]
TABELAS_VOLUME = ["plano_acao", "contrato", "compra", "aditivo", "pessoal"]


def testar(con, banco_anterior: Path) -> list[str]:
    falhas = []
    for nome, sql in TESTES_DUROS:
        n = con.execute(sql).fetchone()[0]
        if n:
            falhas.append(f"{nome}: {n}")
    if banco_anterior.exists():
        con.execute(f"attach '{banco_anterior}' as anterior (read_only)")
        for t in TABELAS_VOLUME:
            try:
                antes = con.execute(f"select count(*) from anterior.core.{t}").fetchone()[0]
            except duckdb.Error:
                continue
            agora = con.execute(f"select count(*) from core.{t}").fetchone()[0]
            if antes >= 20 and agora < 0.8 * antes:
                falhas.append(f"core.{t} caiu de {antes} para {agora} linhas (mais de 20%)")
        con.execute("detach anterior")
    return falhas


def atualizar(forcar: bool = False) -> None:
    DB.parent.mkdir(parents=True, exist_ok=True)
    if DB_TMP.exists():
        DB_TMP.unlink()
    con = duckdb.connect(str(DB_TMP))
    try:
        origem = carregar_staging(con)
        con.execute("create schema if not exists core")
        sql_core = (Path(__file__).parent / "core.sql").read_text(encoding="utf-8")
        con.execute(sql_core)
        _status_fontes(con, origem)
        falhas = testar(con, DB)
        if falhas and not forcar:
            print("Testes falharam; o banco anterior continua valendo:")
            for f in falhas:
                print("  -", f)
            con.close()
            DB_TMP.unlink()
            raise SystemExit(1)
        n = sinais.rodar(con, DB)
        print(f"  {n} ocorrências de sinal ativas")
    finally:
        try:
            con.close()
        except Exception:
            pass
    os.replace(DB_TMP, DB)
    print(f"Banco atualizado: {DB}")
