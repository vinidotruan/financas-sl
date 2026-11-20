# Aba Início com gráficos · design

Data: 19/11/2026. Aprovado pelo Ruan na conversa (escolheu o esboço A, "uma pergunta por cartão", e
aprovou a descrição completa sem mudanças). Esboços com dados reais na página de progresso, seção
"Aba inicial".

## Por quê

Quem abre o site cai hoje na aba Sinais, que está vazia no ar: os 200 sinais calculados esperam
revisão, e o modo público só mostra os revisados. O Ruan quer que a primeira tela responda, em 10
segundos, o que uma pessoa de São Leopoldo quer saber sobre o dinheiro da cidade, com "os gráficos em
primeiro lugar". As perguntas que ele trouxe: quem recebeu o maior salário da prefeitura no mês; qual
empresa mais recebeu dinheiro da prefeitura no mês e no ano; quais medidas estão paradas; e o que mais
eu sugerisse.

## Objetivos

1. Uma aba **Início**, a primeira da barra, com cartões em coluna. Cada cartão: uma pergunta como
   título, um número grande, um gráfico simples quando ajuda (barras horizontais ou uma barra de
   progresso) e um link para a tela de detalhe.
2. Uma fonte nova, **TCE-RS, despesa orçamentária por empenhos**, para responder "quem mais recebeu".
3. Fichas → Fornecedores passa a mostrar o **pago** (TCE-RS) ao lado do **contratado** (PNCP), ligando
   pelo CNPJ. O pago soma os mesmos órgãos do contratado que têm arquivo no TCE-RS (prefeitura, Câmara,
   SEMAE, Fundação Hospital Centenário), desde o início do ente. A lista ganha a ordem "por pago" além de
   "por contratado", e um filtro de órgão e ano usado pelo "Ver todas" do cartão 1. Empresa que só
   aparece no TCE-RS entra na lista e ganha ficha, com o contratado como "—", sem comentário (há
   pagamento legítimo sem contrato no PNCP: contrato anterior a 2023, compra pequena, tarifa). Pessoa
   física: "pessoa física", sem ficha, como hoje. Órgão público e banco aparecem na lista com um selo,
   e só ficam de fora do cartão 1.

## Os cartões, nesta ordem

1. **Quem mais recebeu da prefeitura em {ano}.** Só a prefeitura (58700), como diz o título. O ano é o
   completo mais recente na fonte (hoje, 2025). Número grande: o total pago pela prefeitura no ano, com a
   legenda "pagos no ano a empresas, pessoas e outros órgãos" (como no esboço aprovado). Barras: as 5
   empresas que mais receberam. Ficam de fora órgãos
   públicos e bancos, que recebem repasses e retenções da folha (instituto de previdência dos servidores,
   Caixa, Banco do Brasil, Fundação Municipal de Saúde e afins). Uma linha diz até que mês o TCE-RS tem o
   ano corrente. "Ver todas" leva a Fichas → Fornecedores já ordenada pelo pago da prefeitura naquele
   ano, para as 5 do cartão serem as 5 do topo.
2. **Quanto das emendas chegou à cidade.** Percentual transferido sobre indicado, barra de progresso,
   "R$ X transferidos de R$ Y indicados". Link para Emendas.
3. **Pedidos parados na Câmara.** Pedidos (providência e indicação) cuja situação na Câmara é de
   comissão ou de pauta e que estão nela há mais de 60 dias. "Encaminhado para o Executivo" não conta:
   é o último passo que a Câmara registra, e nenhuma fonte diz ainda se a prefeitura fez. Enquanto a
   situação não estiver completa (2.000 pedidos consultados por coleta, D38), o cartão diz quantos
   faltam conferir. Link para Pedidos.
4. **Partido que mais pediu obras e serviços.** Os 5 partidos com mais pedidos desde 2022. O partido é
   o **da época do pedido** (o que vem com o autor em cada proposição), nunca o de hoje: pôr um pedido na
   conta de um partido que o vereador não tinha seria o erro mais grave num ranking político. Um pedido
   conta uma vez por partido, mesmo assinado por dois vereadores do mesmo partido. Bancada conta para o
   partido dela; comissão e Mesa Diretora não contam.
5. **Bairros que mais pedem.** Os 5 bairros com mais pedidos.
6. **A folha da prefeitura está perto do limite?** Pessoal sobre a receita corrente líquida, do último
   quadrimestre, com as marcas de alerta (48,6%), prudencial (51,3%) e máximo (54%) da LRF. Link para
   Contas.
7. **Maior salário do mês: em breve.** Cartão tracejado, sem número. Diz que o portal da prefeitura só
   mostra a folha com login e que a folha virá por pedido de Lei de Acesso à Informação ou por download
   manual.

Rodapé do Início: link para **Fontes** (de onde vem cada dado), que sai da barra de abas.

## Barra de abas

Seis abas: **Início · Emendas · Pedidos · Fichas · Contas · Sinais**. Início vira a rota padrão (`#/`
e rota desconhecida). Sinais vai para o fim. Fontes continua existindo em `#/fontes`, com link no
rodapé do Início.

## Fonte nova: TCE-RS, despesa por empenhos

- Portal de dados abertos do TCE-RS (CKAN), conjunto "Despesa orçamentária por empenhos" por órgão e
  ano. Arquivo: `https://dados.tce.rs.gov.br/dados/municipal/empenhos/{ano}/{codigo}.csv.zip` (CSV em
  UTF-8 com BOM, vírgula, uma linha por operação: E empenho, L liquidação, P pagamento).
- Órgãos (códigos do TCE-RS, em `config/ente.yaml`): 58700 prefeitura, 58701 Câmara, 58702 SEMAE, 58704
  Fundação Hospital Centenário. A Fundação Municipal de Saúde não tem arquivo próprio no TCE-RS. O
  instituto de previdência (58706) **não** é coletado: o arquivo dele é quase todo benefício pago a
  aposentados e pensionistas (pessoa física, com CPF), e nenhuma tela usa.
- Anos: desde o `inicio` do ente (`config/ente.yaml`: 2022-01-01) até o ano corrente. Arquivo de ano fechado não muda; o do
  ano corrente é baixado de novo a cada coleta.
- Colunas que importam: `tipo_operacao`, `dt_operacao`, `nr_empenho`, `cd_credor`, `nm_credor`,
  `tp_pessoa`, `cnpj_cpf`, `historico`, `vl_empenho`, `vl_liquidacao`, `vl_pagamento`, `nr_licitacao`,
  `nr_contrato`, `ds_funcao`, `nome_orgao`.
- Atraso: o município manda os dados ao Tribunal com meses de atraso (em 19/11/2026, o arquivo de 2026
  ia só até 27/02/2026). A tela sempre diz até quando o dado vai.
- O CNPJ vem sem zeros à esquerda (Caixa aparece como `360305000104`): normalizar para 14 dígitos.
- **Pagamento conta no ano da data dele, lido do arquivo daquele ano.** O arquivo de um ano traz o
  histórico inteiro dos empenhos que andaram nele, inclusive pagamentos de anos anteriores (o de 2025 tem
  R$ 174,9 mi pagos em 2024): somar o arquivo todo conta dinheiro duas vezes. Valores com ponto decimal;
  há estorno com valor negativo, que entra na soma. CPF vem com 8 a 11 dígitos e CNPJ com 5 a 14 (sem os
  zeros à esquerda). Credor PJ com nome de MEI no formato novo ("12.345.678 NOME") é pessoa física, pela
  mesma regra do PNCP (D40): 66 linhas assim no arquivo de 2025 da prefeitura.
- Dados medidos (prefeitura, pagamentos datados em 2025): R$ 944,6 mi. Empresas que mais receberam:
  Green Card R$ 29,5 mi, IDEAS R$ 28,4 mi, Instaladora Elétrica Mercúrio R$ 24,7 mi, Construsinos R$ 17,4 mi,
  RGE Sul R$ 16,9 mi.

## Restrições (valem do projeto)

- **Dados sensíveis (D40).** O arquivo traz CPF inteiro de credor pessoa física. Pessoa física aparece
  como "pessoa física", sem nome nem CPF, em qualquer lista pública; o CPF nunca sai inteiro em modo
  nenhum. O histórico do empenho pode trazer nome e CPF: não vai para o modo público, ou passa pela
  limpeza. A `slf conferir` tem que passar; o pacote aberto (D43) inclui as tabelas novas pelas mesmas
  regras.
- **Uma fonte não segura as outras.** TCE-RS fora do ar: vale a última coleta boa; os cartões que
  dependem dela mostram a data do dado.
- **Raw imutável, manifest com sha256, proveniência (D43).** A coleta segue o padrão dos outros
  coletores; o processamento continua determinístico (mesma entrada, mesma saída).
- **Etapas separadas (D42).** A coleta do TCE-RS entra na coleta diária; o processar não coleta.
- **Linguagem neutra.** Nada de "fraude", "desvio", "corrupção" ou "irregular". "Parado" descreve a
  situação na Câmara, não acusa ninguém.
- **Visual sóbrio (D39).** Tokens de `tokens.css`, nos dois temas; os componentes novos ganham
  stories no Storybook. Celular primeiro (360px), sem rolagem lateral.
- **Só dado público, sem login (regra do projeto).** O portal da prefeitura (Thema GRP) exige login
  para folha e pagamentos: não usar.
- Dependências fixadas e publicadas há mais de duas semanas (D24).

## Risco a conferir primeiro

O `CLAUDE.md` descreve o TCE-RS como instável e atrás de Cloudflare. Os downloads de 19/11 foram feitos
do Mac e funcionaram. **A primeira entrega confere a coleta rodando no GitHub Actions.** Se o TCE-RS
bloquear o runner, parar e voltar ao Ruan: não contornar o bloqueio (regra do projeto), e o arquivo bruto
traz CPF, então não pode entrar pelo `inbox/` de um repositório público.

## Fora do escopo

- Maior salário (sem fonte aberta; entra depois por Lei de Acesso à Informação ou download manual).
- A visão "este mês" de pagamentos (o TCE-RS chega com meses de atraso).
- Se a prefeitura atendeu o pedido encaminhado (nenhuma fonte ainda).
- Obras paradas: a prefeitura não registra nenhuma no portal.

## Anti-objetivos

- Um painel que pareça acusar: os cartões descrevem, não julgam.
- Número sem data: todo cartão diz de quando é o dado.
- Lista de "quem mais recebeu" com órgãos públicos e bancos no topo, escondendo as empresas.

## Decidido pelo Ruan

- Esboço A (uma pergunta por cartão), na ordem acima, aprovada sem mudanças.
- TCE-RS para pagamentos; não usar o login do portal da prefeitura.
- O salário fica "em breve" até haver fonte por Lei de Acesso à Informação ou download manual.

## Minhas escolhas (aprovadas junto com a descrição)

- "Parado" = comissão ou pauta há mais de 60 dias.
- "Ver todas" do cartão 1 leva a Fichas → Fornecedores, com pago ao lado de contratado.
- Mesmos órgãos do PNCP que têm arquivo no TCE-RS; o instituto de previdência fica de fora.
- Depois da revisão do documento: partido da época do pedido, contado uma vez por partido; número grande
  do cartão 1 com a legenda do esboço; pago em Fornecedores pelos mesmos órgãos do contratado, com
  ordem "por pago" e filtro de órgão e ano; empresa só do TCE-RS entra com ficha; primeira entrega
  confere a coleta no Actions.
- Fontes sai da barra e vira link no rodapé do Início.

## Para quem constrói decidir

- Como reconhecer órgão público e banco entre os credores (lista em config, natureza jurídica, raiz de
  CNPJ ou combinação), desde que a regra fique escrita e testada.
- O formato das tabelas novas no `core` e da rota da API/exportação do Início.
- O desenho exato de cada cartão dentro do design system.
- A ordem das entregas, desde que cada uma vá ao ar sozinha.
