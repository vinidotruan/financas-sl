"""O conteúdo que a API serve e que a exportação estática grava.

Um lugar só para as consultas e para os filtros de privacidade: num mesmo modo, a API e os
arquivos JSON devolvem exatamente o mesmo conteúdo. Tudo sai em tipos de JSON (datas em ISO).

Privacidade, em qualquer modo: CPF nunca inteiro (sem_cpf percorre a resposta toda) e o
fornecedor é identificado por um id curto, nunca pelo CPF. No modo público: só sinais com status
confirmado ou encaminhado, sem a nota de revisão, e pessoa física (inclui MEI e empresário
individual) aparece como "pessoa física", sem ficha própria.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from decimal import Decimal

PUBLICOS = ("confirmado", "encaminhado")
STATUS = ("novo", "em análise", "descartado", "confirmado", "encaminhado")
SEVERIDADE = {"alto": 0, "atencao": 1, "baixo": 2}
LINKS = {
    "transferegov": "https://api.transferegov.gestao.gov.br/transferenciasespeciais/",
    "siconfi": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
    "pncp": "https://pncp.gov.br/app/contratos",
    "congresso": "https://dadosabertos.camara.leg.br/",
}
PESSOA_FISICA = "pessoa física"

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


def _valor(v):
    if isinstance(v, (date, datetime)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    return v


def _link(fonte: str) -> str | None:
    if fonte == "camara":
        from .config import ente

        return (ente().get("camara") or {}).get("site")
    return LINKS.get(fonte)


def _json(v):
    return json.loads(v) if isinstance(v, str) else v


class Consulta:
    """Consultas sobre um banco aberto, num modo ("privado" ou "publico"), com a revisão aplicada."""

    def __init__(self, con, modo: str, revisao: dict | None = None):
        self.con = con
        self.modo = modo
        self.revisao = revisao or {}

    @property
    def publico(self) -> bool:
        return self.modo == "publico"

    # ===== apoio =====

    def _q(self, sql: str, params: list | None = None) -> list[dict]:
        cur = self.con.execute(sql, params or [])
        cols = [c[0] for c in cur.description]
        return [{c: _valor(v) for c, v in zip(cols, linha, strict=True)} for linha in cur.fetchall()]

    def _fontes(self, nomes) -> list[dict]:
        linhas = {f["fonte"]: f for f in self._q("select * from core.fonte")}
        return [{"nome": n, "link": _link(n), "coletado_em": linhas.get(n, {}).get("coletado_em")}
                for n in nomes]

    def _preparar(self, s: dict) -> dict:
        """Revisão feita na tela (vale na hora), evidência como objeto e filtros do modo público."""
        rev = self.revisao.get(s["id"])
        if rev:
            s["status"], s["nota"] = rev.get("status", s["status"]), rev.get("nota")
        s["evidencia"] = _json(s.get("evidencia")) or {}
        if self.publico:
            s["nota"] = None
            ev = s["evidencia"]
            if ev.get("pessoa_fisica") or ev.get("tipo_pessoa") == "PF":
                ev["fornecedor"] = PESSOA_FISICA
                s["titulo"] = "Pessoa física · " + s["titulo"].split(" · ", 1)[-1]
        return s

    def _visivel(self, s: dict) -> bool:
        return not self.publico or s["status"] in PUBLICOS

    def _ocorrencias(self, onde: str = "true", params: list | None = None, ativos: bool = True) -> list[dict]:
        linhas = self._q(f"""select o.id, o.regra_id, r.nome, r.area, r.severidade, o.chave, o.titulo,
                                o.valor_observado, o.quando, o.primeira_vez, o.ultima_vez, o.ativo, o.status,
                                o.nota, o.evidencia
                             from sinais.ocorrencia o join sinais.regra r on r.id = o.regra_id
                             where (o.ativo or not ?) and ({onde})""", [ativos, *(params or [])])
        linhas = [s for s in (self._preparar(s) for s in linhas) if self._visivel(s)]
        linhas.sort(key=lambda s: s["primeira_vez"] or "", reverse=True)
        linhas.sort(key=lambda s: (SEVERIDADE.get(s["severidade"], 9), s["status"] != "novo"))
        return linhas

    def _fornecedor_publico(self, f: dict) -> dict:
        """Linha de fornecedor como a tela recebe: no modo público, pessoa física sem nome nem id."""
        if self.publico and f.get("pessoa_fisica"):
            f.update(nome=PESSOA_FISICA, ni=None, id=None)
        return f

    # ===== rotas =====

    def fontes(self) -> dict:
        from .config import ente

        cfg = ente()
        return sem_cpf({"modo": self.modo,
                        "ente": {"nome": cfg.get("nome") or "a cidade", "uf": cfg.get("uf"), "ibge": cfg.get("ibge")},
                        "fontes": [{**f, "link": _link(f["fonte"])}
                                   for f in self._q("select * from core.fonte order by fonte")],
                        "erros_de_regra": self._q("select * from sinais.erro")})

    def regras(self) -> list[dict]:
        regras = self._q("select * exclude (sql) from sinais.regra order by id")
        contagem: dict[str, dict] = {}
        for s in self._ocorrencias():
            c = contagem.setdefault(s["regra_id"], {"ativos": 0, "novos": 0})
            c["ativos"] += 1
            c["novos"] += s["status"] == "novo"
        for r in regras:
            r["observado"] = _json(r.get("observado"))
            r["fontes"] = self._fontes(r["fontes"] or [])
            r.update(contagem.get(r["id"], {"ativos": 0, "novos": 0}))
        regras.sort(key=lambda r: (r["ativos"] == 0, SEVERIDADE.get(r["severidade"], 9), r["id"]))
        return sem_cpf(regras)

    def sinais(self, area: str | None = None, severidade: str | None = None, status: str | None = None,
               ativos: bool = True) -> list[dict]:
        filtros, params = [], []
        for campo, valor in (("r.area", area), ("r.severidade", severidade)):
            if valor:
                filtros.append(f"{campo} = ?")
                params.append(valor)
        linhas = self._ocorrencias(" and ".join(filtros) or "true", params, ativos=ativos)
        # status filtrado depois da revisão: um sinal revisado depois da última atualização já vale aqui
        if status:
            linhas = [s for s in linhas if s["status"] == status]
        return sem_cpf(linhas)

    def sinal(self, oid: str) -> dict | None:
        linhas = self._q("""select o.*, r.nome, r.area, r.severidade, r.base_legal, r.limiar, r.pode_ser_normal_se,
                               r.como_verificar, r.fontes, r.observado, r.resumo
                            from sinais.ocorrencia o join sinais.regra r on r.id = o.regra_id where o.id = ?""",
                         [oid])
        if not linhas:
            return None
        s = self._preparar(linhas[0])
        if not self._visivel(s):
            return None
        s["observado"] = _json(s.get("observado"))
        s["fontes"] = self._fontes(s["fontes"] or [])
        s["ligacoes"] = self._ligacoes(s)
        return sem_cpf(s)

    def _ligacoes(self, s: dict) -> dict:
        """Para onde o sinal leva: a emenda (rastro) ou os contratos e fornecedores."""
        lig: dict = {}
        if s["area"] == "emendas":
            lig["emenda"] = s["chave"].split("/")[0]
        contratos = self._q("""select c.id, c.objeto, c.valor_global, f.id as fornecedor_id, c.fornecedor_nome,
                                  c.pessoa_fisica
                               from core.contrato c left join core.fornecedor f on f.ni = c.fornecedor_ni
                               where c.id = ? or c.compra_id = ? order by c.valor_global desc""",
                            [s["chave"], s["chave"]])
        if contratos:
            for c in contratos:
                if self.publico and c["pessoa_fisica"]:
                    c.update(fornecedor_id=None, fornecedor_nome=PESSOA_FISICA)
            lig["contratos"] = contratos
        return lig

    def emendas(self) -> list[dict]:
        return sem_cpf(self._q("""select codigo_emenda, any_value(codigo_formatado) as codigo,
                                     any_value(parlamentar) as parlamentar, any_value(cargo_parlamentar) as cargo,
                                     any_value(codigo_autor) as codigo_autor, min(ano) as ano, count(*) as planos,
                                     round(sum(valor_indicado), 2) as indicado,
                                     round(sum(transferido), 2) as transferido,
                                     round(sum(executado_relatorio), 2) as executado_relatorio
                                  from core.rastro_plano group by codigo_emenda
                                  order by ano desc, transferido desc, codigo_emenda"""))

    def rastro(self, codigo: str) -> dict | None:
        codigo = "".join(ch for ch in codigo if ch.isdigit())
        planos = self._q("select * from core.rastro_plano where codigo_emenda = ? order by id_plano_acao", [codigo])
        if not planos:
            return None
        ids = [p["id_plano_acao"] for p in planos]
        marcadores = ",".join("?" * len(ids))
        executados = [p["executado_relatorio"] for p in planos if p["executado_relatorio"] is not None]
        indicado = round(sum(p["valor_indicado"] for p in planos), 2)
        transferido = round(sum(p["transferido"] for p in planos), 2)
        return sem_cpf({
            "codigo": codigo,
            "codigo_formatado": planos[0]["codigo_formatado"],
            "parlamentar": {"codigo": planos[0]["codigo_autor"], "nome": planos[0]["parlamentar"],
                            "cargo": planos[0]["cargo_parlamentar"]},
            "ano": min(p["ano"] for p in planos),
            # o valor de cada fonte lado a lado; o portal da prefeitura entra na fase 2
            "valores": [
                {"etapa": "Indicado", "fonte": "transferegov", "valor": indicado},
                {"etapa": "Transferido", "fonte": "transferegov", "valor": transferido},
                {"etapa": "Executado (relatório de gestão)", "fonte": "transferegov",
                 "valor": round(sum(executados), 2) if executados else None,
                 "nota": None if executados else "nenhum relatório de gestão entregue"},
                {"etapa": "Empenhado", "fonte": "prefeitura", "valor": None, "nota": "portal da prefeitura, fase 2"},
                {"etapa": "Pago", "fonte": "prefeitura", "valor": None, "nota": "portal da prefeitura, fase 2"},
            ],
            "planos": planos,
            "transferencias": self._q(f"select * from core.transferencia where id_plano_acao in ({marcadores}) "
                                      "order by data_ob", ids),
            "metas": self._q(f"select * from core.meta where id_plano_acao in ({marcadores}) "
                             "order by id_plano_acao, nome_meta", ids),
            "sinais": self._ocorrencias("o.chave like ?", [codigo + "/%"]),
            "fontes": self._fontes(["transferegov"]),
        })

    def parlamentares(self) -> list[dict]:
        return sem_cpf(self._q("""select r.codigo_autor as codigo, any_value(r.parlamentar) as nome,
                                     any_value(p.cargo) as cargo, any_value(p.uf) as uf, any_value(p.link) as link,
                                     count(distinct r.codigo_emenda) as emendas, count(*) as planos,
                                     round(sum(r.valor_indicado), 2) as indicado,
                                     round(sum(r.transferido), 2) as transferido,
                                     min(r.ano) as primeiro_ano, max(r.ano) as ultimo_ano
                                  from core.rastro_plano r left join core.parlamentar p using (codigo_autor)
                                  group by r.codigo_autor order by indicado desc"""))

    def parlamentar(self, codigo: str) -> dict | None:
        linhas = [p for p in self.parlamentares() if str(p["codigo"]) == str(codigo)]
        if not linhas:
            return None
        emendas = [e for e in self.emendas() if str(e["codigo_autor"]) == str(codigo)]
        codigos = [e["codigo_emenda"] for e in emendas]
        sinais = (self._ocorrencias(" or ".join(["o.chave like ?"] * len(codigos)), [c + "/%" for c in codigos])
                  if codigos else [])
        return sem_cpf({**linhas[0], "emendas_lista": emendas, "sinais": sinais,
                        "fontes": self._fontes(["transferegov", "congresso"])})

    def fornecedores(self, limite: int | None = None) -> list[dict]:
        sql = "select * from core.fornecedor order by valor_total desc"
        linhas = self._q(sql + (" limit ?" if limite else ""), [limite] if limite else [])
        for f in linhas:
            f["pct_direto"] = f["valor_direto"] / f["valor_total"] if f["valor_total"] else None
        return sem_cpf([self._fornecedor_publico(f) for f in linhas])

    def fornecedor(self, fid: str) -> dict | None:
        linhas = self._q("select * from core.fornecedor where id = ?", [fid])
        if not linhas or (self.publico and linhas[0]["pessoa_fisica"]):
            return None
        f = linhas[0]
        f["pct_direto"] = f["valor_direto"] / f["valor_total"] if f["valor_total"] else None
        contratos = self._q("""select id, compra_id, orgao_nome, unidade, ano, objeto, categoria, modalidade, amparo,
                                  contratacao_direta, emergencial, valor_inicial, valor_global, data_assinatura,
                                  vigencia_fim
                               from core.contrato where fornecedor_ni = ? order by data_assinatura desc""",
                            [f["ni"]])
        chaves = [c["id"] for c in contratos] + [c["compra_id"] for c in contratos if c["compra_id"]]
        sinais = self._ocorrencias(f"o.chave in ({','.join('?' * len(chaves))})", chaves) if chaves else []
        return sem_cpf({**f, "contratos_lista": contratos, "sinais": sinais, "fontes": self._fontes(["pncp"])})

    def contratos(self, q: str | None = None, limite: int = 50) -> list[dict]:
        if q and self.publico:
            # no modo público a busca é só pelo objeto: buscar pelo nome ou CPF confirmaria quem é a pessoa física
            linhas = self._q("select * from core.contrato where objeto ilike ? order by valor_global desc limit ?",
                             [f"%{q}%", limite])
        elif q:
            linhas = self._q("""select * from core.contrato
                                where objeto ilike ? or fornecedor_nome ilike ? or fornecedor_ni = ?
                                order by valor_global desc limit ?""", [f"%{q}%", f"%{q}%", q, limite])
        else:
            linhas = self._q("select * from core.contrato order by valor_global desc limit ?", [limite])
        if self.publico:
            for c in linhas:
                if c["pessoa_fisica"]:
                    c["fornecedor_nome"], c["fornecedor_ni"] = PESSOA_FISICA, None
        return sem_cpf(linhas)

    def pedidos(self) -> dict:
        """Pedidos dos vereadores à prefeitura (pedidos de providência e indicações), contados por
        vereador, bairro, tema e ano. A tela soma conforme o filtro. Pedido em coautoria conta para
        cada vereador que assina; pedido com dois bairros conta nos dois."""
        return sem_cpf({
            "total": self._q("select count(*) as n from core.pedido")[0]["n"],
            "temas": [t["tema"] for t in self._q("select tema from core.tema order by ordem")],
            "anos": [a["ano"] for a in self._q("select distinct ano from core.pedido order by ano desc")],
            "por_tema": self._q("select ano, tema, count(*) as pedidos from core.pedido group by all order by all"),
            "por_vereador": self._q("""select v.id, v.nome, v.partido, v.cargo, p.ano, p.tema, count(*) as pedidos
                                       from core.pedido p
                                       join core.pedido_autor a on a.id_pedido = p.id
                                       join core.vereador v on v.id = a.id_vereador
                                       group by all order by all"""),
            "por_bairro": self._q("""select b.id, b.nome, p.ano, p.tema, count(*) as pedidos
                                     from core.pedido p
                                     join core.pedido_bairro pb on pb.id_pedido = p.id
                                     join core.bairro b on b.id = pb.id_bairro
                                     group by all order by all"""),
            "sem_bairro": self._q("""select ano, tema, count(*) as pedidos from core.pedido
                                     where id not in (select id_pedido from core.pedido_bairro)
                                     group by all order by all"""),
            "fontes": self._fontes(["camara"]),
        })

    def vereador(self, vid: str) -> dict | None:
        linhas = self._q("select * from core.vereador where cast(id as varchar) = ?", [str(vid)])
        if not linhas:
            return None
        pedidos = self._q("""select p.id, p.ano, p.numero, p.especie, p.ementa, p.url, p.tema,
                                string_agg(distinct b.nome, ', ' order by b.nome) as bairros
                             from core.pedido p
                             join core.pedido_autor a on a.id_pedido = p.id
                             left join core.pedido_bairro pb on pb.id_pedido = p.id
                             left join core.bairro b on b.id = pb.id_bairro
                             where a.id_vereador = ?
                             group by p.id, p.ano, p.numero, p.especie, p.ementa, p.url, p.tema
                             order by p.ano desc, p.numero desc""", [linhas[0]["id"]])
        return sem_cpf({**linhas[0], "pedidos": pedidos, "fontes": self._fontes(["camara"])})

    def contas(self) -> dict:
        return sem_cpf({
            "limite_pessoal": self._q("select * from core.limite_pessoal order by exercicio desc, periodo desc"),
            "resultado_anual": self._q("select * from core.resultado_anual order by exercicio desc"),
            "fontes": self._fontes(["siconfi"]),
        })
