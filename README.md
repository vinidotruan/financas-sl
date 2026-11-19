# Finanças de São Leopoldo

Coleta Transferegov (emendas Pix), SICONFI (RGF e RREO) e PNCP (contratos, compras e aditivos da
prefeitura, das fundações, do SEMAE e da Câmara), monta um banco DuckDB, roda as regras de sinal e
serve um painel pro celular. Sinais são pontos de atenção, não acusações.

    uv sync
    (cd front && npm install && npm run build)   # front em site/ (Node do .nvmrc)
    uv run slf diario        # coleta tudo e monta o banco (a primeira vez leva uns 40 min, por causa do PNCP)
    uv run slf status        # o que foi coletado e quantos sinais
    uv run slf servir        # abre http://localhost:8765 (e mostra o endereço pro celular)
    ./scripts/agendar.sh     # roda "slf diario" todo dia às 06:10

Outros comandos: `slf coletar pncp` (uma fonte só), `slf atualizar` (remonta sem coletar).
Modo público: `SLF_MODO=publico uv run slf servir` esconde pessoa física (inclusive MEI), esconde as
notas e mostra só sinais confirmados ou encaminhados.

Front: `cd front && npm run dev` abre em http://localhost:5173 usando a API do `slf servir`.
`npm run build:estatico` gera a versão que lê os arquivos JSON de `site/data/` em vez da API.

Testes: `uv run pytest` (sem rede, com fixtures no formato real das APIs) e `uv run ruff check`.

Pastas: `data/raw` guarda tudo como veio (com manifest e sha256), `data/slf.duckdb` é o banco,
`data/revisao.json` guarda seus status e notas. Regras em `slf/regras/*.yaml`. O conteúdo da API sai
de `slf/consultas.py`, que concentra os filtros de privacidade.
