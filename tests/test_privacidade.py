"""Dados sensíveis: a máscara de CPF e a limpeza do texto dos pedidos, o que pegam e o que não podem estragar."""
import json

import pytest

from slf.sensivel import conferir, limpar_pedido, sem_cpf


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


# ===== Texto do pedido no modo público =====

@pytest.mark.parametrize("texto, esperado", [
    # contato de quem pediu: nome, telefone e CPF (mesmo mascarado) saem
    ("Conserto. Solicitante: Fulana Exemplo. Contato: (51) 99999-1234.",
     "Conserto. Solicitante: [nome omitido]. Contato: [contato omitido]."),
    ("LIMPEZA- SOLICITANTE: FULANA EXEMPLO- CONTATO:***.456.789-** - BAIRRO CENTRO",
     "LIMPEZA- SOLICITANTE: [nome omitido]- CONTATO: [contato omitido] - BAIRRO CENTRO"),
    ("ligar para 99999-1234 ou (51) 3590-1234", "ligar para [contato omitido] ou [contato omitido]"),
    ("pede retorno ao CPF 123.456.789-01", "pede retorno ao CPF [contato omitido]"),
    # casa de morador: a rua fica, o número sai
    ("em frente da casa da moradora do endereço Rua das Flores 123, bairro Centro",
     "em frente da casa da moradora do endereço Rua das Flores [nº omitido], bairro Centro"),
    ("na Rua Exemplo, número 855, Bairro Santa Teresa. Morador relata que a calçada cedeu.",
     "na Rua Exemplo, [nº omitido], Bairro Santa Teresa. Morador relata que a calçada cedeu."),
    ("Av. Feitoria, 2.231, em frente à residência", "Av. Feitoria, [nº omitido], em frente à residência"),
    ("Rua Exemplo, quadra 46, casa 8, Cohab", "Rua Exemplo, quadra 46, casa [nº omitido], Cohab"),
    ("na Rua Projetada 5 (Santo Augusto) 47, em frente à casa",
     "na Rua Projetada [nº omitido] (Santo Augusto) [nº omitido], em frente à casa"),
    # o protocolo e a rodovia ficam, mesmo quando o texto fala de casa
    ("protocolo nº 2025/10642, na Rua A com a BR-116, em frente à casa nº 12",
     "protocolo nº 2025/10642, na Rua A com a BR-116, em frente à casa [nº omitido]"),
])
def test_limpa_o_pedido(texto, esperado):
    assert limpar_pedido(texto) == esperado


@pytest.mark.parametrize("texto", [
    # endereço do lugar do serviço, sem casa nem morador: fica, sem ele o pedido não se entende
    "boca de lobo na Rua Medianeira numero 469, no bairro Cristo Rei.",
    "lâmpada com mau contato na Rua A, em frente ao nº 81.",   # "contato" sem dois-pontos não é contato
    "conforme o protocolo de solicitação 2026/2183 e Semae 2025099407.",
    "obras previstas para 2024-2025, Lei 5.123/2010.",
    "Solicita ao Secretário de Obras, Sr. Fulano Exemplo, a poda.",  # autoridade no cargo
    "limpeza da casa de bombas da Rua B, 50.",                      # lugar público
    "reforma da Casa do Imigrante, na Rua C, 10.",
    "imóvel na Rua São Paulo, nº 793, para a Casa de Acolhimento Provisório.",
    "os moradores da Rua D, 300, pedem a capina.",                  # moradores = a comunidade
    "",
])
def test_nao_mexe_no_que_nao_e_sensivel(texto):
    assert limpar_pedido(texto) == texto


def test_pedido_sem_texto():
    assert limpar_pedido(None) is None


# ===== Conferência do que vai para o site =====

def _gravar(pasta, nome, dado):
    (pasta / nome).parent.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(json.dumps(dado, ensure_ascii=False), encoding="utf-8")


def _exemplo(pasta):
    _gravar(pasta, "fornecedores.json", [{"nome": "12.345.678 FULANA EXEMPLO"}, {"nome": "BELTRANA 12345678901"},
                                         {"nome": "CONSTRUTORA EXEMPLO SA"}])
    _gravar(pasta, "vereadores/1.json", {"pedidos": [
        {"ementa": "Contato: (51) 99999-1234."},
        {"ementa": "em frente à casa da moradora, Rua A, 12"},
        {"ementa": "Solicitante: Fulana Exemplo."},
        {"ementa": "Solicitante: [nome omitido]. Contato: [contato omitido]."},
        {"ementa": "boca de lobo na Rua B, número 40"}]})
    # aluguel de prédio para serviço público: a casa é da empresa, não de um morador
    _gravar(pasta, "fornecedores/abc.json", {"contratos_lista": [
        {"objeto": "Locação de imóvel. A casa a ser locada está na Rua C, 331, com 150 m2."}]})


def test_conferir_acha_o_que_nao_pode_ir_ao_ar(tmp_path):
    _exemplo(tmp_path)
    achados = conferir(tmp_path)
    assert {(a.arquivo, a.caminho, a.regra) for a in achados} == {
        ("fornecedores.json", "[0].nome", "MEI com o nome do dono"),
        ("fornecedores.json", "[1].nome", "CPF inteiro"),
        ("vereadores/1.json", "pedidos[0].ementa", "contato de quem pediu"),
        ("vereadores/1.json", "pedidos[0].ementa", "telefone"),
        ("vereadores/1.json", "pedidos[1].ementa", "número da casa de morador"),
        ("vereadores/1.json", "pedidos[2].ementa", "contato de quem pediu"),
    }


def test_relatorio_da_conferencia_nao_espalha_o_dado(tmp_path):
    # o relatório vai para o log do GitHub, que é público
    _exemplo(tmp_path)
    relatorio = json.dumps([a.__dict__ for a in conferir(tmp_path)], ensure_ascii=False)
    for dado in ("12345678901", "99999-1234", "FULANA", "Fulana", "BELTRANA", "12.345.678"):
        assert dado not in relatorio


def test_liberado_pela_chave_nao_volta(tmp_path):
    _exemplo(tmp_path)
    chave = next(a.chave for a in conferir(tmp_path) if a.regra == "número da casa de morador")
    assert not any(a.regra == "número da casa de morador" for a in conferir(tmp_path, liberados={chave}))


def test_exportacao_publica_passa_na_conferencia(banco, tmp_path):
    from slf.exportar import exportar

    exportar(tmp_path / "publico", "publico")
    assert conferir(tmp_path / "publico") == []
    exportar(tmp_path / "privado", "privado")  # o modo privado mostra o nome com CPF mascarado: a conferência pega
    assert {a.regra for a in conferir(tmp_path / "privado")} >= {"CPF mascarado"}


def test_comando_conferir_falha_quando_acha(tmp_path, capsys):
    from slf import cli

    _exemplo(tmp_path)
    with pytest.raises(SystemExit) as saida:
        cli.main(["conferir", "--pasta", str(tmp_path), "--liberados", str(tmp_path / "nao-existe.yaml")])
    assert saida.value.code == 1
    assert "6 trechos parecem dado sensível" in capsys.readouterr().out
    (tmp_path / "liberados.yaml").write_text("liberados: []\n", encoding="utf-8")
    vazia = tmp_path / "vazia"
    vazia.mkdir()
    with pytest.raises(SystemExit) as saida:
        cli.main(["conferir", "--pasta", str(vazia), "--liberados", str(tmp_path / "liberados.yaml")])
    assert saida.value.code == 0
