# Como montar este painel para outra cidade

O código não cita São Leopoldo: a cidade entra por `config/ente.yaml`. O que muda de um município para
outro são os endereços de algumas fontes. A lógica de escolha de cada fonte é a mesma, e é ela que este
guia explica, para você achar o equivalente na sua cidade quando a fonte não for nacional.

## Os critérios para escolher uma fonte

Em ordem de peso:

1. **Oficial e primária.** Quem gera o dado, não quem republica. Agregador serve para achar a fonte
   primária, não para substituí-la.
2. **Nacional quando existe.** Uma API que cobre todos os municípios do mesmo jeito funciona para
   qualquer cidade sem código novo. Só se usa fonte local para o que não existe no nível nacional.
3. **Aberta.** Sem login e sem burlar bloqueio. Quando a fonte é uma página, vale ler o JSON que a
   própria página recebe (é o mesmo dado que qualquer visitante vê); quando ela bloqueia, o arquivo é
   baixado à mão e colocado em `inbox/`.
4. **Tem uma chave que liga a outras fontes.** CNPJ do órgão, código IBGE, código da emenda (12
   dígitos), número de controle do PNCP. Dado sem chave fica solto e não vira rastro.
5. **Data conhecida.** Toda coleta guarda quando foi feita, e a tela mostra a data do último dado bom.
6. **Duas fontes para o mesmo número entram as duas.** O painel mostra lado a lado (como o rastro da
   emenda: indicado e transferido no Transferegov, empenhado e pago no portal da prefeitura). Diferença
   entre fontes é informação, não erro a esconder.

## As fontes, pela pergunta que cada uma responde

| Pergunta | Fonte | Alcance | Chave | Na sua cidade |
|---|---|---|---|---|
| Quanto de emenda Pix foi indicado e transferido? | Transferegov, transferências especiais (API PostgREST) | Nacional | CNPJ do município, código da emenda | Igual. Só muda o CNPJ |
| Como estão as contas da prefeitura (pessoal, receita, despesa)? | SICONFI, RGF e RREO (API do Tesouro) | Nacional | Código IBGE | Igual. Só muda o IBGE |
| Quem a prefeitura contratou, como e com quais aditivos? | PNCP, consulta de contratos, compras e termos | Nacional (obrigatório pela Lei 14.133) | CNPJ de cada órgão, número de controle | Igual, mas a **lista de órgãos** é sua (veja abaixo) |
| Quanto da emenda foi empenhado e pago, e a quem? | Portal de transparência do município | Municipal | Código da emenda, CNPJ/CPF do credor | **Muda.** Depende do sistema do portal (fase 2) |
| Quem pediu obra, placa, limpeza, poda? | Sistema legislativo da Câmara (indicações e pedidos de providência) | Municipal | Vereador, bairro | **Muda.** Depende do sistema da Câmara |
| Quem é a empresa e ela tem sanção? | Cadastro de CNPJ (Receita) e CEIS/CNEP/CEPIM (CGU) | Nacional | CNPJ | Igual (fase 3) |
| O que o tribunal de contas viu? | TCE do seu estado | Estadual | CNPJ, IBGE | **Muda** por estado (fase 4) |
| Emendas de deputados estaduais | Assembleia ou governo do estado | Estadual | Varia | **Muda** por estado (fase 4) |

## Passo a passo

### 1. A configuração da cidade

```yaml
# config/ente.yaml
nome: Sua Cidade
uf: XX
ibge: 0000000              # código de 7 dígitos (IBGE ou a lista de entes do SICONFI)
cnpj_municipio: "00000000000000"   # CNPJ da prefeitura, só dígitos
inicio: 2022-01-01         # de quando em diante coletar
orgaos_pncp:               # órgãos que publicam compras no PNCP (passo 2)
  - cnpj: "00000000000000"
    nome: Prefeitura Municipal de Sua Cidade
```

O CNPJ da prefeitura aparece no próprio Transferegov: procure o município em
`https://api.transferegov.gestao.gov.br/transferenciasespeciais/plano_acao_especial?nome_beneficiario_plano_acao=ilike.*SUA CIDADE*&limit=5`.

### 2. A lista de órgãos do PNCP

Prefeitura, fundações, autarquias (água e esgoto, previdência), consórcios e Câmara podem ter CNPJ
próprio e publicar separado. Para achar:

1. `https://pncp.gov.br/api/pncp/v1/orgaos/?razaoSocial=<nome da cidade>&pagina=1` lista os órgãos com o
   nome da cidade. Procure também por siglas (SEMAE, DMAE, SAAE) e por "fundação", que nem sempre trazem
   o nome da cidade.
2. Para cada CNPJ, `https://pncp.gov.br/api/pncp/v1/orgaos/<cnpj>/unidades` mostra as unidades e o
   município. Só entra quem tem unidade na sua cidade. Órgão sem unidade nunca publicou no PNCP: deixe
   comentado no arquivo.

### 3. Rodar e conferir à mão

```bash
uv sync && (cd front && npm install && npm run build)
uv run slf diario && uv run slf status
```

Antes de confiar nos sinais, confira três números na fonte original, como foi feito para São Leopoldo
(ver `docs/decisoes.md`):

- quantos planos de ação por ano e o total indicado (Transferegov);
- o total transferido de uma emenda que você conhece;
- um contrato emergencial e os aditivos dele no site do PNCP.

Se não bater, a diferença costuma estar numa regra de soma (D11 em `docs/decisoes.md`) ou numa coleta
com falhas (`data/raw/pncp/<coleta>/falhas.json`).

### 4. Fontes municipais

Aqui o endereço muda, mas o jeito de procurar é o mesmo:

- **Portal de transparência.** Descubra o sistema (aparece no rodapé: Thema, IPM, Betha, Fiorilli,
  GovBR e outros). Abra a página de despesas com as ferramentas do navegador e veja de onde vem o JSON
  que a tabela usa. Se a página pede token, ele vem da própria página, sem login. Se o portal exige
  login ou bloqueia, use `inbox/`.
- **Câmara.** Muitas câmaras usam o SAPL, da Interlegis, que tem API aberta padrão
  (`/api/materia/materialegislativa/`). São Leopoldo usa o Legiflow: o site busca as proposições em
  `https://api.<dominio da camara>/proposicoes`, com filtros `ano`, `id_bairro`, `limit` e `offset`. Se a
  sua Câmara só publica PDF, os pedidos entram por `inbox/`.

### 5. O que não muda

- **As regras de sinal.** Elas se apoiam em lei federal (Lei 14.133, LRF, IN-TCU 93/2024), que vale para
  todo município. Só a R06 pede cuidado em cidade de até 20 mil habitantes, que tem prazo de transição
  para o PNCP (art. 176).
- **A privacidade.** Máscara de CPF, MEI como pessoa física e modo público valem para qualquer cidade.
- **A arquitetura.** Raw imutável, última coleta boa, banco trocado só com os testes de dados passando.

## Antes de publicar

- [ ] Os três números do passo 3 batem com a fonte original.
- [ ] `uv run pytest` passa.
- [ ] Nenhum sinal foi publicado sem revisão: o site público sai com `slf exportar --modo publico`.
- [ ] Você leu o "pode ser normal se" de cada regra pensando na sua cidade (enchente, calamidade, obra
      grande) e ajustou o texto se for o caso.
