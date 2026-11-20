# Diagnóstico das execuções e coleta mais segura · plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** cada etapa (coleta, processar, conferir, publicar) registra o que deu errado em arquivos para baixar, publicados numa página `#/diagnostico` com os últimos 30 dias, inclusive quando a etapa trava a publicação; e os cinco pontos da coleta mais segura corrigidos.

**Architecture:** módulo novo `slf/diagnostico.py` com uma `Execucao` por etapa (pasta `{AAAA-MM-DDTHHMMSS}-{etapa}` com `execucao.json`, `eventos.jsonl`, `{etapa}.log`, dumps CSV e respostas da fonte), aberta como gerenciador de contexto pelo `coletar`, pelo `atualizar` e pelo `conferir`; o código de dentro registra pela função `registrar()` (ContextVar, como `raw.coletas_fixadas`). `slf diagnostico publicar` monta a cópia publicável (conferência por arquivo, 30 dias, 50 MB) com `indice.json`; o `publicar.yml` copia para `site/data/diagnostico/`, também quando o `processar` falhou. A API local serve o mesmo índice. A página lê o índice pela camada de dados de sempre.

**Tech Stack:** Python 3 + uv, DuckDB, FastAPI, pytest com `httpx.MockTransport`; Preact 10 + TypeScript + Vite 7; Storybook 10.6.5; GitHub Actions (caches `actions/cache` v5).

**Spec:** `docs/superpowers/specs/2026-11-19-diagnostico-e-coleta-segura-design.md` (leia antes; o contrato do `indice.json` está lá e vale como está).

## Global Constraints

- Tudo em pt-BR (código, comentários, commits, textos de tela); nunca travessão (em dash) em texto entregue.
- Commit: uma linha para mudança pequena, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Push: ao fim de cada tarefa, se a permissão deixar; se for barrado, segue local e o Ruan empurra.
- CPF nunca inteiro nem mascarado em arquivo de diagnóstico (usar `sensivel.sem_documento`); pessoa física e MEI como "pessoa física". Tudo o que vai ao ar passa pela conferência (D40).
- Linguagem neutra: nunca "fraude", "desvio", "corrupção" ou "irregular".
- O diagnóstico nunca trava o site nem a coleta: falha ao gravar diagnóstico vira `print` e segue.
- Uma fonte fora do ar não segura as outras; vale a última coleta boa.
- `data/` nunca vai ao git. A pasta do diagnóstico é `config.DIAG` (`SLF_DIAGNOSTICO`, padrão `data/diagnostico`).
- Limites (spec): resposta original até 1 MB; qualquer arquivo até 5 MB (o excesso é cortado e vira aviso `diagnostico.arquivo_cortado`); cópia publicada abaixo de 50 MB, apagando as execuções mais velhas primeiro; 30 dias; até 50 eventos por execução no índice.
- `situacao`: `falhou` quando a etapa parou; `com_problemas` quando houve evento e a etapa seguiu; `ok` sem evento.
- Dependência nova: nenhuma.
- Front: tokens de `front/src/tokens.css`, dois temas, 360 px sem rolagem lateral; componente novo ganha story.
- Verificação de cada tarefa: `uv run ruff check slf tests`, `uv run pytest -q`; no front, `cd front && nvm use && npx tsc --noEmit && npm run build && npm run build-storybook`.

## Review Focus

1. **Etapa morta no meio** (timeout de 180 min, cancelamento, `kill`): a execução fica aberta e precisa aparecer como `falhou`, não sumir. Teste `test_fechar_abertas_marca_interrompida` na Tarefa 1.
2. **Resposta da fonte enorme, binária ou fora de UTF-8**: corta em 1 MB, binário não é guardado (o evento diz tipo e tamanho), bytes inválidos viram `�`. Testes na Tarefa 1.
3. **CPF dentro de uma linha de log ou de uma célula de CSV**: o arquivo é retido, a execução ganha aviso `conferir.arquivo_retido` com só a forma do trecho, o resto sai. Teste na Tarefa 2.
4. **Pasta de diagnóstico vazia ou inexistente** (primeira execução, cache perdido): o índice sai com `execucoes: []` e a página mostra "Nenhuma execução registrada ainda." Testes nas Tarefas 2 e 3.
5. **Caminho malicioso na API local** (`/api/diagnostico/../slf.duckdb`, nome com `/`): 404, nunca um arquivo fora da pasta da execução (o `slf servir` ainda fica aberto na rede). Teste na Tarefa 2.

---

### Task 1: O registro de diagnóstico

**Files:**
- Create: `slf/diagnostico.py`, `tests/test_diagnostico.py`
- Modify: `slf/config.py` (`DIAG`), `slf/cli.py` (subcomando `diagnostico` com `registrar` e `fechar-abertas`)

**Interfaces:**
- Produces:
  - `config.DIAG: Path`
  - `diagnostico.ETAPAS = ("coleta", "processar", "conferir", "publicar")`; constantes `LIMITE_RESPOSTA = 1_000_000`, `LIMITE_ARQUIVO = 5_000_000`, `LIMITE_PUBLICADO = 50_000_000`, `DIAS = 30`, `EVENTOS_NO_INDICE = 50`
  - `class Execucao(etapa: str)`: atributos `id: str`, `etapa: str`, `dir: Path`; métodos
    `registrar(tipo: str, codigo: str, mensagem: str, *, fonte: str | None = None, passo: str | None = None, quantidade: int | None = None, arquivo: str | None = None) -> dict`,
    `dump_csv(nome: str, linhas: list[dict]) -> str` (devolve o nome do arquivo `{nome}.csv`),
    `resposta(nome: str, corpo: bytes, tipo_conteudo: str | None) -> str | None`,
    `fechar(parou: bool) -> dict` (devolve o conteúdo final de `execucao.json`).
  - `@contextmanager execucao(etapa: str) -> Iterator[Execucao]`
  - `registrar(tipo, codigo, mensagem, **campos) -> dict | None` (na execução atual; sem execução, só imprime `  aviso: {mensagem}` ou `  erro: {mensagem}`)
  - `atual() -> Execucao | None`
  - `fechar_abertas(motivo: str) -> list[str]` (ids fechados)
  - CLI: `slf diagnostico registrar --etapa E --tipo erro|aviso --codigo C --mensagem M [--fonte F]` (abre, registra e fecha uma execução de um evento; fecha como `falhou` quando o tipo é `erro`) e `slf diagnostico fechar-abertas --motivo M`.

- [ ] **Step 1: Escrever os testes que falham** em `tests/test_diagnostico.py`:

```python
def test_execucao_grava_eventos_e_fecha_com_problemas():
    with diagnostico.execucao("coleta") as ex:
        diagnostico.registrar("aviso", "pncp.compra_falhou", "3 compras não vieram", fonte="pncp", quantidade=3)
        print("Coletando pncp…")
    meta = json.loads((ex.dir / "execucao.json").read_text())
    assert meta["situacao"] == "com_problemas" and meta["etapa"] == "coleta" and meta["fim"]
    eventos = [json.loads(l) for l in (ex.dir / "eventos.jsonl").read_text().splitlines()]
    assert eventos[0]["codigo"] == "pncp.compra_falhou" and eventos[0]["etapa"] == "coleta"
    assert "Coletando pncp" in (ex.dir / "coleta.log").read_text()

def test_excecao_fecha_como_falhou_e_propaga():
    with pytest.raises(SystemExit):
        with diagnostico.execucao("processar") as ex:
            raise SystemExit(1)
    meta = json.loads((ex.dir / "execucao.json").read_text())
    assert meta["situacao"] == "falhou"
    assert json.loads((ex.dir / "eventos.jsonl").read_text().splitlines()[0])["codigo"] == "processar.parou"

def test_sem_evento_fecha_ok(): ...  # situacao == "ok", eventos.jsonl ausente ou vazio

def test_mesmo_segundo_ganha_sufixo(monkeypatch):  # agora() fixo: a segunda pasta termina em "-2"

def test_cpf_nunca_inteiro_no_evento_no_csv_e_no_log():
    # mensagem, célula de CSV e linha impressa com "123.456.789-01" saem com "[CPF omitido]"

def test_resposta_corta_em_1mb_e_ignora_binario():
    # 2 MB de HTML → arquivo .html com 1_000_000 bytes no máximo e aviso diagnostico.arquivo_cortado;
    # image/png → devolve None e nenhum arquivo; bytes inválidos em UTF-8 viram "�"

def test_fechar_abertas_marca_interrompida():
    ex = diagnostico.Execucao("coleta")  # aberta e nunca fechada, como num timeout
    assert diagnostico.fechar_abertas("o job terminou com cancelled") == [ex.id]
    meta = json.loads((ex.dir / "execucao.json").read_text())
    assert meta["situacao"] == "falhou"
```

- [ ] **Step 2: Rodar e ver falhar:** `uv run pytest tests/test_diagnostico.py -q`, esperado `ModuleNotFoundError: slf.diagnostico`.
- [ ] **Step 3: Implementar.** `execucao.json` é escrito na abertura (com `fim` e `situacao` nulos: é isso que marca "aberta") e reescrito no `fechar`. `commit` e `url_actions` vêm do ambiente (`GITHUB_SHA`, `GITHUB_SERVER_URL/GITHUB_REPOSITORY/actions/runs/GITHUB_RUN_ID`); fora do Actions, `commit` pelo `consultas._commit()` e `url_actions` nulo. Horários pelo `config.agora()` com o deslocamento do fuso da cidade. O log é um `tee` de `sys.stdout` e `sys.stderr` enquanto o contexto vive, com `sem_documento` linha a linha. `SystemExit(0)` e `SystemExit(None)` não contam como parada. Toda escrita em try/except: erro ao gravar diagnóstico vira `print` e não interrompe a etapa.
- [ ] **Step 4: Rodar e ver passar:** `uv run pytest tests/test_diagnostico.py -q && uv run ruff check slf tests`.
- [ ] **Step 5: Commit:** `git commit -m "Diagnóstico: registro por etapa com eventos, log e dumps (D45)"`.

### Task 2: Conferência, publicação do índice e API

**Files:**
- Modify: `slf/sensivel.py` (`conferir_arquivo`; `conferir` lê os formatos novos), `slf/diagnostico.py` (`indice`, `publicar`, `podar`), `slf/cli.py` (`slf diagnostico publicar`, `slf diagnostico podar`; `slf conferir` abre uma execução `conferir` e registra cada achado), `slf/api.py` (duas rotas)
- Test: `tests/test_diagnostico.py`, `tests/test_privacidade.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: Tarefa 1.
- Produces:
  - `sensivel.conferir_arquivo(arq: Path, nome: str, liberados: set[str] | frozenset[str] = frozenset()) -> list[Achado]` para `.json`, `.parquet`, `.jsonl` (caminho `[linha].campo`), `.csv` (`[linha].coluna`), `.log`, `.txt`, `.html` (`[linha]`).
  - `diagnostico.indice(base: Path = DIAG, dias: int = 30) -> dict` no formato do contrato da spec.
  - `diagnostico.publicar(saida: Path, liberados: set[str], dias: int = 30) -> dict` (grava `saida/indice.json` e `saida/{execucao}/{arquivo}`; devolve o índice publicado).
  - `diagnostico.podar(dias: int = 30) -> list[Path]`.
  - CLI: `slf diagnostico publicar --saida DIR [--liberados config/sensivel-liberados.yaml]` e `slf diagnostico podar`.
  - API: `GET /api/diagnostico` (índice de `DIAG`) e `GET /api/diagnostico/{execucao}/{arquivo}`; `execucao` casa `^\d{4}-\d{2}-\d{2}T\d{6}(-\d+)?-(coleta|processar|conferir|publicar)$`, `arquivo` casa `^[\w.-]+$` e não começa com ponto; fora disso, 404.
  - Evento de achado do `slf conferir`: `erro`, `conferir.dado_sensivel`, mensagem `"{regra} em {arquivo} {caminho}: …{forma}…"` (nunca o texto); com achado, a execução fecha `falhou` e o comando sai com 1, como hoje.

- [ ] **Step 1: Testes que falham:**

```python
def test_indice_segue_o_contrato():  # chaves gerado_em, dias, execucoes[id, etapa, inicio, fim, situacao,
    # commit, url_actions, contagem{erro, aviso}, eventos, arquivos[nome, tipo, bytes, descricao?]];
    # mais nova primeiro; tipo do arquivo em {"eventos", "log", "dump", "resposta"}

def test_indice_corta_em_50_eventos():  # 60 eventos → 50 no índice, 60 no eventos.jsonl publicado

def test_publicar_retem_arquivo_com_cpf():
    # um .log escrito à mão com CPF inteiro dentro da pasta da execução
    indice = diagnostico.publicar(saida, set())
    ex = indice["execucoes"][0]
    assert "coleta.log" not in {a["nome"] for a in ex["arquivos"]}
    assert not (saida / ex["id"] / "coleta.log").exists()
    assert any(e["codigo"] == "conferir.arquivo_retido" for e in ex["eventos"])
    assert "123" not in json.dumps(indice)  # só a forma do trecho

def test_publicar_sem_pasta_da_indice_vazio():
    assert diagnostico.publicar(saida, set())["execucoes"] == []

def test_publicar_deixa_de_fora_mais_de_30_dias_e_passa_de_50_mb(monkeypatch):
    # execução com inicio de 31 dias atrás não sai; com LIMITE_PUBLICADO = 2_000 e três execuções de
    # ~900 bytes, saem só as duas mais novas

def test_conferir_le_csv_jsonl_e_log():  # em tests/test_privacidade.py, um achado por formato

def test_api_diagnostico_e_caminho_malicioso(cliente):  # em tests/test_api.py
    assert cliente.get("/api/diagnostico").status_code == 200
    for ruim in ("../slf.duckdb", "x/../../slf.duckdb", ".execucao.json"):
        assert cliente.get(f"/api/diagnostico/2026-11-20T061003-coleta/{ruim}").status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar:** `uv run pytest tests/test_diagnostico.py tests/test_privacidade.py tests/test_api.py -q`.
- [ ] **Step 3: Implementar.** No `publicar`, o arquivo retido entra no `eventos.jsonl` publicado e no índice como aviso, nunca bloqueia; o `.jsonl` publicado é regravado só com os eventos que passam na conferência. 30 dias contados pelo `inicio` contra `agora()`.
- [ ] **Step 4: Rodar e ver passar** (mesmo comando + ruff).
- [ ] **Step 5: Commit:** `git commit -m "Diagnóstico: índice publicável com conferência por arquivo e rotas na API (D45)"`.

### Task 3: A página de diagnóstico (agentes; não depende do código das Tarefas 1 e 2, só do contrato)

**Files:**
- Create: `front/src/telas/diagnostico.tsx`, `front/src/componentes/diagnostico.tsx`, `front/src/componentes/diagnostico.stories.tsx`
- Modify: `front/src/tipos.ts`, `front/src/dados.ts`, `front/src/rotas.ts`, `front/src/app.tsx`, `front/src/telas/fontes.tsx`, `front/src/formato.ts` (`tamanho`), `front/src/estilo.css` se precisar

**Interfaces:**
- Consumes: o contrato do `indice.json` da spec (campos e valores exatos).
- Produces:
  - Tipos `EventoDiagnostico`, `ArquivoDiagnostico`, `ExecucaoDiagnostico`, `IndiceDiagnostico` (espelham o contrato; `situacao: 'ok' | 'com_problemas' | 'falhou'`; `tipo` do arquivo `'eventos' | 'log' | 'dump' | 'resposta'`).
  - `dados.diagnostico(): Promise<IndiceDiagnostico>` pela rota `{ api: 'api/diagnostico', arquivo: 'diagnostico/indice.json' }`.
  - `urlArquivoDiagnostico(execucao: string, arquivo: string): string` (API: `api/diagnostico/{e}/{a}`; estático: `data/diagnostico/{e}/{a}`).
  - Rota `{ tela: 'diagnostico' }`, `link.diagnostico() === '#/diagnostico'`, `abaDa` devolve `'inicio'` (como Fontes).
  - `formato.tamanho(bytes: number): string`: `412 B`, `39,3 kB`, `1,2 MB` (base 1000, vírgula decimal).
  - Componentes `CartaoExecucao`, `ListaEventos`, `ListaArquivos`.

- [ ] **Step 1: Stories primeiro** em `diagnostico.stories.tsx`, com execuções inventadas no formato do contrato: uma `ok`, uma `com_problemas` (aviso do PNCP com CSV), uma `falhou` (teste de dados que barrou o banco, com log e link do run), uma `falhou` local (sem `url_actions` nem `commit`) e a lista vazia.
- [ ] **Step 2: Tela e componentes.**
  - Topo "Diagnóstico das execuções", subtítulo "O que deu errado em cada etapa, nos últimos 30 dias, com os arquivos para baixar".
  - Filtro por etapa com os botões `filtro` (Todas, Coleta, Processar, Conferir, Publicar).
  - Cada execução: etapa, data e hora (`dataHora`), chip de situação ("ok", "com problemas", "falhou"), "Ver o run no GitHub ↗" quando há `url_actions`, eventos (tipo, fonte, passo, mensagem, quantidade) e arquivos com `download` e o tamanho.
  - Vazio: "Nenhuma execução registrada ainda."
  - No fim da tela Fontes, antes do `Rodape`: link "Diagnóstico das execuções, para desenvolvedores".
- [ ] **Step 3: Verificar:** `cd front && nvm use && npx tsc --noEmit && npm run build && npm run build-storybook`. Conferir as stories a 360 e 1280 px, claro e escuro, sem rolagem lateral; nome de arquivo e mensagem longos quebram linha.
- [ ] **Step 4: Commit:** `git commit -m "Página de diagnóstico das execuções, a partir de Fontes (D45)"`.

### Task 4: A coleta registra (e a pasta de coleta nunca é reaproveitada)

**Files:**
- Modify: `slf/cli.py` (`coletar` dentro de `diagnostico.execucao("coleta")`), `slf/raw.py` (`Coleta.__init__`)
- Test: `tests/test_pipeline.py`, `tests/test_diagnostico.py`

**Interfaces:**
- Consumes: Tarefa 1.
- Produces: evento `erro` `coleta.fonte_falhou` (fonte, mensagem `"{tipo}: {mensagem}"` até 300 caracteres e "; vale a coleta anterior"; com `httpx.HTTPStatusError`, o corpo da resposta via `Execucao.resposta(f"{fonte}-resposta", ...)` e o nome em `arquivo`). O `sys.exit(1)` do `slf coletar` fica fora do contexto: fonte que falhou deixa a etapa `com_problemas`, não `falhou`.

- [ ] **Step 1: Testes que falham:**
  - `test_fonte_que_falha_vira_evento_e_as_outras_seguem`: com o `transferegov` levantando `httpx.HTTPStatusError` 500 de corpo `"<html>fora do ar</html>"`, as outras fontes ganham `_OK`; a execução fecha `com_problemas` com um evento `coleta.fonte_falhou` de fonte `transferegov` e um arquivo `transferegov-resposta.html`.
  - `test_coleta_no_mesmo_segundo_nao_reaproveita_pasta`: com `agora()` fixo, duas `Coleta("x")` têm pastas diferentes, a segunda terminando em `-2`; com as duas concluídas, `ultima_coleta_boa("x")` é a `-2`.
- [ ] **Step 2: Rodar e ver falhar:** `uv run pytest tests/test_pipeline.py tests/test_diagnostico.py -q`.
- [ ] **Step 3: Implementar** (`mkdir(exist_ok=False)` com sufixo `-2`, `-3`; o nome continua ordenando certo para `ultima_coleta_boa`, `podar` e a proveniência).
- [ ] **Step 4: Rodar e ver passar** (+ ruff).
- [ ] **Step 5: Commit:** `git commit -m "Coleta: fonte que falha vira evento de diagnóstico e pasta de coleta única (D45)"`.

### Task 5: Ponto 1, falha no PNCP

**Files:**
- Modify: `slf/coletores/pncp.py` (avisos na coleta), `slf/processar.py` (aviso ao usar coleta com falhas), `slf/core.sql` (`contratacao_direta` nula sem compra), `slf/regras/R07-contratacao-direta.yaml` (versão 2), `docs/metodologia.md` (seção da R07)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: Tarefa 1.
- Produces:
  - Coleta: avisos `pncp.compra_falhou` e `pncp.termos_falhou` (quantidade, CSV `pncp-compras-falharam.csv` / `pncp-termos-falharam.csv` com `chave, erro`).
  - Processar: aviso `pncp.coleta_com_falhas` (passo `staging`), lendo o `falhas.json` da coleta usada, com a frase de que esses contratos ficam fora da conta de licitação da R07.
  - `core.contrato.contratacao_direta` é `null` quando o contrato não tem compra no staging; a R07 v2 só conta contratos com `contratacao_direta is not null`, e o `resumo` diz quantos ficaram de fora. Procure outros usos de `contratacao_direta` (`slf/`, `front/src/`) e trate `null` como "não se sabe", nunca como "com licitação".

- [ ] **Step 1: Testes que falham:** `test_compra_que_falha_fica_fora_da_conta_de_licitacao`. Faça a compra de um contrato da fixture responder 404 (monkeypatch no `responder` do conftest) e anule a pausa de 30 s (`slf.coletores.pncp.time.sleep`). Depois:
  - o contrato tem `contratacao_direta is null`;
  - a evidência da R07 conta um contrato a menos;
  - a execução da coleta tem `pncp.compra_falhou` com quantidade 1 e o CSV com a chave;
  - a do processar tem `pncp.coleta_com_falhas`;
  - `{r["id"]: r["versao"] for r in regras}["R07"] == 2`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar** e atualizar a seção `### R07 · Contratação direta alta · versão 2` em `docs/metodologia.md` (o `test_metodologia_cobre_cada_regra_na_versao_atual` confere).
- [ ] **Step 4: Rodar e ver passar** (suíte inteira + ruff).
- [ ] **Step 5: Commit:** `git commit -m "PNCP: compra que falhou vira aviso e fica fora da conta de licitação da R07 (D45)"`.

### Task 6: Ponto 2, 404 no detalhe do pedido

**Files:**
- Modify: `slf/coletores/camara.py` (`_tramitacoes`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: Tarefa 1.
- Produces:
  - 404 vira registro `{"id", "nome", "data", "verificado_em": hoje, "sem_detalhe": True}`. Se havia situação anterior, `nome` e `data` são mantidos dela; senão, nulos.
  - Na `fila`, `sem_detalhe` vai junto dos parados; em `precisa`, ele só volta depois de `REVER_DIAS`.
  - 404 zera `falhas_seguidas` em vez de somar.
  - Avisos `camara.sem_detalhe` (quantidade) e, quando as 5 falhas seguidas param as consultas, `camara.detalhe_parou`.

- [ ] **Step 1: Teste que falha:** `test_404_no_detalhe_nao_trava_a_fila`. Chame `_tramitacoes` com um cliente falso:
  - a sequência é 6 pedidos sem situação que dão 404 (`httpx.HTTPStatusError` com resposta 404) e depois um pedido que responde;
  - o sétimo sai com `nome`;
  - os seis saem com `sem_detalhe: True` e `verificado_em` de hoje;
  - chamando de novo com esse resultado como `anteriores`, nenhum dos seis é consultado.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar e ver passar** (suíte inteira + ruff).
- [ ] **Step 5: Commit:** `git commit -m "Câmara: pedido sem detalhe (404) não trava a fila de situação (D45)"`.

### Task 7: O processar registra, e um valor estranho não para o banco (ponto 3)

**Files:**
- Modify: `slf/processar.py`, `slf/core.sql`, `slf/cli.py` (`atualizar --exigir-fontes`)
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: Tarefa 1.
- Produces:
  - `processar.atualizar(forcar: bool = False, proveniencia: Path | None = None, exigir_fontes: bool = False)` roda dentro de `diagnostico.execucao("processar")`.
  - Eventos do processar:
    - `processar.core_falhou` (erro, passo `core`, mensagem do DuckDB);
    - `processar.teste_falhou` (erro, passo `testes`, um por falha);
    - `processar.autor_sem_cadastro` (aviso, passo `avisos`, no lugar do `print` de `AVISOS`);
    - `processar.foto_nao_abriu` (aviso, passo `staging`);
    - `processar.fonte_sem_coleta` (erro, com `--exigir-fontes`: depois de trocar o banco, fonte sem coleta em `core.fonte` registra o erro e sai com 1, como o passo do workflow faz hoje);
    - `processar.valor_nao_converteu` (aviso, passo `core`, um por coluna, com a fonte da tabela de staging e o CSV `valores-que-nao-converteram-{tabela}-{coluna}.csv` com `valor, linhas`, até 1000 valores).
  - `processar.CONVERSOES: list[tuple[str, str, str]]` com `(tabela_de_staging, coluna, tipo_duckdb)` de cada conversão do `core.sql` que vira `try_cast`.
  - No `core.sql`, todo `cast(x as integer|bigint|date|timestamp|double)` sobre coluna de staging vira `try_cast`. O nome oficial do bairro vira padrão com os metacaracteres escapados (`regexp_replace(..., '([.^$*+?()\[\]{}|\\])', '\\\1', 'g')`). Os apelidos de `slf/bairros.yaml` continuam sendo expressões regulares de propósito.

- [ ] **Step 1: Testes que falham:**
  - `test_valor_estranho_vira_aviso_e_o_banco_sai`: uma proposição da fixture com `"ano": "2O25"`. O `atualizar()` não levanta, o banco existe e há o aviso `processar.valor_nao_converteu` com quantidade 1 e o CSV contendo `2O25`.
  - `test_bairro_com_parentese_nao_quebra_o_core`: um bairro `Vila (Centro` na fixture e uma ementa "no bairro Vila (Centro". O `atualizar()` não levanta e o pedido fica ligado a esse bairro.
  - `test_teste_duro_que_falha_fecha_processar_como_falhou`: com um `TESTES_DUROS` extra que sempre falha (monkeypatch), `SystemExit`; a execução fecha `falhou` com `processar.teste_falhou`, e o banco anterior continua.
  - `test_exigir_fontes_registra_fonte_sem_coleta`.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar e ver passar** (suíte inteira + ruff).
- [ ] **Step 5: Commit:** `git commit -m "Processar: eventos de diagnóstico e valor que não converte não para o banco (D45)"`.

### Task 8: Ponto 4, regra que falha fica como estava

**Files:**
- Modify: `slf/sinais.py` (`rodar`), `slf/consultas.py` (`proveniencia`), `slf/pacote.py` (LEIAME)
- Test: `tests/test_pipeline.py`, `tests/test_pacote.py`

**Interfaces:**
- Consumes: Tarefa 1.
- Produces:
  - Em `rodar`, as ocorrências de uma regra que falhou são copiadas do banco anterior **como estavam** (sem trocar `ativo`). A cópia de "inativas que sumiram" passa a excluir as regras que falharam.
  - Erro `regra.falhou` (passo `regras`): `"regra {id} falhou; os casos dela ficam como estavam na publicação anterior: {erro}"`.
  - Na `proveniencia()`, cada regra listada em `sinais.erro` ganha `"mantida_do_banco_anterior": true` e `"desde": "<data de referência do banco anterior>"`. O LEIAME do pacote ganha uma linha por regra mantida.

- [ ] **Step 1: Testes que falham:** `test_regra_que_falha_mantem_os_casos`.
  - Monte o banco (fixture `banco`) e guarde os ids ativos da R05.
  - Troque o SQL da R05 por `select quebrado` (monkeypatch em `sinais.carregar_regras`) e rode `processar.atualizar()` de novo.
  - Os mesmos ids continuam ativos e `sinais.erro` tem a R05.
  - A execução tem `regra.falhou`, a proveniência marca a R05 e o LEIAME a cita.
- [ ] **Step 2: Rodar e ver falhar.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Rodar e ver passar** (suíte inteira + ruff).
- [ ] **Step 5: Commit:** `git commit -m "Sinais: regra que falha mantém os casos e a proveniência avisa (D45)"`.

### Task 9: Os workflows

**Files:**
- Modify: `.github/workflows/coleta.yml`, `.github/workflows/processar.yml`, `.github/workflows/publicar.yml`

**Interfaces:**
- Consumes: CLI das Tarefas 1, 2 e 7 (`slf diagnostico registrar|fechar-abertas|podar|publicar`, `slf atualizar --exigir-fontes`).

- [ ] **Step 1: Os três workflows.**
  - `env: SLF_DIAGNOSTICO: diagnostico` (fora de `data/`, para não entrar no cache `dados-`).
  - No começo, `actions/cache/restore` de `diagnostico` (key `diagnostico-${{ github.run_id }}`, restore-keys `diagnostico-`).
  - No fim, com `if: always()`:
    - `uv run slf diagnostico fechar-abertas --motivo "o job terminou com ${{ job.status }}"`;
    - `uv run slf diagnostico podar`;
    - `actions/cache/save` do mesmo caminho.
- [ ] **Step 2: `processar.yml`.**
  - Gatilho: depois da coleta em qualquer conclusão (o filtro de repositório continua); o CI continua exigindo `success`.
  - O passo "Toda fonte tem coleta" sai: o "Montar o banco" passa a `uv run slf atualizar --exigir-fontes`, e a frase de hoje no `GITHUB_STEP_SUMMARY` continua num passo `if: failure()`.
  - O passo "Sem dados no cache" registra `processar.sem_dados_no_cache` com `slf diagnostico registrar` (o `uv sync` vem antes dele).
  - Os dois `slf conferir` já abrem execução `conferir` sozinhos (Tarefa 2).
- [ ] **Step 3: `publicar.yml`.**
  - Roda quando o `processar` concluiu com `success` ou `failure` (a guarda `PUBLICAR_PAGES` continua).
  - Com `failure`, o front vem do último site publicado:
    - `actions/cache/restore` de `site-commit/commit.txt` (key `site-${{ github.run_id }}`, restore-keys `site-`);
    - um segundo `actions/checkout` desse commit em `antigo/`;
    - o build roda em `antigo/front`;
    - sem o cache, usa o commit do run.
  - O `slf` vem sempre do commit atual: `setup-uv` e `uv sync --locked`, como no processar.
  - Depois de copiar o pacote para `site/data`, roda `uv run slf diagnostico publicar --saida site/data/diagnostico`.
  - Publicar que dá certo com o `processar` em `success` grava `site-commit/commit.txt` e salva o cache `site-`.
  - Um passo `if: failure()` registra `publicar.falhou` ("o site não foi atualizado; veja o log do run") e salva o cache `diagnostico-`.
- [ ] **Step 4: Verificar.**
  - Rodar `uv run python -c "import sys, yaml; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" .github/workflows/*.yml`.
  - Rodar `actionlint` se estiver instalado (`which actionlint`); se não estiver, ler os `if:` de novo contra a [documentação de `workflow_run`](https://docs.github.com/actions/writing-workflows/choosing-when-your-workflow-runs/events-that-trigger-workflows#workflow_run).
  - A prova real (coleta à mão com `fontes = siconfi`, a mais rápida, e o site com a página) só depois do push. Disparar workflow é com o Ruan.
- [ ] **Step 5: Commit:** `git commit -m "Workflows: diagnóstico em cache, processar depois de qualquer coleta e publicar também na falha (D45)"`.

### Task 10: Documentação e prova ponta a ponta

**Files:**
- Modify: `docs/decisoes.md` (D45), `CLAUDE.md` (comandos `slf diagnostico ...`, `--exigir-fontes`, `SLF_DIAGNOSTICO`, linha de `slf/diagnostico.py` na arquitetura, página na lista de telas)

- [ ] **Step 1: D45** em `docs/decisoes.md`, no formato das outras: problema, decisão (as cinco mudanças da coleta e o diagnóstico), o que ficou de fora (Release; `core.sql` por fonte; teste "contrato com id repetido") e onde está no código.
- [ ] **Step 2: Prova local com os dados reais do Mac.**
  - Rodar `uv run slf atualizar` sobre `data/raw` (sem coletar).
  - Rodar `uv run slf diagnostico publicar --saida /tmp/diag-teste` e conferir que `indice.json` segue o contrato e que nenhum arquivo foi retido sem motivo.
  - Subir `uv run slf servir --host 127.0.0.1 --porta 8765` com `cd front && nvm use && npm run dev`.
  - Abrir `#/diagnostico` a 360 e 1280 px, claro e escuro: a execução do processar aparece, os arquivos baixam e a página não tem rolagem lateral.
- [ ] **Step 3: Suíte inteira, ruff e build do front** (o comando de verificação das Global Constraints).
- [ ] **Step 4: Commit:** `git commit -m "Docs: D45, diagnóstico das execuções e coleta mais segura"`.
