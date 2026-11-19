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

import re

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


# ===== Texto do pedido =====

# "Solicitante: Fulana Exemplo." / "SOLICITANTE: FULANA EXEMPLO- CONTATO: …": o nome vai até o fim da frase
_SOLICITANTE = re.compile(r"\b(solicitante|requerente)(\s*:\s*)[^.;\n–-]+", re.I)
# "Contato: (51) 99999-1234." / "CONTATO:***.456.789-** - BAIRRO": o valor vai até o fim da frase ou um " - "
_CONTATO = re.compile(r"\b(contato|telefone|fone|celular|whatsapp)\s*:\s*.*?(?=\s+-\s|[.;](?:\s|$)|$)", re.I)
# celular com 9 na frente, ou qualquer número com DDD entre parênteses; protocolo e ano não casam
_TELEFONE = re.compile(r"\(\d{2}\)\s?9?\d{4}-?\d{4}(?!\d)|(?<![\d/.-])9\d{4}-\d{4}(?!\d)")
_CPF_MASCARADO = re.compile(r"\*{3}\.\d{3}\.\d{3}-\*{2}")

# o texto fala de uma casa ou de quem mora nela: aí o número do endereço identifica a pessoa. Não contam
# lugar público ("casa de bombas", "Casa do Imigrante") nem "moradores" no plural, que é a comunidade.
_CASA = re.compile(r"\b(casa(?!\s+(?:de\s+bombas|(?-i:d[oa]s?\s+[A-ZÁÉÍÓÚ])))|resid[eê]ncia|morador|moradora"
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
        t = _LOGRADOURO_NUMERO.sub(lambda m: f"{m[1]}{m[2]}{NUMERO_OMITIDO}", t)
    return t
