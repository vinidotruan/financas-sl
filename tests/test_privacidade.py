"""A máscara de CPF: o que ela tem que pegar e o que ela não pode estragar."""
import pytest

from slf.consultas import sem_cpf


@pytest.mark.parametrize("texto, esperado", [
    ("12345678901", "***.456.789-**"),
    ("FULANO DE TAL 12345678901", "FULANO DE TAL ***.456.789-**"),     # MEI: CPF no fim da razão social
    ("CPF: 123.456.789-01", "CPF: ***.456.789-**"),                     # já pontuado
    ("cpf 12345678901, matrícula 55386", "cpf ***.456.789-**, matrícula 55386"),
])
def test_mascara_cpf(texto, esperado):
    assert sem_cpf(texto) == esperado


@pytest.mark.parametrize("texto", [
    "db68cc6dc89673977497c954df59fce0",   # id de sinal (md5): dígitos colados em letras
    "202642710013",                       # código da emenda, 12 dígitos
    "89814693000160",                     # CNPJ, 14 dígitos
    "89.814.693/0001-60",                 # CNPJ pontuado
    "89814693000160-2-000002/2024",       # número de controle do PNCP
    "R$ 123.456.789,01",                  # valor em reais
    "2026-11-18T22:12:02",
])
def test_nao_mexe_no_que_nao_e_cpf(texto):
    assert sem_cpf(texto) == texto


def test_percorre_a_estrutura_inteira():
    dado = {"a": ["x 12345678901"], "b": {"c": "98765432100"}, "n": 12345678901}
    assert sem_cpf(dado) == {"a": ["x ***.456.789-**"], "b": {"c": "***.654.321-**"}, "n": 12345678901}
