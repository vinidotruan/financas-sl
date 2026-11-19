# Decisões técnicas

Registro das decisões que moldam o painel, para quem quiser auditar o que ele faz e por quê. Cada
decisão diz o problema, o que foi escolhido, o que ficou de fora e onde está no código. Quando uma
decisão muda, a antiga fica aqui marcada como substituída, com a data.

Formato: **Dnn · título** · data · situação (vale, substituída, em aberto).

Os números citados vêm da coleta de 18/11/2026.

---

## Princípios

### D01 · Só dados públicos, sem login e sem contornar bloqueio · 18/11/2026 · vale

**Problema.** Várias fontes úteis exigem login, ficam atrás de Cloudflare ou mudam de formato sem aviso.

**Decisão.** O painel só lê o que qualquer pessoa lê sem se identificar. Não automatiza login, não
contorna bloqueio e não força acesso. Quando uma fonte bloqueia, o caminho é baixar o arquivo à mão e
colocar na pasta `inbox/`.

**Consequência.** Algumas fontes ficam de fora ou entram com atraso (portal da prefeitura na fase 2,
TCE-RS e painéis estaduais na fase 4). Em troca, qualquer pessoa consegue refazer a coleta.

### D02 · Linguagem de sinal, nunca de acusação · 18/11/2026 · vale

**Problema.** Um indicador acima do limiar não prova nada. Num estudo da CGU, 76,4% dos alertas do
sistema de risco ALICE foram julgados improcedentes.

**Decisão.** Tela, README, commits e documentos falam em "sinal", "ponto de atenção" e "indicador acima
do limiar". Nunca "fraude", "desvio", "corrupção" ou "irregular" junto de nome de pessoa ou empresa.
Todo sinal mostra a regra, o limiar, a base legal, a data do dado, a fonte e o "pode ser normal se".

**Onde.** Campos obrigatórios em `slf/sinais.py` (`CAMPOS_REGRA`); rodapé em todas as telas do front.

### D03 · Privacidade: CPF nunca inteiro, pessoa física protegida · 18/11/2026 · vale

**Problema.** Contratos com pessoa física trazem CPF. MEI e empresário individual aparecem como PJ, mas
a razão social costuma terminar no CPF do dono ("FULANO DE TAL 12345678901"): 9 fornecedores e 12
contratos em São Leopoldo.

**Decisão.**
- Toda resposta da API (e todo arquivo exportado) passa por uma máscara que troca qualquer CPF por
  `***.456.789-**`, em qualquer modo. A máscara reconhece 11 dígitos seguidos ou o formato
  `123.456.789-01`, desde que não estejam colados em letra ou dígito, para não estragar ids em hash,
  códigos de emenda (12 dígitos) e CNPJ (14).
- O fornecedor é identificado por um id curto (`left(md5(ni), 12)`), nunca pelo CPF, em links e nomes
  de arquivo.
- MEI e empresário individual contam como pessoa física quando o nome termina em 11 dígitos. É uma
  heurística até a fase 3 trazer a natureza jurídica do cadastro de CNPJ.
- Endereço de pessoa física nunca entra.

**Onde.** `sem_cpf` em `slf/consultas.py`; `core.contrato.pessoa_fisica` e `core.fornecedor.id` em
`slf/core.sql`; testes em `tests/test_privacidade.py` e `tests/test_api.py`.

**Histórico.** A primeira versão da máscara (só "11 dígitos sem dígito colado") trocava trechos dos ids
de sinal, que são hash hexadecimal, e quebrava os links. Corrigida em 19/11/2026.

### D04 · Modo público e modo privado · 18/11/2026 · vale

**Problema.** O painel serve para o Ruan revisar sinais e, talvez, para ser publicado.

**Decisão.** `SLF_MODO=publico` mostra só sinais com status `confirmado` ou `encaminhado`, esconde a
nota da revisão, mostra pessoa física (inclusive MEI) como "pessoa física", não tem ficha de pessoa
física e só busca contratos pelo objeto (buscar pelo nome confirmaria quem é a pessoa). Tudo que for
publicado na internet sai em modo público. A revisão só existe no modo privado com a API local.

**Onde.** Classe `Consulta` em `slf/consultas.py`; `podeRevisar` em `front/src/dados.ts`.

---

## Coleta e armazenamento

### D05 · Raw imutável, com manifest · 18/11/2026 · vale

**Problema.** Para auditar um número é preciso saber exatamente o que a fonte respondeu e quando.

**Decisão.** Cada coleta grava as respostas como vieram em `data/raw/{fonte}/{AAAA-MM-DDTHHMMSS}/`, com um
`manifest.jsonl` (url, parâmetros, linhas, bytes, sha256, horário). Nada em `data/raw` é editado:
correção de dado se faz no staging ou no core. Falhas que sobram depois das tentativas ficam em
`falhas.json` dentro da própria coleta.

**Onde.** `slf/raw.py`.

### D06 · Última coleta boa por fonte · 18/11/2026 · vale

**Problema.** As APIs do governo ficam lentas ou fora do ar.

**Decisão.** Uma coleta só vale quando termina e grava `_OK`. O banco é montado com a última coleta boa
de cada fonte, então uma fonte que falha não apaga nem trava as outras. A tela de Fontes mostra a data
do último dado bom de cada uma.

**Onde.** `ultima_coleta_boa` em `slf/raw.py`; `try` por coletor em `slf/cli.py`.

### D07 · Repetir o que falhou e registrar o motivo · 18/11/2026 · vale

**Problema.** Na primeira coleta real, 34 consultas de compra do PNCP falharam e o coletor descartava o
erro. 43 contratos ficaram sem modalidade e contaram como "com licitação".

**Decisão.** O cliente HTTP repete em 429, 5xx e timeout (até 5 vezes, espera exponencial). O que ainda
falha ganha uma segunda tentativa no fim da coleta, e o que sobra vai para `falhas.json` com o motivo.
Um erro HTTP sem corpo é erro, não "sem dados": o status é checado antes do corpo vazio (só o 204 é
"sem dados").

**Onde.** `slf/http.py`; `_cada_um` em `slf/coletores/pncp.py`.

### D08 · DuckDB e SQL puro · 18/11/2026 · vale (revisar perto de 40 modelos)

**Decisão.** Um arquivo DuckDB, com o core em SQL puro (`slf/core.sql`). dbt-duckdb fica para quando
passar de uns 40 modelos.

**Alternativas.** dbt-duckdb desde já (mais estrutura, mais dependência); Postgres (servidor a manter).

### D09 · O banco só é trocado se os testes de dados passarem · 18/11/2026 · vale

**Decisão.** O banco é montado num arquivo novo e trocado com `os.replace` só se passar nos testes
duros (ids repetidos, código de emenda fora do padrão) e se nenhuma tabela importante cair mais de 20%.
`slf atualizar --forcar` passa por cima, de propósito e à mão.

**Onde.** `TESTES_DUROS` e `testar` em `slf/processar.py`.

### D10 · Staging tolerante · 18/11/2026 · vale

**Decisão.** `processar.COLUNAS` lista as colunas que o core usa. Fonte vazia ou sem a coluna gera a
coluna como nula, então o core nunca quebra por falta de coluna. Joins entre ids usam
`cast(... as varchar)` porque o tipo inferido varia de uma coleta para outra.

---

## Fontes

### D11 · Transferido é o documento hábil com ordem bancária · 18/11/2026 · vale

**Problema.** No Transferegov a cadeia é plano de ação, empenho, documento hábil e ordem bancária.
Somar empenhos ou todos os documentos hábeis superestima o que chegou.

**Decisão.** Valor transferido = soma do `valor_dh` dos documentos hábeis que têm ordem bancária com
número; a data é a da ordem bancária. Conferido contra a análise manual: R$ 5.545.122,50 (a soma de
todos os documentos hábeis daria R$ 6.739.122,50).

**Onde.** `core.transferencia` em `slf/core.sql`.

### D12 · Relatório de gestão só conta se entregue · 18/11/2026 · vale

**Decisão.** Valores reais de `tipo_relatorio_gestao_novo`: `Final` e `Parcial`. Só conta como entregue
o relatório com situação `DISPONIBILIZADO`; `EM_ELABORACAO` é rascunho e aparece só na evidência.

### D13 · PNCP: limites da API e chave do registro · 18/11/2026 · vale

**Decisão.** Página de 500 (1000 dá erro 400), janela de até 365 dias (mais dá erro 422), consulta por
mês e por CNPJ do órgão. Os termos aditivos são buscados pelo ano e sequencial do `numeroControlePNCP`,
que podem diferir do `anoContrato`. A data de publicação usada é `dataPublicacaoPncp`, conferida no
histórico do PNCP como a primeira inclusão da compra.

### D14 · Órgãos do PNCP conferidos no cadastro · 18/11/2026 · vale

**Decisão.** Entram os órgãos com unidade cadastrada no PNCP e todas as unidades no município
(prefeitura, Fundação Hospital Centenário, Fundação Municipal de Saúde, SEMAE e Câmara). Órgãos sem
unidade cadastrada nunca publicaram lá e ficam comentados em `config/ente.yaml`.

### D15 · SICONFI pelo código de conta · 18/11/2026 · vale

**Decisão.** Pessoal sobre a RCL vem do RGF Anexo 01 do Poder Executivo pelo `cod_conta`
(`DespesaComPessoalTotal`, `ReceitaCorrenteLiquidaAjustada` e os três limites) e pela coluna
(`Valor` ou `% sobre a RCL Ajustada`), iguais nos 14 quadrimestres de 2022 a 2026. Receita e despesa do
ano vêm do RREO Anexo 01 (`TotalReceitas`, `TotalDespesas`), do último bimestre publicado.

---

## Regras de sinal

### D16 · Regra é um arquivo YAML com SQL e texto · 18/11/2026 · vale

**Decisão.** Cada regra é um arquivo em `slf/regras/` com id, nome, versão, área, severidade, base legal,
limiar, "pode ser normal se", como verificar, fontes e o SQL. Dois campos opcionais servem à tela:
`observado` (o que é o número e como formatar) e `resumo` (a frase do que foi visto, preenchida com
campos da evidência). Mudou o sentido da regra, sobe a versão.

### D17 · Ocorrência estável e histórico · 18/11/2026 · vale

**Decisão.** O id de uma ocorrência é `md5(regra|chave)`. A primeira data em que apareceu é guardada entre
execuções; a que some vira inativa, não é apagada. Um sinal descartado volta a "novo" se o valor
observado mudar. Por isso **o valor observado precisa ser estável**: um número que muda todo dia
(como "dias de atraso") reabriria todo descarte no dia seguinte. Dias e datas vão para a evidência.

**Onde.** `slf/sinais.py`.

### D18 · Revisão fora do banco · 18/11/2026 · vale

**Decisão.** Status e nota de cada sinal ficam em `data/revisao.json`, não no banco, e a API aplica na
hora. O banco pode ser refeito do zero sem perder a revisão. `data/` nunca vai para o git.

### D19 · R02: sem relatório não é 0% executado · 18/11/2026 · vale (R02 v2)

**Problema.** A v1 tratava plano sem relatório como 0% executado: 15 sinais, todos sem relatório.

**Decisão.** A R02 só dispara quando existe relatório entregue mostrando menos de 10% executado. Plano
sem relatório é assunto da R03. Aprovado pelo Ruan em 18/11/2026.

### D20 · R03: prazo do relatório parcial · 18/11/2026 · vale (R03 v2)

**Problema.** A v1 só olhava o prazo do plano de trabalho vencido sem relatório final.

**Decisão.** Também dispara quando nenhum relatório foi entregue até 30/06 do ano seguinte ao repasse
(30/06/2025 para repasses anteriores a 17/01/2024), conforme a IN-TCU 93/2024 (arts. 3º e 8º) e a Nota
Conjunta TCU/AGU/CGU/MGI 1/2025. O valor observado é o valor transferido (estável), não os dias de
atraso. Aprovado pelo Ruan em 18/11/2026.

**Inferência registrada.** A situação `CONCLUIDO_NT_TCU` do plano de trabalho parece indicar a dispensa
da análise do plano decidida pelo STF em 24/08/2025, não do relatório de gestão. Não achamos o código
documentado. Por isso esses planos continuam na regra, com a situação na evidência.

**Conferência.** Para descartar falha de coleta: no RS, 651 de 1.000 planos de 2024 têm relatório; em
São Leopoldo, 0 de 6.

### D21 · R05: só termo aditivo muda vigência · 18/11/2026 · vale (R05 v3)

**Decisão.** v2: apostilamento não conta (Lei 14.133, art. 136; caso real: troca de fiscal "durante o
prazo de férias" virava prorrogação). v3 (19/11/2026): o valor observado é o número de aditivos que
mudam a vigência, porque o valor acrescido numa prorrogação quase sempre é zero. A leitura do aditivo é
pelo texto (`prorroga|prazo|vigência|renova`), já que os campos de qualificação vêm vazios; os 18 casos
de 18/11/2026 foram lidos um a um.

### D22 · R06: inclui dispensa com disputa · 18/11/2026 · vale

**Decisão.** A dispensa com disputa também exige aviso publicado antes das propostas (art. 75, § 3º), então
entra na regra; só inexigibilidade fica de fora. Decisão do Ruan em 18/11/2026.

**Ressalva para outras cidades.** Municípios de até 20 mil habitantes têm prazo de transição para o
PNCP (art. 176 da Lei 14.133). Lá a R06 precisa considerar essa transição.

---

## Painel

### D23 · Um módulo de consultas para a API e para a exportação · 19/11/2026 · vale

**Decisão.** O conteúdo de cada rota sai de `slf/consultas.py`. A API (`slf/api.py`) e a exportação
estática chamam as mesmas funções, então o site publicado mostra exatamente o que a API mostra no mesmo
modo, com os mesmos filtros de privacidade. A API ainda aplica a máscara de CPF uma segunda vez na
resposta.

### D24 · Front leve, estático e sem terceiros · 19/11/2026 · vale

**Decisão.** Vite + Preact 10 + TypeScript, gerando arquivos estáticos em `site/` (cerca de 17 KB de
JavaScript com gzip). Uma camada de dados única lê a API local ou arquivos JSON, por configuração
(`VITE_DADOS`). Rotas no hash, para funcionar em qualquer hospedagem estática. Fontes (Archivo, Public
Sans, IBM Plex Mono) empacotadas no build, sem Google Fonts, para o site publicado não mandar dados de
quem visita a terceiros. Dependências com versão fixa e publicadas há mais de duas semanas.

**Alternativas.** Preact 11 e Vite 8 (mais novos, menos conhecidos por quem escreveu); JS puro (menos
estrutura para sete telas).

### D25 · Dinheiro em centavos nas somas · 19/11/2026 · vale

**Decisão.** Somas de valores são arredondadas em 2 casas no SQL e no Python, para o JSON não carregar
ruído de ponto flutuante (como `414134.66000000003`).

### D26 · A cidade vem da configuração · 19/11/2026 · vale

**Decisão.** Nome, UF, IBGE, CNPJ, data de início e órgãos ficam em `config/ente.yaml`. Código, regras e
front não citam o município. Ver `docs/replicar.md`.

---

## Pedidos dos vereadores

### D27 · Câmara pelo JSON que o próprio site usa · 19/11/2026 · vale

**Problema.** Quem pede obra, placa, limpeza ou poda à prefeitura são os vereadores, por pedido de
providência e indicação. A Câmara de São Leopoldo não tem SAPL; o site usa o sistema Legiflow.

**Decisão.** O coletor lê `https://api.camarasaoleopoldo.rs.gov.br/proposicoes`, o mesmo endereço que o
site da Câmara chama para qualquer visitante, sem login (D01). Conferido ao vivo: filtros `ano` e
`id_bairro`, página de até 100 (`limit` maior volta ao padrão de 10), sem filtro por espécie. Vem tudo
por ano e o core separa pedidos de providência e indicações. O endereço fica em `config/ente.yaml`;
cidade sem Câmara configurada pula a fonte sem erro.

**Onde.** `slf/coletores/camara.py`; `core.pedido`, `core.vereador`, `core.pedido_bairro` em `slf/core.sql`.

### D28 · Tema por palavra-chave, num arquivo legível · 19/11/2026 · vale

**Decisão.** O tema de cada pedido sai de expressões procuradas na ementa, em `slf/temas.yaml`. A
primeira regra que casa, na ordem do arquivo, decide; sem nenhuma, "Outros". A tela avisa que a
classificação pode errar.

**Alternativas.** Modelo de linguagem para classificar (melhor em casos ambíguos, mas cada resultado
fica difícil de explicar e de reproduzir); classificação manual (não escala para milhares de pedidos
por ano).

### D29 · Coautoria conta para cada um; bairro pelo filtro da API · 19/11/2026 · vale

**Decisão.** Pedido assinado por mais de um vereador conta no ranking de cada um (a tela avisa que a
soma pode passar do total). O bairro não vem na proposição: vem de consultar a API bairro por bairro.
Pedido sem bairro identificado aparece contado à parte, não some.

**Limite conhecido.** A API não traz se a prefeitura atendeu o pedido. O painel mostra o que foi
pedido, não o que foi feito.

---

## Em aberto

- **Publicação.** Pages aberto em modo público, ou Actions só coleta e o Mac serve em modo privado.
  Decidir antes da tarefa 4.
- **Persistência no GitHub Actions.** Release fixa, branch de dados ou cache.
- **dbt-duckdb.** Quando o core passar de uns 40 modelos.
- **Fontes novas.** Cadastro de CNPJ, sanções, TCE-RS e emendas estaduais nas fases seguintes.
- **Atendimento dos pedidos.** Ver se a Câmara ou a prefeitura publicam a resposta a cada pedido de
  providência, para mostrar o que foi pedido e o que foi feito.
