# Diagnóstico das execuções e coleta mais segura · design

Data: 19/11/2026. Descrição aprovada pelo Ruan na conversa, sem mudanças. Ele pediu que a página seja
construída por outros agentes. O que está marcado como **decisão minha** foi escolha minha, não dele.

## Por quê

Hoje o que dá errado em cada etapa só aparece no log do GitHub Actions (ou no terminal do Mac) e não
fica guardado em lugar nenhum. Exemplos do código atual:

- coletor que falha: `slf/cli.py` imprime o erro e segue para a próxima fonte;
- compra ou termo aditivo do PNCP que falhou na segunda tentativa: vai para `falhas.json` dentro da
  coleta (`slf/coletores/pncp.py`), que ninguém lê;
- regra de sinal que falha: vai para `sinais.erro` no banco e os sinais dela somem do site;
- teste de dados que barra o banco, fonte sem coleta, conferência de dados sensíveis que trava a
  publicação: só no log e no resumo do run.

A revisão de 19/11 (artefato de progresso) também apontou cinco pontos em que a coleta falha calada ou
uma fonte derruba as outras. O Ruan quer que **desenvolvedores consultem o que deu errado e em qual
etapa**, baixando os logs, os dumps e os erros, em JSON ou no formato que for melhor para cada tipo de
dado.

## Objetivos

1. Cada etapa registra o que deu errado num formato estruturado, com a etapa, a fonte e o motivo.
2. Uma página do site lista as execuções dos **últimos 30 dias** com os arquivos para baixar, **mesmo
   quando a etapa falhou e travou a publicação**.
3. Os cinco pontos da coleta mais segura corrigidos, cada um gerando o registro do item 1.

## Não objetivos

- Gráfico, alerta por e-mail ou notificação, busca. A página é uma lista com links.
- Os 6 menores da revisão final da aba Início, o teste "contrato com id repetido" que nunca falha
  (`processar.py`, o SQL já tira as duplicatas antes), modo privado e navegação. Ficam na fila.
- Mudar a ordem coleta → processar → publicar (D42) ou a regra do "último dado bom".
- Isolar o `core.sql` por fonte (rodar um bloco por fonte). O ponto 3 abaixo resolve o caso apontado sem
  essa reforma (**decisão minha**).

## Anti-objetivos (falhou mesmo funcionando)

- CPF inteiro, nome de pessoa física ou qualquer dado sensível num arquivo de diagnóstico publicado.
  Vale a regra de sempre: tudo o que vai para a internet sai em modo público.
- O diagnóstico travar a publicação dos dados. Ele nunca para o site.
- O diagnóstico sumir justamente quando a etapa falhou.
- Texto de tela ou de evento com "fraude", "desvio", "corrupção" ou "irregular".

## Etapas e o que cada uma registra

As etapas têm nomes fixos: `coleta`, `processar`, `conferir`, `publicar`. O `passo` detalha dentro da
etapa quando ajuda (ex.: `staging`, `core`, `testes`, `avisos`, `regras` no processar).

| Etapa | Erro (parou a etapa ou a fonte) | Aviso (seguiu, mas algo ficou incompleto) |
|---|---|---|
| coleta | coletor de uma fonte levantou exceção (vale a coleta anterior); volume caiu (Câmara, Congresso) | compras e termos do PNCP que falharam; pedidos da Câmara sem detalhe (404); 5 falhas seguidas no detalhe |
| processar | fonte sem nenhuma coleta; teste duro ou queda de volume que barra o banco; `core.sql` que abortou; regra de sinal que falhou | `AVISOS` de hoje (autor sem cadastro); valores que não converteram (ponto 3); foto que não abriu; PNCP com falhas na coleta usada (ponto 1) |
| conferir | dado sensível no export ou no pacote (trava a publicação, como hoje) | arquivo de diagnóstico retido pela conferência |
| publicar | build do front ou do Storybook falhou | |

Limitação aceita: uma falha do `publicar` só aparece na página na próxima publicação que der certo
(o próprio publicar é quem põe a página no ar). O link do run no Actions continua valendo.

## Formatos

| O quê | Formato | Por quê |
|---|---|---|
| Erros e avisos | `eventos.jsonl`, um evento por linha | dá para acrescentar ao longo da etapa e ler com `jq` ou pandas |
| Log da etapa | `{etapa}.log`, texto puro | é o que o terminal mostrou |
| Linhas que causaram o problema | CSV (UTF-8, cabeçalho, vírgula) | tabela; abre em planilha |
| Resposta inesperada da fonte | o corpo como veio, extensão pelo tipo (`.html`, `.json`, `.txt`, `.bin`) | é a prova do que a fonte mandou |

Campos de um evento:

```json
{"quando": "2026-11-20T06:42:10-03:00", "etapa": "coleta", "passo": null, "fonte": "pncp",
 "tipo": "aviso", "codigo": "pncp.compra_falhou",
 "mensagem": "3 compras do PNCP não vieram nem na segunda tentativa; os contratos delas ficam fora da conta de licitação",
 "quantidade": 3, "arquivo": "pncp-compras-falharam.csv"}
```

`quando` no fuso da cidade (`config/ente.yaml`). `tipo` é `erro` ou `aviso`. `codigo` é um
identificador curto e estável (o construtor escolhe os nomes). `fonte`, `passo`, `quantidade` e
`arquivo` são opcionais.

**Decisões minhas:** resposta original limitada a 1 MB e qualquer arquivo a 5 MB (o excesso é cortado
e o corte vira aviso); a pasta de diagnóstico publicada fica abaixo de 50 MB, apagando as execuções
mais velhas primeiro se passar.

## Onde fica e como vai ao ar

- **Local:** `data/diagnostico/{execucao}/` (dentro de `data/`, fora do git). `execucao` é
  `{AAAA-MM-DDTHHMMSS}-{etapa}`, no fuso da cidade, uma pasta por execução de etapa. Roda igual no
  Mac (`slf diario`) e no Actions.
- **Índice:** `data/diagnostico/indice.json`, refeito ao fim de cada etapa (contrato abaixo), com poda
  das execuções de mais de 30 dias.
- **Actions:** cada workflow fecha a pasta da sua etapa e guarda o diagnóstico num cache `diagnostico-`
  acumulado (o mesmo esquema de `restore-keys` dos caches `dados-` e `banco-`), em passos com
  `if: always()`, para sair também quando a etapa falha. Cada execução leva o link do seu run no
  Actions (o repositório é público, o log também).
- **Publicação (decisão minha):** o `publicar` passa a rodar também quando o `processar` falhou. Nesse
  caso ele monta o site com o último pacote bom (cache `pacote-`, que só é salvo depois da conferência)
  e com o **front do último site publicado**, não o do commit que falhou; só o diagnóstico é novo. Para
  isso, todo publicar que dá certo guarda o commit do front num cache `site-` (o `pacote/commit.txt`
  não serve: num push só de tela o pacote fica no commit antigo e o front vai do commit novo, e voltar
  ao commit do pacote desfaria a tela no ar). Assim os dados e as telas ficam como estavam e a página
  mostra a falha. O diagnóstico vai para `site/data/diagnostico/`. Quando o processar dá certo, nada
  muda em relação a hoje. Limitação aceita: se o primeiro processar depois desta entrega falhar, o
  último site publicado ainda não tem a página; ela aparece na primeira publicação que der certo.
- **Coleta que falha no workflow (decisão minha):** timeout de 180 min (o PNCP já leva cerca de 2
  horas), cancelamento ou `uv sync` quebrado deixam a coleta sem `success`, e hoje o processar não roda.
  O processar passa a rodar depois da coleta em qualquer conclusão, com a última coleta boa de cada
  fonte, que é a regra de sempre. A ordem das etapas (D42) não muda, só o gatilho.
- **Por que não numa Release (decisão minha):** a página não conseguiria listar os arquivos de uma
  Release (o download da Release não libera leitura por outro site), e uma Release por dia de
  diagnóstico se misturaria às de dados abertos.

## Privacidade (D40 aplicada ao diagnóstico)

1. Quem grava evento, dump ou log mascara na hora: documento de pessoa física nunca inteiro, nome de
   pessoa física (inclui MEI) vira "pessoa física", pelas mesmas funções de `slf/sensivel.py`.
2. Antes de ir para o cache publicado, a pasta passa pelo `slf conferir`, que hoje só lê `.json` e
   `.parquet` e precisa passar a ler `.jsonl`, `.csv`, `.log`, `.txt` e `.html`.
3. Arquivo com achado **não é publicado**: no lugar dele entra um aviso `conferir.arquivo_retido` com o
   nome do arquivo e só a forma do trecho (como o relatório de hoje). O resto sai. O diagnóstico nunca
   trava o site.
4. Arquivo bruto do TCE-RS (traz CPF inteiro) nunca entra como "resposta original"; só o corpo de uma
   resposta de erro.
5. Os falsos positivos usam o mesmo `config/sensivel-liberados.yaml`.

## Os cinco pontos da coleta mais segura

Cada um com um teste que falha antes da correção.

1. **Falha no PNCP não avisa ninguém.** O processar lê o `falhas.json` da coleta usada e registra um
   aviso por etapa (compra, termos) com o CSV das chaves que falharam. Contrato cuja compra não veio
   fica **fora da conta de licitação** da R07 (nem com, nem sem licitação), em vez de contar como "com
   licitação". A R07 sobe de versão (o teste da metodologia confere a versão). A R05 não tem como ver
   aditivo que não veio: fica só o aviso.
2. **404 no detalhe do pedido trava a fila da Câmara.** 404 vira "sem detalhe": o pedido ganha
   `verificado_em`, sai da frente da fila, volta a ser consultado depois de `REVER_DIAS` como os
   parados, e **não conta** como falha seguida. Outros erros continuam contando. Aviso com a
   quantidade.
3. **Um valor estranho para o banco inteiro.** As conversões estritas do `core.sql` passam a ser
   tolerantes (`try_cast`), e o processar conta, por coluna, os valores não nulos que não converteram:
   aviso com o CSV dessas linhas (mascarado). Nome de bairro usado como expressão regular passa a ser
   escapado. Se o `core.sql` ainda abortar por outro motivo, vira erro com a mensagem, e o banco
   anterior continua valendo, como hoje.
4. **Regra que falha some calada.** As ocorrências de uma regra que falhou **ficam como estavam** no
   banco anterior (ativas continuam ativas), em vez de virarem inativas e sumirem do site. Erro
   `regra.falhou` com o id da regra e a mensagem. A tabela `sinais.erro` continua. Como essas
   ocorrências não saem das coletas da publicação, refazer pela proveniência (D43) não as reproduz:
   a `proveniencia.json` e o LEIAME do pacote marcam a regra como "mantida do banco anterior", com a
   data, e a Release sai normalmente (**decisão minha**).
5. **Duas coletas no mesmo segundo escrevem na mesma pasta.** A pasta de uma coleta nunca é
   reaproveitada: se já existir, ganha sufixo `-2`, `-3` (**decisão minha**). A ordem por nome continua
   certa para `ultima_coleta_boa`, `podar` e a proveniência (D43).

## A página (vai para os agentes)

- Rota `#/diagnostico`, link no fim da tela **Fontes** ("Diagnóstico das execuções, para
  desenvolvedores"). Fora da barra de abas; a aba acesa é a mesma da tela Fontes.
- Conteúdo: execuções dos últimos 30 dias, da mais nova para a mais antiga. Em cada uma: etapa,
  data e hora, situação (`ok`, `com_problemas`, `falhou`), link para o run no Actions, os eventos
  (tipo, fonte, passo, mensagem, quantidade) e os arquivos para baixar com o tamanho. Filtro por etapa.
  Sem execução: "Nenhuma execução registrada ainda."
- Mesmo sistema visual do site (tokens, componentes que já existem, história no Storybook para
  componente novo), celular primeiro, funciona em 360 px, tema claro e escuro.
- Camada de dados de sempre (`front/src/dados.ts`): no site estático, `data/diagnostico/indice.json` e
  os arquivos em `data/diagnostico/{execucao}/{arquivo}`; na API local (`slf servir`), uma rota que
  serve o mesmo índice e os mesmos arquivos.
- Os agentes podem começar pela fixture do contrato, sem esperar o backend.

## Contrato do índice

```json
{
  "gerado_em": "2026-11-20T08:03:00-03:00",
  "dias": 30,
  "execucoes": [
    {
      "id": "2026-11-20T061003-coleta",
      "etapa": "coleta",
      "inicio": "2026-11-20T06:10:03-03:00",
      "fim": "2026-11-20T08:02:41-03:00",
      "situacao": "com_problemas",
      "commit": "98b1de3",
      "url_actions": "https://github.com/vinidotruan/financas-sl/actions/runs/0000000000",
      "contagem": {"erro": 0, "aviso": 1},
      "eventos": [
        {"quando": "2026-11-20T06:42:10-03:00", "etapa": "coleta", "passo": null, "fonte": "pncp",
         "tipo": "aviso", "codigo": "pncp.compra_falhou",
         "mensagem": "3 compras do PNCP não vieram nem na segunda tentativa; os contratos delas ficam fora da conta de licitação",
         "quantidade": 3, "arquivo": "pncp-compras-falharam.csv"}
      ],
      "arquivos": [
        {"nome": "eventos.jsonl", "tipo": "eventos", "bytes": 412},
        {"nome": "coleta.log", "tipo": "log", "bytes": 40211},
        {"nome": "pncp-compras-falharam.csv", "tipo": "dump", "bytes": 233,
         "descricao": "chaves das compras que falharam"}
      ]
    }
  ]
}
```

- `situacao`: `falhou` quando a etapa parou; `com_problemas` quando houve erro de uma fonte ou aviso e
  a etapa seguiu; `ok` sem nenhum evento.
- `tipo` do arquivo: `eventos`, `log`, `dump`, `resposta`.
- `url_actions` e `commit` são nulos numa execução local.
- **Decisão minha:** no índice vão até 50 eventos por execução; a lista inteira fica no
  `eventos.jsonl`.

## O que fica para quem constrói

Nomes de funções e de comandos (algo como `slf diagnostico` para fechar a pasta de uma etapa e refazer
o índice), como capturar o log de cada etapa (`tee` no workflow ou no próprio `slf`), os códigos dos
eventos, o desenho exato da página e os textos de tela, em linguagem neutra.

## Documentação junto

D45 em `docs/decisoes.md` (diagnóstico e os cinco pontos), a versão nova da R07 em
`docs/metodologia.md`, o comando novo no `CLAUDE.md`, e o artefato de progresso.
