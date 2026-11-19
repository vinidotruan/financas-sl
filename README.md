# Finanças de São Leopoldo · fase 1

Coleta Transferegov (emendas Pix), SICONFI (RGF e RREO) e PNCP (contratos, compras e aditivos),
monta um banco DuckDB, roda as regras de sinal e serve uma tela pro celular.

    uv sync
    uv run slf diario        # coleta tudo e monta o banco (a primeira vez leva uns 10 a 20 min)
    uv run slf status        # o que foi coletado e quantos sinais
    uv run slf servir        # abre http://localhost:8765 (e mostra o endereço pro celular)
    ./scripts/agendar.sh     # roda "slf diario" todo dia às 06:10

Outros comandos: `slf coletar pncp` (uma fonte só), `slf atualizar` (remonta sem coletar).
Modo público: `SLF_MODO=publico uv run slf servir` esconde pessoa física e mostra só sinais revisados.

Pastas: `data/raw` guarda tudo como veio (com manifest e sha256), `data/slf.duckdb` é o banco,
`data/revisao.json` guarda seus status e notas. Regras em `slf/regras/*.yaml`.
Antes de rodar, adicione em `config/ente.yaml` os CNPJs das fundações e autarquias do município.
