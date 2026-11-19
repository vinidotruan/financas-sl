# Metodologia

Como o painel chega a cada número e a cada sinal, como refazer as contas e como mostrar que uma regra
está errada. Vale para São Leopoldo e para qualquer cidade montada com o mesmo código
(`docs/replicar.md`).

## O que um sinal é, e o que não é

Sinal é um **ponto de atenção** calculado a partir de dados públicos: um caso que passou do limiar de
uma regra. Não é acusação nem conclusão. Cada regra diz o limiar, a base legal, o que pode explicar o caso
sem problema nenhum e como verificar. Um sinal só aparece no site depois de revisado por uma pessoa
(confirmado ou encaminhado), e a linguagem do painel é neutra: nunca "fraude", "desvio", "corrupção" ou
"irregular" perto de um nome.

## Do dado bruto ao sinal

1. **Coleta** (`slf coletar`, diária): cada fonte é baixada como veio, numa pasta datada que nunca é
   editada depois. Um `manifest.jsonl` guarda, de cada arquivo, a URL, os parâmetros, o número de linhas e
   o sha256. A pasta só vale quando a coleta termina inteira (`_OK`). Fonte fora do ar não segura as
   outras: vale a última coleta boa dela.
2. **Tratamento** (`slf atualizar`): o bruto vira tabelas (`staging`), as tabelas viram o modelo do painel
   (`core`, em `slf/core.sql`) e testes de dados barram o banco novo quando algo não fecha (id repetido,
   código de emenda fora do padrão, fonte com volume caído).
3. **Regras** (`slf/regras/*.yaml`): cada regra é um SQL sobre as tabelas `core`, com versão. Mudou o
   que a regra diz, sobe a versão.
4. **Revisão**: uma pessoa olha cada caso e marca novo, em análise, descartado, confirmado ou encaminhado.
   Descartado volta a "novo" se o valor observado mudar.
5. **Modo público e conferência** (D40): o que vai para a internet passa pelas regras de dados sensíveis
   (`slf/sensivel.py`) e por uma conferência que para a publicação se achar algo que pareça CPF, telefone,
   contato ou nome de dono de MEI.

## Resultado repetível (D43)

As mesmas coletas, com o mesmo commit do código, dão o mesmo resultado, byte a byte:

- **Data de referência** (`core.referencia`): a da coleta mais recente usada, não o dia em que o
  processamento roda. As regras usam `hoje()`, que devolve essa data.
- **Escolhas fixas**: quando um registro aparece com valores diferentes (o nome de um fornecedor que mudou
  de razão social, o partido de um vereador que trocou), vale o mais recente, com o próprio valor no
  desempate. Nada é escolhido ao acaso.
- **Ordem sem empate**: toda lista termina ordenada por um campo único.
- **Proveniência** (`data/proveniencia.json` no site e no pacote): o commit do código, a data de
  referência, a versão de cada regra e, de cada fonte, a coleta usada e o sha256 de cada arquivo bruto.

O teste `test_processar_de_novo_da_o_mesmo_resultado` processa duas vezes e compara a exportação inteira.

## Refazer as contas com o pacote de dados abertos

O pacote (Release do GitHub, `dados-abertos-AAAA-MM-DD.zip`) traz as tabelas tratadas em Parquet, em modo
público, e a proveniência. Para refazer os casos de todas as regras, com Python e DuckDB:

```python
import pathlib
import duckdb

con = duckdb.connect()
for p in sorted(pathlib.Path("tabelas").glob("*.parquet")):
    esquema, tabela = p.stem.split(".")
    con.execute(f"create schema if not exists {esquema}")
    con.execute(f"create view {esquema}.{tabela} as select * from '{p}'")
con.execute("create macro hoje() as (select data from core.referencia)")
for regra, versao, sql in con.execute("select id, versao, sql from sinais.regra order by id").fetchall():
    print(regra, f"v{versao}", len(con.execute(sql).fetchall()), "casos")
```

O resultado é o número de casos calculados de cada regra, revisados ou não; o site mostra só os revisados.
O teste `test_regras_refeitas_sobre_o_pacote_dao_os_mesmos_casos` garante que esse caminho chega aos
mesmos casos do banco. Em contratos de pessoa física o pacote não tem nome, CPF nem objeto, mas tem os
valores e as datas, que é o que as regras usam.

Para testar uma regra sua, escreva o SQL sobre as mesmas tabelas. Para propor uma regra ao projeto, crie um
`slf/regras/RNN-nome.yaml` com os campos das outras (limiar, base legal, o que pode explicar, como verificar)
e um teste com as fixtures.

## Refazer do zero com o código

Com o repositório: `uv run slf coletar`, `uv run slf atualizar` e `uv run slf exportar`. As fontes mudam
com o tempo (corrigem dados, publicam atrasado), então uma coleta nova não reproduz uma publicação antiga;
compare os sha256 da sua coleta com os da proveniência para saber se partiu do mesmo dado. Os dados brutos
não são publicados porque trazem CPF de fornecedor pessoa física.

## As regras

Para cada regra: o que ela testa, o limiar, o que pode explicar o caso sem problema e como mostrar que o
caso (ou a regra) está errado. O texto completo de cada uma está no YAML e em `sinais.regra`.

### R02 · Dinheiro de emenda parado · versão 2

- **Testa:** dinheiro de emenda que chegou à prefeitura e quase não andou.
- **Limiar:** transferido há mais de 180 dias e o último relatório de gestão entregue mostra menos de 10%
  executado. Plano sem relatório entregue fica para a R03.
- **Pode ser normal:** projeto e licitação de obra são lentos; a enchente de maio de 2024; relatório de
  gestão atrasado em relação ao gasto real.
- **Como refutar:** cronograma do plano de trabalho e situação das licitações ligadas à emenda. Se o
  dinheiro foi empenhado e pago (portal da prefeitura), o caso não se sustenta.

### R03 · Relatório de gestão ausente · versão 2

- **Testa:** prestação de contas da transferência especial que não foi entregue no prazo.
- **Limiar:** dinheiro transferido e nenhum relatório entregue depois de 30/06 do ano seguinte ao repasse,
  ou prazo do plano de trabalho vencido sem relatório final.
- **Pode ser normal:** a API atrasada em relação ao sistema do Transferegov; prazo prorrogado; relatório em
  elaboração; plano dispensado da análise (situação CONCLUIDO_NT_TCU).
- **Como refutar:** a interface do Transferegov e as listas do TCU e do STF de quem não prestou contas.

### R05 · Contrato emergencial prorrogado · versão 3

- **Testa:** contrato emergencial (Lei 14.133, art. 75, VIII) que foi prorrogado, o que a lei veda.
- **Limiar:** contrato emergencial com termo aditivo que altere a vigência. Apostilamento não conta.
- **Pode ser normal:** prorrogação dentro do teto de um ano; regime de calamidade (MP 1.221/2024 e Lei
  14.981/2024). A leitura do aditivo é feita pelo texto e pode errar.
- **Como refutar:** a justificativa de cada aditivo e se a licitação definitiva foi aberta.

### R06 · Licitação publicada depois de fechar · versão 1

- **Testa:** compra com disputa que só apareceu no PNCP depois do prazo de propostas.
- **Limiar:** primeira publicação no PNCP depois do encerramento das propostas (licitação ou dispensa com
  disputa; inexigibilidade fica de fora).
- **Pode ser normal:** o edital saiu em outro meio e o PNCP serviu só de registro posterior.
- **Como refutar:** a data de publicação no diário oficial do município e a plataforma da licitação.

### R07 · Contratação direta alta · versão 1

- **Testa:** órgão que contratou mais sem licitação do que com licitação no ano.
- **Limiar:** mais de 50% do valor contratado no ano sem licitação, por órgão.
- **Pode ser normal:** ano de calamidade (2024, enchente); fornecedor exclusivo.
- **Como refutar:** os maiores contratos diretos do ano e a justificativa de cada um.

### R08 · Aditivo acima do teto legal · versão 1

- **Testa:** contrato que cresceu além do limite de acréscimo da Lei 14.133 (art. 125).
- **Limiar:** valor global atual mais de 25% acima do valor inicial.
- **Pode ser normal:** reforma (teto de 50%); reajuste ou repactuação, que não contam no limite; valor
  inicial de uma parcela só; contrato por consumo ou demanda (energia, passagens, combustível).
- **Como refutar:** os termos aditivos e o objeto do contrato.

## Limites conhecidos

- As fontes atrasam e corrigem dados; o painel mostra a data da última coleta boa de cada uma.
- Algumas leituras são feitas pelo texto (o tema do pedido, se o aditivo mexe na vigência) e podem errar;
  a tela mostra o texto para conferir.
- Pessoa física aparece como "pessoa física": quem quiser ligar um caso a uma pessoa precisa ir à fonte.
- O agendamento do GitHub pode atrasar a coleta diária em horas.
