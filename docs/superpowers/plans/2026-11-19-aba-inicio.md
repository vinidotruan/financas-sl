# Aba Início com gráficos e fonte TCE-RS · plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** uma aba Início, primeira do site, com sete cartões-pergunta, e a fonte TCE-RS (pagamentos por credor) alimentando o cartão "quem mais recebeu" e o pago em Fichas → Fornecedores.

**Architecture:** coletor novo `tce` (zip por órgão e ano no raw, com manifest) → `staging.tce_operacao` → `core.despesa`, `core.credor_ano`, `core.despesa_mes` (pagamento conta no ano da data dele) → `Consulta.inicio()` servida em `/api/inicio` e exportada em `inicio.json` → tela `inicio.tsx` com componentes novos no Storybook. Cada tarefa vai ao ar sozinha pela cadeia coleta → processar → publicar (D42).

**Tech Stack:** Python 3 + uv, httpx, DuckDB 2.0, FastAPI, pytest com `httpx.MockTransport`; Preact 10 + TypeScript + Vite 7; Storybook 10.6.5.

**Spec:** `docs/superpowers/specs/2026-11-19-aba-inicio-design.md` (leia antes; este plano argumenta a partir dela).

## Global Constraints

- Tudo em pt-BR (código, commits, textos); nunca travessão (em dash) em texto entregue.
- Commit: uma linha para mudança pequena, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; push autorizado a cada micro entrega (fluxo de micro entregas do Ruan).
- CPF nunca inteiro, em modo nenhum; pessoa física (inclui MEI nos dois formatos) aparece como "pessoa física", sem nome, CPF nem ficha, no modo público (D40). `uv run slf conferir` tem que passar no export público e no pacote.
- Linguagem neutra: nunca "fraude", "desvio", "corrupção" ou "irregular".
- Raw imutável, manifest com sha256; processamento determinístico: toda ordenação termina num campo único, nada de `any_value` (D43).
- Uma fonte fora do ar não segura as outras.
- Só dado público, sem login; não contornar bloqueio.
- Dependência nova: nenhuma (se for inevitável, versão fixa publicada há mais de duas semanas, D24).
- Front: tokens de `front/src/tokens.css`, dois temas, 360px sem rolagem lateral; componente novo ganha story.
- Verificação de cada tarefa: `uv run ruff check slf tests`, `uv run pytest -q` e, no front, `cd front && nvm use && npx tsc --noEmit && npm run build && npm run build-storybook`.

## Review Focus

1. **Arquivo do TCE-RS que não existe** (órgão sem arquivo naquele ano, 404): a coleta continua boa e registra o ausente; teste na Tarefa 1.
2. **Pagamento de ano anterior dentro do arquivo do ano** (o de 2025 traz R$ 174,9 mi de 2024): conta só no ano da data, sem dobrar; teste na Tarefa 2.
3. **CNPJ e CPF sem zeros à esquerda** (Caixa vem `360305000104`): normalizado para 14 e 11 dígitos, casa com o NI do PNCP; teste na Tarefa 2.
4. **MEI com nome no formato novo vindo como PJ no TCE-RS**: vira pessoa física e não aparece pelo nome; teste na Tarefa 2 e na conferência da Tarefa 3.
5. **Ano corrente sem dezembro**: o cartão usa o último ano com pagamento em dezembro e diz até que dia vai o ano corrente; teste na Tarefa 3.

---

## Fixtures do TCE-RS (usadas nas Tarefas 1 a 5)

Arquivos CSV em `tests/fixtures/tce/{codigo}-{ano}.csv`, UTF-8 com BOM, com o cabeçalho real (as 48 colunas listadas na spec, na ordem do arquivo de verdade: copie de `head -1` de um arquivo baixado) e só as colunas abaixo preenchidas. Valores com ponto decimal.

`58700-2025.csv` (prefeitura):

| tipo_operacao | dt_operacao | tp_pessoa | cnpj_cpf | nm_credor | vl_pagamento |
|---|---|---|---|---|---|
| E | 2025-01-02 | PJ | 11222333000144 | GREEN EXEMPLO REFEICOES LTDA | (vl_empenho 500000.00) |
| P | 2025-03-10 | PJ | 11222333000144 | GREEN EXEMPLO REFEICOES LTDA | 300000.00 |
| P | 2025-12-15 | PJ | 11222333000144 | GREEN EXEMPLO REFEICOES LTDA | 100000.00 |
| P | 2025-05-05 | PJ | 22333444000155 | CONSTRUTORA EXEMPLO SA | 250000.00 |
| P | 2025-10-01 | PJ | 22333444000155 | CONSTRUTORA EXEMPLO SA | -50000.00 |
| P | 2025-06-01 | PJ | 360305000104 | CAIXA ECONOMICA FEDERAL | 500000.00 |
| P | 2025-07-01 | PJ | 93850972000156 | INSTITUTO APOSENT PENSOES SERVIDORES MUNICIPAIS DE SL | 800000.00 |
| P | 2025-08-01 | PF | 4567890123 | FULANA EXEMPLO | 5000.00 |
| P | 2025-09-01 | PJ | 12345678000190 | 12.345.678 JOANA EXEMPLO | 20000.00 |
| P | 2024-11-20 | PJ | 11222333000144 | GREEN EXEMPLO REFEICOES LTDA | 999999.00 |

`58700-2024.csv`: P 2024-11-20 Green 999999.00; P 2024-12-10 Construtora 10000.00.
`58700-2026.csv`: P 2026-01-15 Green 70000.00; P 2026-02-20 Construtora 30000.00 (sem dezembro).
`58701-2025.csv` (Câmara): P 2025-04-01 PJ 55555555000155 PAPELARIA EXEMPLO LTDA 1000.00.
SEMAE (58702): sem arquivo (404).

`cd_orgao`/`nome_orgao` preenchidos com o código e nome do arquivo; `nr_empenho` e `nr_pagamento` com números distintos por linha.

---

### Tarefa 1: Coletor do TCE-RS e a prova de acesso no GitHub Actions

**Files:**
- Create: `slf/coletores/tce.py`, `tests/fixtures/tce/*.csv` (tabela acima), `tests/test_tce.py`
- Modify: `slf/cli.py` (registrar `tce` em `COLETORES` e no `coletar`), `config/ente.yaml` (bloco `tce_rs`), `tests/conftest.py` (ente de teste com `tce_rs`, rota do host `dados.tce.rs.gov.br`, contador de pedidos), `slf/consultas.py` (`LINKS["tce"]`), `front/src/telas/fontes.tsx` (texto da fonte), `docs/replicar.md` (linha da tabela), `CLAUDE.md` (coletores)

**Interfaces:**
- Produces: `slf.coletores.tce.coletar() -> Coleta`; arquivos na coleta: `empenhos/{codigo}-{ano}.csv.zip` (bytes exatos do TCE-RS, via `Coleta.salvar_arquivo`) e `ausentes.json` (lista `{"orgao": int, "ano": int}`); `URL = "https://dados.tce.rs.gov.br/dados/municipal/empenhos/{ano}/{codigo}.csv.zip"`.
- Config: `ente()["tce_rs"]["orgaos"]` = lista de `{codigo: int, nome: str}`; no real, 58700 Prefeitura Municipal de São Leopoldo, 58701 Câmara Municipal, 58702 SEMAE, 58704 Fundação Hospital Centenário. No teste: 58700, 58701, 58702.

- [ ] **Step 1: Testes que falham** em `tests/test_tce.py`:
  - `test_coleta_tce_guarda_um_zip_por_orgao_e_ano`: `cli.coletar(["tce"]) == []`; na `ultima_coleta_boa("tce")` existem `empenhos/58700-2024.csv.zip`, `58700-2025`, `58700-2026` e `58701-2025`; cada um tem linha no `manifest.jsonl` com o sha256 dos bytes; o zip abre e o CSV de dentro é o da fixture.
  - `test_arquivo_ausente_nao_derruba_a_coleta`: `ausentes.json` contém `{"orgao": 58702, "ano": 2024}`, `2025` e `2026`, e `{"orgao": 58701, "ano": 2024}` e `2026`; a coleta tem `_OK`.
  - `test_ano_fechado_vem_da_coleta_anterior`: duas coletas seguidas; o arquivo de 2024 (ano corrente menos 2) é pedido ao TCE-RS uma vez só (contador do mock), e a segunda coleta tem o mesmo sha256 para ele; 2025 e 2026 são pedidos nas duas.
- [ ] **Step 2:** `uv run pytest tests/test_tce.py -q`: falham (módulo não existe).
- [ ] **Step 3: Implementar** `slf/coletores/tce.py`. Anos: de `ente()["inicio"].year` até o ano corrente. Ano corrente e o anterior: sempre baixados. Anos mais velhos: copiados da coleta boa anterior quando lá estão, baixados quando não. 404 vai para `ausentes.json` (pegar `httpx.HTTPStatusError` com status 404 de `Cliente.get_bytes`); outro erro derruba a coleta (as outras fontes seguem, pelo `cli.coletar`). Imprimir uma linha por órgão com quantos arquivos e bytes.
- [ ] **Step 4:** testes passam; `ruff` e a suíte inteira verdes.
- [ ] **Step 5:** textos: `fontes.tsx` ("TCE-RS: empenhos, liquidações e pagamentos da prefeitura, da Câmara, do SEMAE e do Hospital Centenário, por credor; chega com meses de atraso"), `LINKS["tce"] = "https://dados.tce.rs.gov.br/"`, linha em `docs/replicar.md` (Pergunta "Quem recebeu dinheiro de cada órgão?", Alcance "Estadual (RS)", Chave "código do órgão no TCE-RS, CNPJ do credor", Na sua cidade "Igual no RS; troque os códigos em `tce_rs`").
- [ ] **Step 6: Commit e push.** `git commit -m "Coletor do TCE-RS: empenhos e pagamentos por órgão e ano (D44)"` e `git push`.
- [ ] **Step 7: Prova de acesso no Actions (risco da spec).** Pedir ao Ruan para rodar `gh workflow run coleta.yml --repo vinidotruan/financas-sl --ref main -f fontes="tce"` (o disparo pela sessão foi barrado antes). Conferir no log: os quatro órgãos baixados, sem 403. **Se o TCE-RS bloquear o runner: parar o plano aqui e voltar ao Ruan**, sem contornar.

### Tarefa 2: Staging e core dos pagamentos

**Files:**
- Modify: `slf/processar.py` (`PREFIXO["tce"] = "tce"`, carregador dos zips, `TABELAS_VOLUME += ["despesa"]`), `slf/core.sql` (macro de pessoa física compartilhada; `core.despesa`, `core.credor_ano`, `core.despesa_mes`), `slf/pacote.py` (`core.credor_ano` e `core.despesa_mes` em `TABELAS`, pessoa física mascarada), `tests/test_tce.py`
- Create: `slf/repasses.yaml`

**Interfaces:**
- Consumes: Tarefa 1 (`empenhos/*.csv.zip` na última coleta boa de `tce`).
- Produces:
  - `staging.tce_operacao` (varchar): `orgao_codigo` mais as colunas da spec (`tipo_operacao`, `dt_operacao`, `nr_empenho`, `nr_pagamento`, `cd_credor`, `nm_credor`, `tp_pessoa`, `cnpj_cpf`, `vl_empenho`, `vl_liquidacao`, `vl_pagamento`, `ds_funcao`, `nome_orgao`) e `ano_arquivo`. O `historico` **não** entra no staging.
  - Macro `pessoa_fisica(tipo varchar, nome varchar) -> boolean` em `core.sql`, a mesma regra de hoje (PF; CPF no fim do nome; raiz de CNPJ na frente), usada por `core.contrato` e pela despesa.
  - `core.despesa`: uma linha por pagamento (`tipo_operacao = 'P'`) **lido do arquivo do próprio ano** (`year(dt_operacao) = ano_arquivo`): `orgao int, orgao_nome, ano int, mes int, data date, nr_empenho, nr_pagamento, ni varchar (14 dígitos se PJ e não pessoa física, 11 se pessoa física; lpad com zeros), pessoa_fisica bool, nome, valor double`.
  - `core.credor_ano`: `orgao, ano, ni, pessoa_fisica, nome (o do pagamento mais recente: arg_max por (data, nome)), pago double, pagamentos int, repasse bool`.
  - `core.despesa_mes`: `orgao, ano, mes, pago`.
  - `repasse` = CNPJ (14 dígitos) na lista `cnpjs` de `slf/repasses.yaml` **ou** nome casando um dos `padroes` (regex, sem diferenciar maiúsculas). Conteúdo inicial: `cnpjs: ["93850972000156"]` (instituto de previdência); `padroes: ["^BANCO ", "^CAIXA ECONOMICA", "^BANRISUL", "PREVID", "APOSENT.*PENS", "^FUNDACAO MUNICIPAL", "^FUNDO MUNICIPAL", "^MUNICIPIO ", "^PREFEITURA", "^SECRETARIA", "RECEITA FEDERAL", "^INSTITUTO NACIONAL DO SEGURO SOCIAL", "^PASEP", "^ESTADO DO "]`. Cada entrada com um comentário do porquê.

- [ ] **Step 1: Testes que falham** em `tests/test_tce.py` (sobre o `banco` com a coleta `tce`):
  - `test_pagamento_conta_no_ano_da_data`: `core.despesa_mes` da prefeitura em 2025 soma 1.925.000; em 2024, 1.009.999 (o pagamento de 2024-11-20 que também está no arquivo de 2025 conta uma vez).
  - `test_estorno_entra_na_soma`: `core.credor_ano` da Construtora em 2025 = 200.000.
  - `test_cnpj_sem_zeros_a_esquerda`: a Caixa tem `ni = '00360305000104'` e `repasse`.
  - `test_mei_do_tce_e_pessoa_fisica`: o credor `12.345.678 JOANA EXEMPLO` tem `pessoa_fisica` e `ni` de 11 dígitos não é o CNPJ; a Fulana (CPF de 10 dígitos) tem `ni = '04567890123'`.
  - `test_repasse_e_empresa`: instituto e Caixa com `repasse`; Green e Construtora sem.
  - em `tests/test_pacote.py`, `test_pacote_esconde_pessoa_fisica` ganha: em `core.credor_ano` do pacote, toda linha de pessoa física tem `ni` nulo e `nome = 'pessoa física'`; `FULANA` e `JOANA` não aparecem nos bytes do pacote.
- [ ] **Step 2:** falham.
- [ ] **Step 3: Implementar.** Carregador: para cada zip da última coleta boa de `tce`, extrair o CSV para um arquivo temporário e `insert into staging.tce_operacao select ... from read_csv(arquivo, header=true, all_varchar=true)` com `orgao_codigo` e `ano_arquivo` do nome do arquivo; sem coleta, a tabela vazia com as colunas (padrão de `_carregar_tabela`). Trocar a regra de `core.contrato.pessoa_fisica` pela macro sem mudar o resultado (os testes de MEI do PNCP seguem verdes).
- [ ] **Step 4:** testes passam; suíte inteira, `ruff`, `slf conferir` sobre um `slf pacote` local. O teste de volume de `despesa` não pode falhar quando o banco anterior ainda não tem a tabela (primeira vez da fonte): conferir como `testar` trata tabela nova e cobrir com teste se precisar.
- [ ] **Step 5: Conferir nos dados reais** (Mac, `uv run slf coletar tce && uv run slf atualizar`): prefeitura 2025 = R$ 944,6 mi (± arredondamento); as cinco empresas sem repasse: Green Card, IDEAS, Instaladora Elétrica Mercúrio, Construsinos, RGE Sul. Se diferir, explicar antes de seguir.
- [ ] **Step 6: Commit e push** (`"Pagamentos do TCE-RS no core: por credor, por ano e por mês (D44)"`). Antes do push, confirmar que a coleta `tce` já está no cache do Actions (Tarefa 1, Step 7): sem ela, o processar para de propósito (fonte sem coleta).

### Tarefa 3: Os dados do Início (`/api/inicio` e `inicio.json`)

**Files:**
- Modify: `slf/core.sql` (`core.pedido_partido`), `slf/consultas.py` (`Consulta.inicio`), `slf/api.py` (rota), `slf/exportar.py` (`gravar("inicio.json", c.inicio())`), `tests/test_exportar.py` (`ROTAS["inicio.json"] = "/api/inicio"`), `tests/test_api.py`

**Interfaces:**
- Consumes: Tarefa 2 (`core.credor_ano`, `core.despesa_mes`), `core.pedido` com `situacao`/`situacao_data`, `core.limite_pessoal`, `core.emenda`.
- Produces: `GET /api/inicio` e `inicio.json`, mesmo conteúdo (`Consulta.inicio() -> dict`):

```
{ "data_referencia": "AAAA-MM-DD",
  "recebeu": { "ano": int, "total": float, "empresas": [ {"id": str, "nome": str, "valor": float} ] (até 5),
               "ano_corrente": int, "ate": "AAAA-MM-DD" | null },
  "emendas": { "indicado": float, "transferido": float },
  "parados": { "dias": 60, "total": int, "por_situacao": [ {"situacao": str, "pedidos": int} ], "sem_situacao": int },
  "partidos": [ {"partido": str, "pedidos": int} ] (até 5),
  "bairros": [ {"id": int, "nome": str, "pedidos": int} ] (até 5),
  "folha": <a linha mais recente de contas()["limite_pessoal"]> | null,
  "fontes": [FonteRef] }
```

  - `recebeu.ano`: o maior ano em que a prefeitura (58700) tem pagamento em dezembro (`core.despesa_mes`, `mes = 12`); `total`: tudo o que ela pagou nesse ano (empresas, pessoas, repasses); `empresas`: credores da prefeitura nesse ano sem `pessoa_fisica` e sem `repasse`, por `pago desc, ni`; `id = left(md5(ni), 12)` (o mesmo do `core.fornecedor`); `ate`: a data do último pagamento da prefeitura no ano corrente da referência, ou null.
  - `core.pedido_partido(id_pedido, partido)`: pares distintos de `staging.cm_autores` (partido do autor **naquela proposição**) para os pedidos de `core.pedido`, sem partido vazio e sem autor cujo `core.vereador.cargo` seja comissão ou Mesa Diretora. `partidos`: contagem de pedidos distintos por partido, `pedidos desc, partido`.
  - `parados`: pedidos com `situacao` fora de `('Encaminhado para o Executivo', 'Arquivado')` e `hoje() - situacao_data > 60`; `sem_situacao`: pedidos com `situacao` nula.
  - Modo público: nada de pessoa física (as empresas já excluem); passa no `sem_cpf` como as outras rotas.

- [ ] **Step 1: Testes que falham** (`tests/test_api.py`; fixar a data de referência em 2026-11-19 reescrevendo o `coletado_em` dos manifests, como `test_data_de_referencia_e_a_da_coleta_e_nao_a_de_hoje`, e rodar `processar.atualizar()`):
  - `test_inicio_quem_mais_recebeu`: `ano == 2025`, `total == 1925000`, `[e["nome"] for e in empresas] == ["GREEN EXEMPLO REFEICOES LTDA", "CONSTRUTORA EXEMPLO SA"]`, valores 400000 e 200000, `ano_corrente == 2026`, `ate == "2026-02-20"`.
  - `test_inicio_partido_da_epoca`: `partidos == [{"partido": "MDB", "pedidos": 4}, {"partido": "PT", "pedidos": 3}]` (a Ana é PSOL no cadastro de hoje e PT nos pedidos; a comissão de 9007 não conta).
  - `test_pedido_de_dois_do_mesmo_partido_conta_uma_vez`: com `_nova_coleta("camara", ...)` acrescentando ao pedido 9004 um segundo autor do MDB (id 703), `MDB` continua 4.
  - `test_inicio_parados`: `parados == {"dias": 60, "total": 1, "por_situacao": [{"situacao": "Encaminhado à Comissão", "pedidos": 1}], "sem_situacao": 1}` (9007 está na pauta há 1 dia; 9005 não tem situação).
  - `test_inicio_emendas_e_folha`: `emendas` igual à soma de `indicado` e de `transferido` de `/api/emendas` (os mesmos números da aba Emendas); `folha` igual a `cliente.get("/api/contas").json()["limite_pessoal"][0]`.
  - `test_inicio_publico_sem_pessoa_fisica` (modo público): o corpo de `/api/inicio` não contém `FULANA` nem `JOANA`.
  - `test_exportacao_igual_a_api` passa a cobrir `inicio.json` (via `ROTAS`).
- [ ] **Step 2:** falham.
- [ ] **Step 3: Implementar** `core.pedido_partido` e `Consulta.inicio()`; rota `GET /api/inicio`; exportação.
- [ ] **Step 4:** testes, suíte, `ruff`; nos dados reais, `slf exportar --modo publico` + `slf conferir` sem achados, e conferir à mão os números do esboço corrigido (R$ 944,6 mi; Green Card no topo).
- [ ] **Step 5: Commit e push** (`"Dados da aba Início: quem mais recebeu, emendas, parados, partidos, bairros e folha (D44)"`).

### Tarefa 4: A aba Início no front

**Files:**
- Create: `front/src/telas/inicio.tsx`, `front/src/componentes/cartoes.tsx`, `front/src/componentes/cartoes.stories.tsx`
- Modify: `front/src/rotas.ts`, `front/src/componentes/abas.tsx`, `front/src/app.tsx`, `front/src/dados.ts`, `front/src/tipos.ts`, `front/src/estilo.css`, `docs/decisoes.md` (D44), `CLAUDE.md`

**Interfaces:**
- Consumes: `inicio.json` (Tarefa 3).
- Produces:
  - `tipos.ts`: `interface Inicio` com o formato da Tarefa 3.
  - `dados.inicio(): Promise<Inicio>` (rota `{ api: 'api/inicio', arquivo: 'inicio.json' }`).
  - `rotas.ts`: `Aba` ganha `'inicio'`; `Rota` ganha `{ tela: 'inicio' }`; `lerRota('')`, `lerRota('#/')` e rota desconhecida dão `{ tela: 'inicio' }`; `link.inicio = () => '#/'`; `abaDa({ tela: 'fontes' }) === 'inicio'`.
  - `abas.tsx`: ordem `inicio, emendas, pedidos, fichas, contas, sinais`; ícone de casa para Início; Fontes sai da barra.
  - `cartoes.tsx`: `CartaoPergunta({ pergunta, children, href?, rotuloLink?, tracejado? })`; `BarrasValor({ linhas: { chave, nome, valor, href? }[], formato: (n: number) => string })` (barra proporcional ao maior, valor à direita, nome com reticências); `BarraProgresso({ parte, todo, rotulo })`; o medidor da LRF reaproveita o de `contas.tsx` (extrair `Medidor` para `componentes/` em vez de duplicar).
  - `inicio.tsx`: os sete cartões na ordem da spec, com os textos do esboço A aprovado (página de progresso, seção "Aba inicial"); cartão 1 com "R$ X pagos no ano a empresas, pessoas e outros órgãos" e a nota "Sem órgãos públicos e bancos. Fonte: TCE-RS. 2026 vai até {ate}."; cartão 3 com "Ainda conferindo N pedidos" quando `sem_situacao > 0`; cartão 7 tracejado; rodapé com link para Fontes. "Ver todas" do cartão 1 aponta para `link.fichas('fornecedores')` nesta tarefa (a Tarefa 5 troca pela ordem por pago).
- [ ] **Step 1:** stories em `cartoes.stories.tsx`: `Pergunta com barras`, `Pergunta com progresso`, `Em breve (tracejado)`, nos dois temas.
- [ ] **Step 2: Implementar** tipos, dados, rotas, abas, componentes e tela; `app.tsx` com `case 'inicio'`.
- [ ] **Step 3: Verificar:** `npx tsc --noEmit`, `npm run build`, `npm run build-storybook`; com `uv run slf servir --host 127.0.0.1` e Playwright a 360px e 1280px, nos dois temas: `#/` abre o Início, sem rolagem lateral, sem erro no console, cada link dos cartões abre a tela certa; print comparado com o esboço A.
- [ ] **Step 4:** `docs/decisoes.md`: D44 (fonte TCE-RS, regra do ano da data, repasses, Início como primeira aba, partido da época, "parado"); `CLAUDE.md` (aba Início, fonte `tce`).
- [ ] **Step 5: Commit e push** (`"Aba Início: sete cartões-pergunta e a primeira aba do site (D44)"`). Conferir no site publicado: `#/` mostra o Início; prints na página de progresso.

### Tarefa 5: Pago ao lado do contratado em Fichas → Fornecedores

**Files:**
- Modify: `slf/core.sql` (`core.fornecedor`), `slf/consultas.py` (`fornecedores`, `fornecedor`), `slf/pacote.py` (colunas novas mascaradas), `front/src/rotas.ts`, `front/src/telas/fichas.tsx`, `front/src/telas/inicio.tsx` (link do cartão 1), `front/src/tipos.ts`, `tests/test_api.py`

**Interfaces:**
- Consumes: Tarefa 2 (`core.credor_ano`), Tarefa 4 (cartão 1).
- Produces:
  - `core.fornecedor`: NIs dos contratos do PNCP **e** credores PJ (não pessoa física) do TCE-RS; colunas novas `pago_total double` (soma de `core.credor_ano` de todos os órgãos e anos), `repasse bool`; pessoa física só do TCE-RS não entra (continua o que o PNCP tem).
  - `fornecedores.json` e `/api/fornecedores`: cada item ganha `pago_total: number`, `pago_prefeitura: Record<string, number>` (ano → pago pela 58700) e `repasse: boolean`; contratado zero quando o fornecedor só aparece no TCE-RS.
  - `/api/fornecedores/{id}`: ganha `pagos: [{orgao_nome, ano, valor}]` (ordem `ano desc, orgao_nome`).
  - `rotas.ts`: `{ tela: 'fichas', lista: 'fornecedores', ordem?: string }`, com `#/fichas/fornecedores/pago-2025` → `ordem: 'pago-2025'`; `link.fichas('fornecedores', 'pago-2025')`.
  - `fichas.tsx`: seletor "Maior contratado" / "Maior pago pela prefeitura em {ano}" (um por ano de `pago_prefeitura`); valor rotulado "contratados" ou "pagos"; selo "órgão público ou banco" quando `repasse`; contratado "—" quando zero. Ficha: cartão "Pago" e a lista `pagos`.
  - Cartão 1 do Início: "Ver todas" → `link.fichas('fornecedores', \`pago-${recebeu.ano}\`)`.

- [ ] **Step 1: Testes que falham** (`tests/test_api.py`):
  - `test_fornecedor_so_do_tce_entra_com_pago`: em `/api/fornecedores`, Green tem `contratos == 0`, `pago_total == 1469999`, `pago_prefeitura == {"2024": 999999, "2025": 400000, "2026": 70000}`; a Papelaria (só Câmara) tem `pago_total == 1000` e `pago_prefeitura == {}`.
  - `test_fornecedor_com_contrato_e_pago`: a Construtora tem `contratos == 1` (PNCP) e `pago_prefeitura == {"2024": 10000, "2025": 200000, "2026": 30000}`; a ficha tem `pagos` com três linhas da prefeitura.
  - `test_repasse_tem_selo`: a Caixa tem `repasse` true.
  - `test_pessoa_fisica_do_tce_nao_vira_fornecedor` (público e privado): nenhum item com `FULANA` ou `JOANA` no nome; nenhum id novo de pessoa física.
- [ ] **Step 2:** falham.
- [ ] **Step 3: Implementar** core, consultas, pacote e front.
- [ ] **Step 4: Verificar:** suíte, `ruff`, `slf conferir` no export e no pacote; front (`tsc`, build, Storybook) e Playwright: o "Ver todas" do Início abre Fornecedores com as mesmas 5 empresas no topo, na mesma ordem.
- [ ] **Step 5: Commit e push** (`"Fornecedores: pago pelo TCE-RS ao lado do contratado, e o Ver todas do Início (D44)"`). Conferir no site e atualizar a página de progresso.
