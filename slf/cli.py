"""Linha de comando: slf coletar | atualizar | diario | servir | status"""
from __future__ import annotations

import argparse
import socket
import sys
import traceback

COLETORES = ("transferegov", "siconfi", "pncp", "camara")


def coletar(fontes) -> list[str]:
    from .coletores import camara, pncp, siconfi, transferegov
    mods = {"transferegov": transferegov, "siconfi": siconfi, "pncp": pncp, "camara": camara}
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
    p = argparse.ArgumentParser(prog="slf", description="Finanças municipais: coleta, sinais e painel")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("coletar", help="baixa os dados das fontes")
    c.add_argument("fontes", nargs="*", help="transferegov, siconfi, pncp, camara (padrão: todas)")
    a = sub.add_parser("atualizar", help="monta o banco e roda as regras de sinal")
    a.add_argument("--forcar", action="store_true", help="troca o banco mesmo com teste falhando")
    sub.add_parser("diario", help="coletar tudo e atualizar (o que o agendamento roda)")
    s = sub.add_parser("servir", help="sobe a API e a tela pro celular")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--porta", type=int, default=8765)
    sub.add_parser("status", help="mostra a última coleta de cada fonte e os sinais")
    e = sub.add_parser("exportar", help="grava um JSON por rota da API, para o site estático")
    e.add_argument("--modo", choices=("publico", "privado"), default="publico",
                   help="publico (padrão): o que pode ir para a internet")
    e.add_argument("--saida", default="site/data", help="pasta de saída (padrão: site/data)")
    po = sub.add_parser("podar", help="apaga coletas antigas de data/raw, mantendo as N últimas boas de cada fonte")
    po.add_argument("--manter", type=int, default=3)
    r = sub.add_parser("revisao-publica", help="gera config/revisao-publica.json (sem notas) para publicar")
    r.add_argument("--saida", default="config/revisao-publica.json")
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
    if args.cmd == "exportar":
        from pathlib import Path

        from .exportar import exportar
        contagem = exportar(Path(args.saida), args.modo)
        print(f"Exportado em {args.saida} (modo {args.modo}): "
              + ", ".join(f"{k} {v}" for k, v in sorted(contagem.items())))
    if args.cmd == "podar":
        from .raw import podar
        removidas = podar(args.manter)
        print(f"{len(removidas)} coletas antigas apagadas de data/raw "
              f"(mantidas as {args.manter} últimas boas por fonte)")
    if args.cmd == "revisao-publica":
        from pathlib import Path

        from .config import DATA
        from .exportar import revisao_publica
        n = revisao_publica(DATA / "revisao.json", Path(args.saida))
        print(f"{args.saida}: {n} sinais confirmados ou encaminhados (sem notas)")
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
