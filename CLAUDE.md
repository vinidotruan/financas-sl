# Finanças de São Leopoldo

Painel que junta dados públicos das emendas parlamentares destinadas a São Leopoldo (RS) e das
finanças da prefeitura, e aponta **sinais de risco** (pontos de atenção, nunca acusações). Projeto
pessoal do Ruan. Fala em português do Brasil, tanto na conversa quanto em textos de tela, commits e
comentários.

- Município: IBGE `4318705`, CNPJ `89.814.693/0001-60`
- Pasta: `~/studies/financas-sl`
- Estado: a **fase 1** do backend foi escrita e testada com respostas falsas no formato real das APIs,
  mas **ainda não rodou contra as APIs ao vivo**. Isso é a primeira coisa a fazer (ver "Tarefas").

## Objetivo desta etapa

1. Rodar e corrigir o backend contra as APIs reais.
2. Fazer o **front** (painel pensado pra celular).
3. Rodar a coleta e a publicação no **GitHub Actions**.

Antes de começar o item 3, pergunte ao Ruan a decisão de privacidade (seção "Decisão em aberto").

## Comandos

```bash
uv sync                      # instala dependências (uv também baixa o Python)
uv run slf coletar [fonte]   # transferegov | siconfi | pncp; sem argumento, todas
uv run slf atualizar         # raw -> staging -> core -> testes -> sinais (sem coletar)
uv run slf atualizar --forcar  # troca o banco mesmo com teste de dados falhando
uv run slf diario            # coletar tudo + atualizar (o que o agendamento roda)
uv run slf status            # última coleta boa por fonte e contagem de sinais
uv run slf servir            # API + tela em http://localhost:8765 (mostra o IP pro celular)
SLF_MODO=publico uv run slf servir   # modo público (ver "Regras que não se quebram")
./scripts/agendar.sh         # launchd: slf diario todo dia às 06:10
```

`SLF_HOME` muda a raiz do projeto (útil em testes).

## Arquitetura

```
fontes -> coletores -> data/raw (imutável) -> staging (DuckDB) -> core -> sinais -> API / export
```

| Caminho | O que é |
|---|---|
| `config/ente.yaml` | IBGE, CNPJ, data de início e a lista de órgãos do PNCP |
| `slf/coletores/*.py` | Um coletor por fonte. Grava via `raw.Coleta` e só marca `_OK` no fim |
| `slf/raw.py` | `data/raw/{fonte}/{AAAA-MM-DDTHHMMSS}/*.json` + `manifest.jsonl` (url, params, sha256, linhas) |
| `slf/http.py` | httpx com retry (tenacity) em 429/5xx/timeout e pausa entre chamadas |
| `slf/processar.py` | Carrega a última coleta boa de cada fonte em `staging`, roda `core.sql`, testes, sinais |
| `slf/core.sql` | Entidades: `plano_acao`, `emenda`, `transferencia`, `relatorio_gestao`, `prazo_plano`, `meta`, `rastro_plano`, `compra`, `contrato`, `aditivo`, `fornecedor`, `pessoal`, `receita`, `fonte` |
| `slf/sinais.py` | Lê `slf/regras/*.yaml`, roda o SQL de cada regra, guarda histórico e aplica a revisão |
| `slf/regras/*.yaml` | Uma regra por arquivo: id, nome, versao, area, severidade, base_legal, limiar, pode_ser_normal_se, como_verificar, fontes, sql |
| `slf/api.py` | FastAPI só leitura (conexão `read_only` a cada pedido) |
| `slf/web/index.html` | Tela provisória em JS puro. Vai ser substituída pelo front novo |
| `data/slf.duckdb` | Banco. É montado em `slf.novo.duckdb` e trocado com `os.replace` só se os testes passarem |
| `data/revisao.json` | Status e nota que o Ruan dá a cada sinal. Fica fora do banco de propósito |

Detalhes que importam:
- **Chave da emenda:** código de 12 dígitos `AAAA` + autor (4) + sequencial (4), ex. `202642710013`.
  No portal da prefeitura aparece como `2026/42710013`. `core.plano_acao.codigo_emenda` guarda só os dígitos.
- **Cadeia da transferência no Transferegov:** `plano_acao_especial` -> `empenho_especial` (id_plano_acao)
  -> `documento_habil_especial` (id_empenho) -> `ordem_pagamento_ordem_bancaria_especial` (id_dh).
  O valor transferido é o `valor_dh`; a data é a da ordem bancária.
- **PNCP:** contratos vêm da API de consulta por mês e por CNPJ do órgão. Modalidade e amparo legal
  vêm da compra (`numeroControlePncpCompra`), e os aditivos da API `/api/pncp/v1/.../termos`.
  Os campos de qualificação do aditivo costumam vir vazios, por isso `core.aditivo.altera_vigencia`
  também lê o texto do objeto.
- **Staging tolerante:** `processar.COLUNAS` lista as colunas que o core usa. Se a fonte vier vazia
  ou sem a coluna, ela é criada como nula, então o core nunca quebra por falta de coluna.
  Joins entre ids usam `cast(... as varchar)` porque o tipo inferido varia.
- **Testes de dados** (`processar.TESTES_DUROS` e queda de mais de 20% de linhas) barram a troca do banco.
- **Ocorrência de sinal:** id = `md5(regra_id|chave)`. Guarda `primeira_vez` entre execuções; as que
  somem viram `ativo=false`. Um sinal descartado volta a `novo` se o valor observado mudar.

## Regras de sinal da fase 1

| Id | Regra | Observação |
|---|---|---|
| R02 | Dinheiro de emenda parado | Transferido há mais de 180 dias e menos de 10% executado. Hoje mede pelo relatório de gestão do Transferegov; o empenhado e o pago reais vêm do portal da prefeitura (fase 2) |
| R03 | Relatório de gestão ausente | Prazo do plano vencido sem relatório final |
| R05 | Contrato emergencial prorrogado | Art. 75, VIII com aditivo de vigência |
| R06 | Licitação publicada depois de fechar | Publicação no PNCP depois do fim das propostas |
| R07 | Contratação direta alta | Mais de 50% do valor sem licitação, por órgão e ano |
| R08 | Aditivo acima do teto | Valor global mais de 25% acima do inicial |

Planejadas: R01 valor que não bate entre fontes (precisa da MSC do SICONFI e do portal), R04 gasto
fora do objeto e R09 piso de 70% em investimento (portal), R10 a R13 (cadastro de CNPJ e sanções).

## Regras que não se quebram

- **Linguagem neutra.** Tela, README e commits falam em "sinal", "ponto de atenção", "indicador acima
  do limiar". Nunca "fraude", "desvio", "corrupção" ou "irregular" junto de um nome de pessoa ou empresa.
  Todo sinal mostra a regra, o limiar, a data do dado, a fonte e o "pode ser normal se".
- **CPF nunca aparece inteiro**, em nenhum modo (`api._mascara_cpf`). Endereço de pessoa física, nunca.
- **Modo público** (`SLF_MODO=publico`): pessoa física (inclui MEI e empresário individual) aparece
  como "pessoa física"; só aparecem sinais com status `confirmado` ou `encaminhado`; sem edição.
  **Tudo que for publicado na internet sai em modo público.**
- **`data/` nunca vai pro git.** Está no `.gitignore`. Não commitar `revisao.json` num repositório público.
- **Raw é imutável.** Correção de dado se faz no staging ou no core, nunca editando arquivo em `data/raw`.
- **Uma fonte falhar não pode parar as outras.** Mantenha o `try` por coletor e o "último dado bom".
- Só dados públicos. Não automatizar login nem contornar bloqueio de site (Cloudflare etc.); quando
  bloquear, o caminho é a pasta `inbox/` com arquivo baixado à mão.

## Tarefas, em ordem

### 1. Verificar contra as APIs reais

- `uv sync && uv run slf diario`, depois `uv run slf status`.
- Pontos que não foram conferidos ao vivo:
  - Parâmetro `no_anexo=RREO-Anexo 01` no coletor do SICONFI. Se o RREO vier vazio, testar sem ele
    e filtrar o anexo no core.
  - Limite de `tamanhoPagina` e da janela de datas na API de consulta do PNCP.
  - Valores reais de `tipo_relatorio_gestao_novo` (a R03 procura "final" no texto).
  - Nomes das colunas de RCL e de "% sobre a RCL" no RGF Anexo 01, pra tela de contas.
- Conferir os números com a análise de 18/11/2026: 34 planos de ação de 2022 a 2026 (8, 1, 6, 11, 8);
  R$ 10.373.122,50 indicados e R$ 5.545.122,50 transferidos; emenda `202642710013` com 2 planos
  (R$ 248.750,00 + R$ 224.372,50); 21 de 80 emergenciais com aditivo de prazo; 73% dos contratos de
  2024 a 2026 sem licitação.
- Pedir ao Ruan os CNPJs da Fundação Hospital Centenário e das outras fundações e autarquias pra
  `config/ente.yaml`.
- Transformar o teste com respostas falsas em `tests/` (pytest), com fixtures por fonte, e adicionar ruff.

### 2. Front

Telas (a "opção C" escolhida no desenho): **Sinais** (lista por severidade, filtro por área) ->
**detalhe do sinal** (o que foi visto, regra, pode ser normal se, como verificar, fontes, revisão) ->
**rastro da emenda** (do parlamentar ao valor transferido e executado, com o valor de cada fonte lado a lado)
-> **fichas** de parlamentar e fornecedor; mais **Contas** (pessoal sobre RCL com os limites da LRF:
48,6%, 51,3%, 54%) e **Fontes** (data do último dado bom).

Requisitos:
- Celular primeiro, abas embaixo, funciona bem em 360 px. Tema claro e escuro.
- Mesmo front nos dois modos de dados: a API local (`/api/...`) em desenvolvimento e arquivos JSON
  estáticos na publicação. Faça uma camada de dados única que troca por configuração.
- A revisão (botões de status e nota) só aparece quando a API estiver disponível e em modo privado.
- Sem dependência pesada. Stack é escolha sua; algo como Vite com Preact ou Svelte, ou JS puro, gerando
  arquivos estáticos em `site/`. Coloque o código em `front/`.
- Paleta usada no desenho (claro / escuro): fundo `#f4f7f5`/`#111714`, superfície `#ffffff`/`#18201c`,
  texto `#17211d`/`#e3eae6`, apagado `#56665f`/`#9bada5`, linha `#d6dfda`/`#2b3732`, destaque
  `#1d6b58`/`#5fc3a5`, alerta alto `#a3301d`/`#f29482`, atenção `#8f5a00`/`#e6ad47`, info `#2c5a88`/`#92bae8`.
  Fontes: Archivo (títulos), Public Sans (texto), IBM Plex Mono (números e rótulos).
- Valores em reais no formato brasileiro (`R$ 1.234.567,89`), datas `dd/mm/aaaa`.

### 3. Exportação estática

Adicionar `slf exportar [--modo publico] [--saida site/data]` que gera um JSON por rota da API:
`sinais.json`, `sinais/{id}.json`, `emendas.json`, `rastro/{codigo}.json`, `contas.json`, `fontes.json`.
Tire a lógica das rotas de `api.py` pra um módulo compartilhado (ex. `slf/consultas.py`), pra API e
exportação devolverem exatamente o mesmo conteúdo. A exportação pública passa pelos mesmos filtros
de privacidade.

### 4. GitHub Actions

- `ci.yml`: em push e pull request, `uv sync`, ruff, pytest (com as fixtures, sem rede).
- `coleta.yml`: `schedule` com cron em UTC (`10 9 * * *` = 06:10 em Brasília) e `workflow_dispatch`.
  Roda `slf diario`, `slf exportar --modo publico`, builda o front e publica.
- **Persistência entre execuções:** o runner começa vazio a cada vez. Proposta: guardar `data/raw`
  recente e `data/slf.duckdb` como asset de uma release fixa (ex. `dados-latest`) com `gh release`,
  baixando no início e subindo no fim. Assim o histórico de sinais (`primeira_vez`) continua.
  Alternativas: um branch `dados` ou o cache do Actions (que expira); discuta com o Ruan antes.
- **Revisão:** num site estático ninguém grava. O `revisao.json` precisa morar em algum lugar que o
  workflow leia (ex. arquivo versionado num repositório privado, editado pelo Ruan localmente) e
  `config.REVISAO` precisa aceitar esse caminho.
- Cuidados: o cron do Actions pode atrasar; em repositório público, workflows agendados são desligados
  depois de 60 dias sem atividade; os sites do governo podem bloquear ou ficar lentos com IP de fora
  do Brasil, então mantenha os timeouts e o "último dado bom". Nenhum segredo é necessário (APIs abertas).
- Repositório: criar **privado** com `gh repo create` e só mudar se o Ruan pedir.

## Decisão em aberto (perguntar antes da tarefa 4)

**O painel publicado é público?** GitHub Pages publica um site aberto mesmo vindo de repositório
privado (exceto em planos Enterprise com páginas privadas). Então há dois caminhos:

| Caminho | Como fica |
|---|---|
| A. Publicar no Pages | Site aberto, sempre em modo público. A revisão continua no Mac |
| B. Actions só coleta | O workflow coleta e guarda o banco na release; o Mac baixa e serve em modo privado (Tailscale pro celular) |

Também em aberto, vindas do desenho: SQL puro ou dbt-duckdb (ficou SQL puro até passar de uns 40
modelos) e o ok pra adicionar fontes novas (cadastro de CNPJ, sanções CEIS/CNEP/CEPIM, TCE-RS, ZIP de
emendas da CGU).

## Fases seguintes (contexto, não fazer agora)

- **Fase 2, portal da prefeitura** (`grp.saoleopoldo.rs.gov.br`, sistema Thema): sem API pública, token
  por página. Playwright capturando o JSON que a própria página recebe (não ler HTML). Traz empenhado,
  liquidado e pago por emenda, empenho por credor, contratos e folha. É o que liga emenda a fornecedor.
- **Fase 3, empresas:** cadastro de CNPJ (só os que aparecem, com cache) e sanções da CGU.
- **Fase 4:** TCE-RS (CSV, instável, Cloudflare), ZIP completo de emendas da CGU, emendas estaduais
  (só em painéis Power BI e Qlik, via `inbox/`), e por último pessoas e doações (TSE), o cruzamento
  mais sensível.
