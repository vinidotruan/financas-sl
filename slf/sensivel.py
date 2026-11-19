"""Dados sensíveis: o que nunca aparece e o que o modo público esconde (D40).

Um lugar só para as regras de privacidade do texto que vai para a API e para o site:
- CPF nunca inteiro, em nenhum modo (sem_cpf percorre a resposta toda);
- no modo público, pessoa física (inclui MEI e empresário individual) aparece como "pessoa física", e o
  objeto do contrato dela não aparece (costuma trazer o nome e, às vezes, o endereço);
- no modo público, o texto do pedido perde o contato de quem pediu (nome, telefone, CPF) e o número da
  casa quando fala de uma casa ou de um morador. O endereço do lugar do serviço (a boca de lobo, o buraco)
  fica, porque sem ele o pedido não se entende.

Quem decide se uma pessoa física é MEI é o core.sql (pela forma do nome); aqui só se esconde.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

PESSOA_FISICA = "pessoa física"
NOME_OMITIDO = "[nome omitido]"
CONTATO_OMITIDO = "[contato omitido]"
NUMERO_OMITIDO = "[nº omitido]"
# o objeto do contrato de pessoa física costuma trazer o nome dela, às vezes o endereço
OBJETO_OMITIDO = "objeto omitido (pessoa física)"

# CPF = 11 dígitos seguidos, ou no formato 123.456.789-01, sem letra nem dígito colado (CNPJ tem 14
# dígitos e o código da emenda, 12; ids em hash como "c89673977497c" não são CPF). Aparece no campo
# do fornecedor PF e também no nome de MEI e empresário individual ("FULANO DE TAL 12345678901").
_CPF = re.compile(r"(?<![0-9A-Za-z])(\d{3})\.?(\d{3})\.?(\d{3})-?(\d{2})(?![0-9A-Za-z])")
_CPF_MASCARADO_TEXTO = re.compile(r"\*{3}\.\d{3}\.\d{3}-\*{2}")


def sem_cpf(x):
    """CPF nunca aparece inteiro, em nenhum modo (LGPD)."""
    if isinstance(x, str):
        return _CPF.sub(lambda m: f"***.{m[2]}.{m[3]}-**", x)
    if isinstance(x, dict):
        return {k: sem_cpf(v) for k, v in x.items()}
    if isinstance(x, list):
        return [sem_cpf(v) for v in x]
    return x


def titulo_pessoa_fisica(chave: str) -> str:
    """Título do sinal de contrato com pessoa física: o número do contrato, sem nome nem objeto."""
    return f"{PESSOA_FISICA.capitalize()} · contrato {chave.rsplit('-', 1)[-1]}"


CPF_OMITIDO = "[CPF omitido]"


def sem_documento(x):
    """Para os dados abertos: CPF nenhum, nem mascarado (o do representante da empresa, no texto do
    aditivo, por exemplo). Percorre a estrutura inteira, como sem_cpf."""
    if isinstance(x, str):
        return _CPF_MASCARADO_TEXTO.sub(CPF_OMITIDO, sem_cpf(x))
    if isinstance(x, dict):
        return {k: sem_documento(v) for k, v in x.items()}
    if isinstance(x, list):
        return [sem_documento(v) for v in x]
    return x


# ===== Texto do pedido =====

# "Solicitante: Fulana Exemplo." / "SOLICITANTE: FULANA EXEMPLO- CONTATO: …": o nome vai até o fim da frase
_SOLICITANTE = re.compile(r"\b(solicitante|requerente)(\s*:\s*)[^.;\n–-]+", re.I)
# "Contato: (51) 99999-1234." / "CONTATO:***.456.789-** - BAIRRO": o valor vai até o fim da frase ou um " - "
_CONTATO = re.compile(r"\b(contato|telefone|fone|celular|whatsapp)\s*:\s*.*?(?=\s+-\s|[.;](?:\s|$)|$)", re.I)
# celular com 9 na frente, ou qualquer número com DDD entre parênteses; protocolo e ano não casam
_TELEFONE = re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}(?!\d)|(?<![\d/.-])9\d{4}-\d{4}(?!\d)")
_CPF_MASCARADO = re.compile(r"\*{3}\.\d{3}\.\d{3}-\*{2}")

# o texto fala de uma casa ou de quem mora nela: aí o número do endereço identifica a pessoa. Não contam
# lugar público ("casa de bombas", "Casa do Imigrante", "Casa de Passagem") nem "moradores" no plural,
# que é a comunidade.
_CASA = re.compile(r"\b(casa(?!\s+(?:de\s+bombas|(?-i:d[eoa]s?\s+[A-ZÁÉÍÓÚ])))|resid[eê]ncia|morador|moradora"
                   r"|residente)\b", re.I)
_NUMERO_COM_ROTULO = re.compile(r"\b(?:n[º°;]\.?|nro\.?|n[úu]mero)\s*\d+(?:\.\d{3})*(?![\d/])", re.I)
_CASA_NUMERO = re.compile(r"\b(casa)\s+\d+(?![\d/])", re.I)
# logradouro seguido do número; o nome da rua não tem hífen, então "BR-116" e "RS-240" não casam
_LOGRADOURO_NUMERO = re.compile(
    r"\b((?:Rua|R\.|Avenida|Av\.|Travessa|Tv\.|Estrada|Alameda|Beco|Praça)\s+[^\d,.;:\n-]{1,60}?)(,?\s+)"
    r"(\d+(?:\.\d{3})*)(?![\d/])")


def limpar_pedido(texto: str | None) -> str | None:
    """Texto do pedido como sai no modo público: sem contato de quem pediu nem número da casa de morador."""
    if not texto:
        return texto
    t = _SOLICITANTE.sub(lambda m: f"{m[1]}{m[2]}{NOME_OMITIDO}", texto)
    t = _CONTATO.sub(lambda m: f"{m[1]}: {CONTATO_OMITIDO}", t)
    t = _CPF_MASCARADO.sub(CONTATO_OMITIDO, sem_cpf(t))
    t = _TELEFONE.sub(CONTATO_OMITIDO, t)
    if _CASA.search(t):
        t = _NUMERO_COM_ROTULO.sub(NUMERO_OMITIDO, t)
        t = _CASA_NUMERO.sub(lambda m: f"{m[1]} {NUMERO_OMITIDO}", t)
        # de novo até parar: "Rua X 5 (Vila Y) 47" tem dois números para a mesma rua
        for _ in range(3):
            antes, t = t, _LOGRADOURO_NUMERO.sub(lambda m: f"{m[1]}{m[2]}{NUMERO_OMITIDO}", t)
            if t == antes:
                break
    return t


# ===== Conferência do que vai para o site =====
# Última barreira: varre os arquivos exportados atrás do que as regras acima deveriam ter tirado. O
# relatório vai para o log do GitHub, que é público, então mostra só a forma do trecho (dígitos viram #
# e nomes viram iniciais) e uma chave: o sha1 do texto, usada na lista de falsos positivos liberados.

_CPF_INTEIRO = _CPF
_MEI_NOVO = re.compile(r"^\s*\d{2}\.?\d{3}\.?\d{3}\s+[^\d\s]")
_ROTULO_CONTATO = re.compile(r"\b(solicitante|requerente|contato|telefone|fone|celular|whatsapp)\s*:(?!\s*\[)", re.I)
_NUMERO_DE_CASA = (_NUMERO_COM_ROTULO, _CASA_NUMERO, _LOGRADOURO_NUMERO)


@dataclass(frozen=True)
class Achado:
    arquivo: str
    caminho: str
    regra: str
    trecho: str
    chave: str


def _forma(texto: str, ini: int, fim: int) -> str:
    """O trecho em volta do achado sem o dado: dígitos viram # e palavras com maiúscula, iniciais."""
    pedaço = texto[max(0, ini - 40): fim + 40]
    pedaço = re.sub(r"\d", "#", pedaço)
    return re.sub(r"\b([A-ZÀ-Ú])[A-Za-zÀ-ú]+", r"\1.", pedaço)


def _regras(texto: str, caminho: str):
    m = _CPF_INTEIRO.search(texto)
    if m:
        yield "CPF inteiro", m
    m = _CPF_MASCARADO.search(texto)
    if m:
        yield "CPF mascarado", m
    m = _MEI_NOVO.search(texto)
    if m:
        yield "MEI com o nome do dono", m
    m = _ROTULO_CONTATO.search(texto)
    if m:
        yield "contato de quem pediu", m
    m = _TELEFONE.search(texto)
    if m:
        yield "telefone", m
    # casa de morador só no texto do pedido, que é onde a limpeza atua; no objeto de contrato de empresa,
    # "a casa a ser locada" é um prédio alugado para serviço público
    if caminho.endswith("ementa") and _CASA.search(texto):
        for rx in _NUMERO_DE_CASA:
            m = rx.search(texto)
            if m:
                yield "número da casa de morador", m
                break


def _textos(dado, caminho: str = ""):
    if isinstance(dado, str):
        yield caminho, dado
    elif isinstance(dado, dict):
        for k, v in dado.items():
            yield from _textos(v, f"{caminho}.{k}" if caminho else k)
    elif isinstance(dado, list):
        for i, v in enumerate(dado):
            yield from _textos(v, f"{caminho}[{i}]")


def _linhas_parquet(arq: Path):
    """Cada texto de um Parquet, com o caminho "[linha].coluna" (como no JSON)."""
    import duckdb

    con = duckdb.connect()
    try:
        cur = con.execute("select * from read_parquet(?)", [str(arq)])
        colunas = [c[0] for c in cur.description]
        for i, linha in enumerate(cur.fetchall()):
            for coluna, valor in zip(colunas, linha, strict=True):
                if isinstance(valor, str):
                    yield f"[{i}].{coluna}", valor
    finally:
        con.close()


def conferir(pasta: Path, liberados: set[str] | frozenset[str] = frozenset()) -> list[Achado]:
    """Tudo o que parece dado sensível nos JSON e Parquet da pasta, menos o que foi liberado pela chave."""
    achados = []
    arquivos = sorted([*pasta.rglob("*.json"), *pasta.rglob("*.parquet")])
    for arq in arquivos:
        nome = arq.relative_to(pasta).as_posix()
        textos = (_linhas_parquet(arq) if arq.suffix == ".parquet"
                  else _textos(json.loads(arq.read_text(encoding="utf-8"))))
        for caminho, texto in textos:
            chave = hashlib.sha1(texto.encode("utf-8")).hexdigest()[:12]
            if chave in liberados:
                continue
            for regra, m in _regras(texto, caminho):
                achados.append(Achado(nome, caminho, regra, _forma(texto, m.start(), m.end()), chave))
    return achados


def ler_liberados(arquivo: Path) -> set[str]:
    """Chaves aprovadas como falso positivo (config/sensivel-liberados.yaml)."""
    if not arquivo.exists():
        return set()
    dado = yaml.safe_load(arquivo.read_text(encoding="utf-8")) or {}
    return {str(item["chave"]) for item in dado.get("liberados") or []}
