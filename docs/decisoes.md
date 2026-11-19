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

**Onde.** `sem_cpf` em `slf/sensivel.py` (D40); `core.contrato.pessoa_fisica` e `core.fornecedor.id` em
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

**Conferência com a análise de 18/11.** A análise contou "21 de 80 emergenciais com aditivo de prazo"
somando o art. 75, VIII e o regime de calamidade da enchente (MP 1.221/2024). Reproduzido em 19/11/2026:
81 contratos, 21 com aditivo de vigência, R$ 27,3 mi de valor inicial, os mesmos números. A R05 fica só
com o art. 75, VIII (18 na prefeitura, 22 com os outros órgãos), porque o regime de calamidade é
justamente uma das explicações do "pode ser normal se" da regra.

### D22 · R06: inclui dispensa com disputa · 18/11/2026 · vale

**Decisão.** A dispensa com disputa também exige aviso publicado antes das propostas (art. 75, § 3º), então
entra na regra; só inexigibilidade fica de fora. Decisão do Ruan em 18/11/2026.

**Ressalva para outras cidades.** Municípios de até 20 mil habitantes têm prazo de transição para o
PNCP (art. 176 da Lei 14.133). Lá a R06 precisa considerar essa transição.

---

### D30 · R08: contrato por consumo no "pode ser normal se" · 19/11/2026 · vale

**Problema.** Com o SEMAE e a Câmara, a R08 subiu de 3 para 25 casos. Vários são contratos por consumo
(energia elétrica, cartões de passagem), em que o valor global cresce com o uso e não por aditivo.

**Decisão.** A regra continua a mesma; o "pode ser normal se" passou a citar contrato por consumo ou
demanda. Quem revisa vê a explicação ao lado do número.

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

### D36 · Emendas por área numa pizza, com as categorias da fonte · 19/11/2026 · vale

**Decisão.** A tela Emendas mostra uma pizza do valor indicado por área, e a área é a função do
orçamento que o plano de ação informa no Transferegov (`codigo_descricao_areas_politicas_publicas_plano_acao`),
sem o código: "10-Saúde / 302-Assistência Hospitalar" vira "Saúde". Plano com mais de uma função fica
em "Mais de uma área", porque a fonte não diz quanto vai para cada uma; plano sem área fica em "Sem
área informada". Nenhum valor é dividido por estimativa. A pizza tem até 5 fatias com cor e "Outras";
a legenda lista as áreas que estão dentro de "Outras", para nenhuma categoria da fonte sumir. As cores
ficam presas às 5 maiores áreas de todas as emendas, para o filtro de ano não repintar uma área com a
cor de outra. Ao lado, dois cartões com o indicado por cargo (deputados federais e senadores).

**Alternativas.** Barras ordenadas mostrariam as 13 áreas sem agrupar e comparariam melhor valores
próximos; o Ruan preferiu a pizza, mais fácil de ler de relance.

### D39 · Design system no Storybook, visual sóbrio · 19/11/2026 · vale

**Decisão.** Os componentes de `front/src/componentes` e os fundamentos (cores, tipografia, cartões)
ficam documentados no Storybook 10.6.5 (`@storybook/preact-vite`, versão fixa, publicada há mais de
duas semanas, como D24 pede), nos temas claro e escuro, pela barra do próprio Storybook. Sem telemetria.
O build vai junto com o site em `/storybook/` (os dois workflows de publicação) e o CI confere que ele
compila. A foto de exemplo é um boneco neutro, sem rosto de ninguém.

**Direção visual, escolhida pelo Ruan.** Visual sóbrio: base cinza neutra, dois temas, e cor só com
motivo: o número principal de cada tela, os gráficos e os estados dos sinais. A hierarquia vem do
tamanho e do peso do texto. Antes dessa, três direções foram descartadas: verde forte (cartões
preenchidos), marca-texto (azul-tinta com grifo amarelo) e Rio dos Sinos (faixa azul-petróleo no topo).

**Entregas.** 1) Storybook com o que existe hoje; 2) cores por função no visual sóbrio; 3) escala de
texto; 4) o site usando só as variáveis.

### D40 · Dados sensíveis: um módulo para esconder e conferir · 19/11/2026 · vale

**Problema.** A revisão de 19/11 achou no ar dois MEIs com o nome do dono. Desde 2023 a Receita monta o
nome do MEI como "raiz do CNPJ + nome do dono" ("12.345.678 FULANO DE TAL"), e a regra só conhecia o
formato antigo, com o CPF no fim. Achou também contato de morador no texto de pedidos e o objeto de
contrato de pessoa física passando inteiro no modo público. As regras de privacidade estavam espalhadas
e nada conferia o que ia para a internet.

**Decisão.** Um módulo de dados sensíveis, pedido pelo Ruan, em micro entregas: 1) MEI nos dois formatos
e pessoa física decidida por fornecedor (basta um contrato denunciar o dono para todos esconderem o
nome); 2) contato e casa de morador no texto dos pedidos (o endereço do lugar do serviço fica, o número
sai quando o texto liga o endereço a uma casa ou a um morador); 3) uma conferência de tudo o que vai
para o site antes de publicar, com uma lista de falsos positivos aprovada pelo Ruan; 4) objeto de
contrato de pessoa física.

**Conferência (`slf conferir`).** Roda depois da exportação nos dois workflows de publicação. Se achar algo
que pareça dado sensível (CPF inteiro ou mascarado, telefone, "Solicitante:"/"Contato:", nome de MEI,
número de casa de morador no texto do pedido), **a publicação para** e o site fica na versão anterior
(decisão do Ruan). O relatório vai para o log público do GitHub, então mostra só a forma do trecho
(dígitos viram #, nomes viram iniciais) e uma chave (sha1 do texto). Falso positivo entra em
`config/sensivel-liberados.yaml` pela chave, com o motivo.

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
pedido, não o que foi feito (a situação na Câmara, D38, é o andamento dentro da Câmara).

### D38 · Situação do pedido na Câmara, coletada aos poucos · 19/11/2026 · vale

**Problema.** O pedido não tem valor (nenhum campo da API, e só 1 de 10.555 ementas cita um), mas o
detalhe de cada um (`/proposicao/{id}`) traz o último passo de tramitação na Câmara. A lista não traz
esse passo, e o `updated_at` da proposição não muda quando entra tramitação nova: é uma consulta por
pedido, meio segundo cada, mais de hora e meia para todos.

**Decisão.** A coleta da Câmara consulta no máximo 2.000 pedidos por vez (`SLF_CAMARA_TRAMITACOES`) e
reaproveita o resto da coleta anterior (`tramitacoes.json`, com a data em que cada um foi visto).
Ordem: os pedidos sem situação, do mais novo ao mais antigo; os que ainda andam na Câmara (comissão,
pauta, parecer), sempre; os parados ("Encaminhado para o Executivo", "Arquivado"), uma vez por mês. Só a
coleta diária consulta; o processar e o publicar (D42) não coletam nada. Cinco falhas
seguidas param as consultas daquela coleta. A tela do vereador mostra "Na Câmara: passo em data".

**Limite.** O passo é da Câmara, não diz se a prefeitura atendeu: 87% de uma amostra de 60 estava em
"Encaminhado para o Executivo", inclusive pedidos de 2022. A cobertura completa leva uns 6 dias de
coleta diária; até lá, parte dos pedidos aparece sem situação.

---

## Cadastro de parlamentares

### D34 · Nome e cargo pelo cadastro de cada casa legislativa · 19/11/2026 · vale

**Problema.** O nome de quem indicou a emenda saía de cada consulta (`any_value` sobre os planos de
ação) e o de quem assinou o pedido, de uma expressão que tirava o "Ver." do nome. Nenhuma das duas
fontes diz o cargo: no ranking de pedidos, uma comissão aparecia como se fosse vereador.

**Decisão.** Um cadastro por casa, coletado da fonte oficial, e o cargo junto:

- **Federais.** Fonte nova `congresso`: `/deputados` da Câmara dos Deputados, por legislatura (e a
  mesma consulta com `siglaSexo=F`, porque a lista não traz o sexo), e
  `/senador/lista/legislatura/{inicio}/{fim}` do Senado. `core.parlamentar` casa o autor do
  Transferegov pelo nome sem acento e sem caixa, contra todas as grafias que o cadastro já registrou
  para a pessoa (a Câmara guarda "Tenente Coronel Zucco" e "Zucco" para o mesmo deputado). Com dois
  cadastros de mesmo nome, fica o da UF da cidade e depois o da legislatura mais recente. Quem não casa
  fica com o nome do Transferegov, sem cargo, e o `slf atualizar` avisa. Conferido em 19/11/2026: os 18
  autores de São Leopoldo casaram (15 deputados, 3 senadores), nenhum com homônimo.
- **Câmara municipal.** `/parlamentares` do Legiflow traz o cargo (Vereador, Vereadora) de quem está no
  mandato atual. Quem já saiu não aparece ali; o cargo vem do tratamento no nome ("Ver.ª" é vereadora).
  Comissão, bancada, Mesa Diretora e Executivo saem do começo do nome. Tudo fica em `core.vereador`.

O tratamento do nome acontece uma vez, nessas duas tabelas; as consultas e as telas leem o nome pronto.
Cadastro vazio deixa a coleta sem `_OK` e vale a anterior (D05).

**Alternativas.** Arquivo de nomes e cargos mantido à mão (simples, mas desatualiza sem aviso e não tem
fonte para conferir); casar pelo código de autor (o do Transferegov vem do sistema de orçamento e não
existe nos cadastros da Câmara e do Senado); Portal da Transparência (a API exige chave cadastrada por
e-mail).

**Limite conhecido.** O cargo é o do cadastro mais recente, não o da data da emenda: quem foi deputado e
virou senador aparece como senador. O partido dos federais fica de fora, porque a Câmara repete o
deputado por partido sem data e o painel poderia mostrar um partido que não era o da época.

**Onde.** `slf/coletores/congresso.py`, `slf/coletores/camara.py`; `core.parlamentar` e `core.vereador`
em `slf/core.sql`; selo `ChipCargo` em `front/src/componentes/pecas.tsx`.

### D37 · Foto oficial, copiada na coleta e publicada reduzida · 19/11/2026 · vale

**Problema.** Dois nomes parecidos (como "Johnson Souza" e "Diógenes Padilha de Souza (Johnson)") não
bastam para saber quem é quem. A foto ajuda a reconhecer.

**Decisão.** A coleta da Câmara usa `/parlamentares?all` (o cadastro de todas as legislaturas, que o
próprio site da Câmara usa fora da documentação) e baixa a `url_foto` de cada vereador para o raw, como
veio, com linha no manifest. Foto que falha não derruba a coleta. O `atualizar` gera em `data/fotos`
uma cópia reduzida (até 160 px, JPEG) de cada foto do raw; `staging.fotos` lista o que existe e o core
liga a foto à pessoa (`vereador-{id}.jpg`). A API serve e a exportação copia só as fotos que alguma
tela usa. Quem não tem foto na fonte aparece com as iniciais. Efeito do `?all`: quem já saiu do
mandato passa a ter cargo e partido da fonte, não do "Ver." no nome.

A coleta `congresso` faz o mesmo para deputados (a `urlFoto` do cadastro) e senadores (a foto oficial,
`senadores/img/fotos-oficiais/senador{codigo}.jpg`), mas só para quem é da UF da cidade, para não
baixar as quase mil fotos da Câmara a cada coleta. Autor de emenda de outra UF aparece com as iniciais.
Nomes: `camara-{id}.jpg` e `senado-{codigo}.jpg`.

**Por que copiar e não apontar para a fonte.** O site não quebra se o endereço mudar, a foto do Senado
cai de até 330 KB para uns 7 KB e quem visita o site não carrega nada dos sites do governo.

**Dados conferidos em 19/11/2026.** 49 vereadores no cadastro, 46 com foto; dos que assinam
proposições, 32 têm foto. A API manda pelo menos um endereço com espaço no começo (tratado). No
Congresso, 54 fotos do RS (3 suplentes do Senado sem foto oficial); os 18 autores de emenda têm foto.

---

## Publicação

### D31 · Dados entre execuções no cache do Actions, não em release · 19/11/2026 · vale

**Problema.** O runner do GitHub Actions começa vazio. Para o histórico de sinais (primeira vez visto)
continuar e para valer a "última coleta boa" de uma fonte que falhou, o banco e o raw precisam passar
de uma execução para outra. O plano original era uma release fixa com o banco como asset.

**Decisão.** `data/` vai para o cache do Actions (`actions/cache`, chave nova a cada execução e
restauração pela mais recente). O raw do PNCP traz CPF inteiro de fornecedor pessoa física: numa
release, que fica pública se o repositório ficar público, isso republicaria os CPFs (D03). O cache só é
lido pelos workflows do próprio repositório.

**Consequência.** O cache some depois de 7 dias sem uso. Com a coleta diária ele se renova; se o
workflow parar por mais de uma semana, a próxima execução recomeça do zero e perde a data em que cada
sinal apareceu pela primeira vez.

### D32 · Poda do raw no Actions · 19/11/2026 · vale

**Decisão.** No Actions, `slf podar --manter 2` apaga coletas antigas, mantendo as 2 últimas boas de
cada fonte, para o cache não crescer todo dia. Nada é editado (D05): só coletas inteiras saem. No Mac
o raw fica inteiro.

### D33 · Publicar é uma chave, e só em modo público · 19/11/2026 · vale

**Decisão.** O workflow de coleta sempre coleta, monta, exporta e guarda os dados. Publicar no GitHub
Pages depende da variável de repositório `PUBLICAR_PAGES = true`. O site sai sempre de
`slf exportar --modo publico`. A revisão vem de `config/revisao-publica.json`, gerado no Mac por
`slf revisao-publica`, que copia só id e status dos sinais confirmados ou encaminhados, sem nota. A
exportação apaga a pasta de saída antes, para não sobrar arquivo de sinal que deixou de ser público.

**Situação.** Repositório público e site no ar em https://vinidotruan.github.io/financas-sl/ desde
19/11/2026, por decisão do Ruan. Antes de abrir, o histórico inteiro foi varrido: só CPFs de exemplo,
nenhum segredo, nada de `data/`. A primeira coleta no GitHub levou cerca de 2 horas (o PNCP responde
devagar para máquinas fora do Brasil), dentro do limite de 3 horas do workflow.

### D35 · Publicação rápida a cada push, sem refazer a coleta inteira · 19/11/2026 · substituída por D42

**Problema.** O site só mudava na coleta diária, que leva cerca de 2 horas por causa do PNCP. Uma
mudança de tela ou de regra esperava até o dia seguinte para ir ao ar.

**Decisão.** O workflow `publicar.yml` roda quando o CI termina verde num push para `main` (ou à mão).
Parte dos dados da última coleta diária no cache, recoleta só as fontes rápidas (Câmara e Congresso),
remonta o banco, exporta em modo público e publica. Leva minutos. Não salva o cache: quem guarda os
dados entre execuções continua sendo a coleta diária. Usa o mesmo grupo de concorrência dela, para as
duas nunca publicarem ao mesmo tempo. Fonte rápida fora do ar não segura a publicação: vale a última
coleta boa dela.

**Consequência.** Entregas pequenas vão ao ar no mesmo dia. Se o cache estiver vazio (mais de 7 dias
sem coleta diária), a publicação rápida falha de propósito em vez de publicar um site sem dados.

### D42 · Coletar, processar e publicar em etapas separadas · 19/11/2026 · vale

**Problema.** Cada publicação refazia tudo: recoletava Câmara e Congresso, remontava o banco, rodava as
regras, exportava e montava o front, mesmo para mudar um texto da tela. E a coleta diária fazia as três
coisas num workflow só, então nenhuma etapa podia ser repetida sozinha.

**Decisão (pedido do Ruan).** Três workflows encadeados, ligados pelo cache do Actions:
1. `coleta.yml` (diária, 06:10): só baixa os dados brutos de todas as fontes e guarda em `dados-`.
2. `processar.yml`: depois da coleta e depois do CI verde num push para `main`. Monta o banco a partir da
   última coleta boa de cada fonte, roda as regras, exporta em modo público, confere os dados sensíveis
   (D40) e guarda o **pacote de dados públicos** (`pacote-`, com o commit que o gerou) e o banco
   (`banco-`, de onde vem o histórico dos sinais). No push, só reprocessa se mudou `slf/`, `config/`,
   `pyproject.toml` ou `uv.lock` desde o commit do pacote anterior.
3. `publicar.yml`: depois do processar. Monta o front e o Storybook com o último pacote e publica.

Coletar e processar dividem o grupo de concorrência `dados` (nunca processa durante a coleta); publicar
tem o seu (`pages`). Os dados brutos continuam só no cache, porque têm CPF (D31).

**Consequência.** Mudança só de tela vai ao ar sem reprocessar. O pacote de dados é a peça que a etapa
seguinte (resultado repetível, com o pacote numa Release do GitHub) vai publicar.

### D43 · Resultado repetível: as mesmas coletas dão o mesmo resultado · 19/11/2026 · vale

**Problema.** Para alguém aplicar método científico nos dados (refazer as contas, testar outra regra,
usar em outra cidade), o mesmo ponto de partida tem que dar o mesmo resultado. Não dava: as regras R02 e
R03 e a data dos sinais usavam o dia em que o processamento rodava; 25 `any_value` no SQL escolhiam
qualquer linha no empate (o nome de um fornecedor com dois nomes podia trocar de uma rodada para outra);
e listas com valores empatados (dois parlamentares com o mesmo valor indicado) saíam em ordem diferente.

**Decisão (pedido do Ruan).**
- **Data de referência** (`core.referencia`): a data da coleta mais recente usada. As regras usam `hoje()`
  no lugar de `current_date`, e os sinais gravam essa data. Processar de novo em outro dia, sobre as
  mesmas coletas, dá o mesmo resultado.
- **Escolhas fixas** no lugar de `any_value`: o nome, o partido ou o tipo do registro mais recente
  (`arg_max` por data, com o próprio valor no desempate); `min` quando o valor é o mesmo em todas as linhas.
- **Toda ordenação termina num campo único** (id, código), para empate não trocar a ordem.
- Conferido nos dados reais: processar duas vezes dá os mesmos 563 arquivos, byte a byte.
- **Proveniência** em cada publicação (`data/proveniencia.json`, também em `/api/proveniencia`): o commit do
  código, a data de referência, a versão de cada regra e, de cada fonte, a coleta usada com o sha256, a
  URL e os parâmetros de cada arquivo bruto (vem do manifest, gravado em `core.arquivo_coleta`).

- **Pacote de dados abertos** (`slf pacote`, `slf/pacote.py`): as tabelas tratadas em Parquet, em modo
  público, com a proveniência e um LEIAME. Pessoa física sem nome, CPF ou objeto; pedidos limpos (D40);
  só os sinais revisados; e CPF nenhum, nem mascarado (o representante da empresa aparece com CPF no texto
  de aditivos). Fica de fora `core.proposicao`. Passa pela `slf conferir`, que também lê Parquet. Rodar o
  SQL das regras sobre o pacote dá os mesmos casos do banco (teste e `docs/metodologia.md`).
- **Release do GitHub** (escolha minha; o Ruan não escolheu entre ela e o Zenodo, que pode arquivar cada
  release com DOI depois): uma por data de referência, `dados-AAAA-MM-DD`, criada pelo processar, só com
  `PUBLICAR_RELEASE = true`. **Ligada pelo Ruan em 19/11/2026**, sabendo que, com as tabelas abertas,
  qualquer pessoa recalcula também os casos ainda não revisados (o site mostra só os revisados). Primeira:
  `dados-2026-11-19`, conferida de fora: passa na `slf conferir` e refaz os mesmos casos.
- **`docs/metodologia.md`**: o caminho do dado bruto ao sinal, como refazer as contas e, para cada regra, o
  que testa, o limiar, o que pode explicar e como refutar. Um teste confere que cada regra, na versão
  atual, está lá.

---

## Em aberto

- **Coleta incremental do PNCP.** Hoje cada execução busca de novo a compra e os termos de todos os
  contratos (cerca de 2 horas no GitHub, perto do limite de 3). Reaproveitar o que não mudou (pela data de atualização do contrato)
  cortaria o tempo e os minutos do Actions.
- **dbt-duckdb.** Quando o core passar de uns 40 modelos.
- **Fontes novas.** Cadastro de CNPJ, sanções, TCE-RS e emendas estaduais nas fases seguintes.
- **Vereador com dois cadastros.** A Câmara tem "Ver. Johnson Souza" (id 777, 13 pedidos) e "Ver.
  Diógenes Padilha de Souza (Johnson)" (id 778, 256 pedidos), que parecem a mesma pessoa. Juntar exige
  confirmação e um arquivo de equivalências; por ora aparecem separados.
- **Atendimento dos pedidos.** Ver se a Câmara ou a prefeitura publicam a resposta a cada pedido de
  providência, para mostrar o que foi pedido e o que foi feito.
