"""Linha de comando: slf coletar | atualizar | diario | servir | status"""
from __future__ import annotations

import argparse
import socket
import sys
import traceback

COLETORES = ("transferegov", "siconfi", "pncp")


def coletar(fontes) -> list[str]:
    from .coletores import pncp, siconfi, transferegov
    mods = {"transferegov": transferegov, "siconfi": siconfi, "pncp": pncp}
    falhas = []
    for nome in fontes:
        print(f"Coletando {nome}…")
        try:
            mods[nome].coletar()
        except Exception as e:  # uma fonte falhar não para as outras
            falhas.append(nome)
            print(f"  {nome} falhou: {e}")
            traceback.print_exc(limit=2)
    return falhas


def _ip_local() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "IP-do-Mac"


def main(argv=None):
    p = argparse.ArgumentParser(prog="slf", description="Finanças de São Leopoldo")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coletar", help="baixa os dados das fontes")
    c.add_argument("fontes", nargs="*", help="transferegov, siconfi, pncp (padrão: todas)")
    a = sub.add_parser("atualizar", help="monta o banco e roda as regras de sinal")
    a.add_argument("--forcar", action="store_true", help="troca o banco mesmo com teste falhando")
    sub.add_parser("diario", help="coletar tudo e atualizar (o que o agendamento roda)")
    s = sub.add_parser("servir", help="sobe a API e a tela pro celular")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--porta", type=int, default=8765)
    sub.add_parser("status", help="mostra a última coleta de cada fonte e os sinais")
    args = p.parse_args(argv)

    if args.cmd == "coletar":
        invalidas = set(args.fontes) - set(COLETORES)
        if invalidas:
            p.error(f"fonte desconhecida: {', '.join(invalidas)}")
        falhas = coletar(args.fontes or COLETORES)
        sys.exit(1 if falhas else 0)
    if args.cmd == "atualizar":
        from .processar import atualizar
        atualizar(forcar=args.forcar)
    if args.cmd == "diario":
        falhas = coletar(COLETORES)
        from .processar import atualizar
        atualizar()
        if falhas:
            print("Fontes com falha (usadas da coleta anterior):", ", ".join(falhas))
    if args.cmd == "servir":
        import uvicorn
        print(f"No Mac: http://localhost:{args.porta}")
        print(f"No celular, na mesma rede: http://{_ip_local()}:{args.porta}")
        uvicorn.run("slf.api:app", host=args.host, port=args.porta)
    if args.cmd == "status":
        import duckdb

        from .config import DB
        if not DB.exists():
            print("Banco ainda não existe. Rode: slf diario")
            return
        con = duckdb.connect(str(DB), read_only=True)
        for f in con.execute("select fonte, coletado_em, linhas from core.fonte order by 1").fetchall():
            print(f"{f[0]:<14} última coleta boa: {f[1] or 'nunca'}  ({f[2]} linhas)")
        print()
        for r in con.execute("""select r.id, r.nome, count(*) filter (where o.ativo),
                                       count(*) filter (where o.ativo and o.status = 'novo')
                                from sinais.regra r left join sinais.ocorrencia o on o.regra_id = r.id
                                group by 1, 2 order by 1""").fetchall():
            print(f"{r[0]}  {r[1]:<40} {r[2]:>4} ativos  {r[3]:>4} novos")
        for e in con.execute("select * from sinais.erro").fetchall():
            print(f"Regra {e[0]} falhou: {e[1]}")


if __name__ == "__main__":
    main()
