-- Core: entidades ligadas pelas chaves que as fontes compartilham.
-- d() e n() convertem com segurança: a fonte pode mandar texto, número ou nulo.
create or replace macro d(x) as try_cast(left(cast(x as varchar), 10) as date);
create or replace macro n(x) as coalesce(try_cast(x as double), 0);
create or replace macro so_digitos(x) as regexp_replace(cast(x as varchar), '[^0-9]', '', 'g');
-- Funções do orçamento citadas no plano, sem o código: "10-Saúde / 302-Assistência Hospitalar" vira
-- "Saúde". O Transferegov separa as áreas com " , " (o nome de subfunção pode ter vírgula).
create or replace macro funcoes_orcamento(x) as list_distinct(list_filter(list_transform(
  string_split(cast(x as varchar), ' , '),
  lambda f: regexp_replace(trim(split_part(f, '/', 1)), '^[0-9]+\s*-\s*', '')), lambda f: f <> ''));

-- ===== Emendas Pix (Transferegov) =====
create or replace table core.plano_acao as
select
  cast(id_plano_acao as bigint)                         as id_plano_acao,
  codigo_plano_acao                                     as codigo_plano,
  so_digitos(numero_emenda_parlamentar_plano_acao)      as codigo_emenda,
  -- como o portal da prefeitura mostra: 2026/42710013 (o "formatado" do Transferegov vem com o nome do autor)
  left(so_digitos(numero_emenda_parlamentar_plano_acao), 4) || '/'
    || substr(so_digitos(numero_emenda_parlamentar_plano_acao), 5) as codigo_formatado,
  cast(ano_plano_acao as integer)                       as ano,
  situacao_plano_acao                                   as situacao,
  motivo_impedimento_plano_acao                         as motivo_impedimento,
  nome_parlamentar_emenda_plano_acao                    as parlamentar,
  cast(codigo_parlamentar_emenda_plano_acao as varchar) as codigo_autor,
  n(valor_custeio_plano_acao)                           as valor_custeio,
  n(valor_investimento_plano_acao)                      as valor_investimento,
  n(valor_custeio_plano_acao) + n(valor_investimento_plano_acao) as valor_indicado,
  -- área: a função do orçamento. Com mais de uma, a fonte não diz quanto vai para cada uma.
  case coalesce(len(funcoes_orcamento(codigo_descricao_areas_politicas_publicas_plano_acao)), 0)
    when 0 then 'Sem área informada'
    when 1 then funcoes_orcamento(codigo_descricao_areas_politicas_publicas_plano_acao)[1]
    else 'Mais de uma área' end                       as area
from staging.tg_plano_acao_especial;

-- Cadastro dos autores das emendas. O Transferegov dá o código de autor e o nome, mas não o cargo; o
-- cargo vem do cadastro oficial da Câmara dos Deputados e do Senado (fonte "congresso"), casado pelo
-- nome sem acento e sem caixa. O casamento olha todas as grafias que o cadastro já registrou para a
-- pessoa (a Câmara guarda "Tenente Coronel Zucco" e "Zucco" para o mesmo deputado). Com dois cadastros
-- de mesmo nome, fica o da UF da cidade e depois o da legislatura mais recente. Quem não casa fica com
-- o nome do Transferegov e sem cargo.
create or replace macro chave_nome(x) as lower(strip_accents(trim(cast(x as varchar))));

create or replace table core.parlamentar as
with autor as (
  select codigo_autor, any_value(parlamentar) as nome_fonte
  from core.plano_acao where codigo_autor is not null group by 1
),
grafia as (
  select 'camara' as casa, cast(id as varchar) as id_casa, nome, max(cast(legislatura as integer)) as leg_nome
  from staging.cg_deputados where id is not null and nome is not null group by all
  union all
  select 'senado', cast(codigo as varchar), nome, max(cast(legislatura as integer))
  from staging.cg_senadores where codigo is not null and nome is not null group by all
),
pessoa as (
  select 'camara' as casa, cast(id as varchar) as id_casa,
         arg_max(uf, cast(legislatura as integer)) as uf, max(cast(legislatura as integer)) as legislatura,
         case when cast(id as varchar) in (select cast(id as varchar) from staging.cg_deputadas)
              then 'Deputada federal' else 'Deputado federal' end as cargo,
         'https://www.camara.leg.br/deputados/' || cast(id as varchar) as link
  from staging.cg_deputados where id is not null group by id
  union all
  select 'senado', cast(codigo as varchar), uf, cast(legislatura as integer),
         case when sexo = 'Feminino' then 'Senadora' else 'Senador' end, link
  from staging.cg_senadores where codigo is not null
)
select a.codigo_autor, coalesce(g.nome, a.nome_fonte) as nome, p.cargo, p.uf, p.casa, p.id_casa, p.link,
       a.nome_fonte
from autor a
left join grafia g on chave_nome(g.nome) = chave_nome(a.nome_fonte)
left join pessoa p on p.casa = g.casa and p.id_casa = g.id_casa
qualify row_number() over (partition by a.codigo_autor
                           order by (p.uf = (select uf from staging.ente)) desc nulls last,
                                    p.legislatura desc nulls last, p.casa, g.leg_nome desc nulls last) = 1;

create or replace table core.emenda as
select e.codigo_emenda, any_value(e.codigo_formatado) as codigo_formatado,
       any_value(coalesce(p.nome, e.parlamentar)) as parlamentar, any_value(p.cargo) as cargo_parlamentar,
       any_value(e.codigo_autor) as codigo_autor, min(e.ano) as ano, count(*) as planos,
       sum(e.valor_indicado) as valor_indicado
from core.plano_acao e left join core.parlamentar p using (codigo_autor)
group by e.codigo_emenda;

-- Empenho federal -> documento hábil -> ordem bancária: é a transferência que chegou ao município.
create or replace table core.transferencia as
with ob as (
  select id_dh, min(d(data_emissao_ob)) as data_ob, any_value(numero_ordem_bancaria) as numero_ob
  from staging.tg_ordem_pagamento_ordem_bancaria_especial
  where numero_ordem_bancaria is not null
  group by id_dh
)
select cast(e.id_plano_acao as bigint) as id_plano_acao, e.numero_empenho, dh.id_dh,
       ob.numero_ob, ob.data_ob, n(dh.valor_dh) as valor
from ob
join staging.tg_documento_habil_especial dh on cast(dh.id_dh as varchar) = cast(ob.id_dh as varchar)
join staging.tg_empenho_especial e on cast(e.id_empenho as varchar) = cast(dh.id_empenho as varchar);

-- Todos os relatórios. Valores reais (18/11/2026): tipo 'Final' ou 'Parcial'; situacao
-- 'DISPONIBILIZADO' (entregue) ou 'EM_ELABORACAO' (rascunho, ainda não conta como entregue).
create or replace table core.relatorio_gestao as
select cast(id_plano_acao as bigint) as id_plano_acao,
       d(data_e_hora_relatorio_gestao_novo) as data,
       tipo_relatorio_gestao_novo as tipo,
       situacao_relatorio_gestao_novo as situacao,
       coalesce(upper(situacao_relatorio_gestao_novo) = 'DISPONIBILIZADO', false) as entregue,
       try_cast(valor_executado_relatorio_gestao_novo as double) as valor_executado
from staging.tg_relatorio_gestao_novo_especial;

create or replace table core.prazo_plano as
select cast(id_plano_acao as bigint) as id_plano_acao,
       min(d(data_inicio_execucao_plano_trabalho)) as inicio,
       max(d(data_fim_execucao_plano_trabalho)) as fim,
       any_value(situacao_plano_trabalho) as situacao
from staging.tg_plano_trabalho_especial group by 1;

create or replace table core.meta as
select cast(x.id_plano_acao as bigint) as id_plano_acao, x.nome_executor as executor,
       x.objeto_executor as objeto, m.nome_meta, m.desc_meta
from staging.tg_executor_especial x
left join staging.tg_meta_especial m on cast(m.id_executor as varchar) = cast(x.id_executor as varchar);

-- Uma linha por plano com o funil que a tela de rastro mostra.
-- executado_relatorio é null quando não há relatório entregue: sem relatório não é o mesmo que 0%.
-- prazo_relatorio_parcial: IN-TCU 93/2024 (arts. 3º e 8º) e Nota Conjunta TCU/AGU/CGU/MGI 1/2025:
-- 30/06 do ano seguinte ao repasse; para repasses anteriores a 17/01/2024, 30/06/2025.
create or replace table core.rastro_plano as
select p.* replace (coalesce(pa.nome, p.parlamentar) as parlamentar), pa.cargo as cargo_parlamentar,
       coalesce(t.transferido, 0) as transferido, t.primeira_ob, t.ultima_ob,
       r.valor_executado as executado_relatorio, r.tipo as tipo_relatorio, r.data as data_relatorio,
       coalesce(q.relatorios_entregues, 0) as relatorios_entregues,
       coalesce(q.relatorios_em_elaboracao, 0) as relatorios_em_elaboracao,
       coalesce(q.tem_final, false) as tem_relatorio_final,
       case when t.primeira_ob is not null
            then make_date(greatest(year(t.primeira_ob) + 1, 2025), 6, 30) end as prazo_relatorio_parcial,
       z.inicio as prazo_inicio, z.fim as prazo_fim, z.situacao as situacao_plano_trabalho
from core.plano_acao p
left join (select id_plano_acao, round(sum(valor), 2) as transferido, min(data_ob) as primeira_ob,
                  max(data_ob) as ultima_ob
           from core.transferencia group by 1) t using (id_plano_acao)
left join (select * from core.relatorio_gestao where entregue
           qualify row_number() over (partition by id_plano_acao order by data desc nulls last) = 1
          ) r using (id_plano_acao)
left join (select id_plano_acao, count(*) filter (where entregue) as relatorios_entregues,
                  count(*) filter (where not entregue) as relatorios_em_elaboracao,
                  bool_or(entregue and lower(tipo) like '%final%') as tem_final
           from core.relatorio_gestao group by 1) q using (id_plano_acao)
left join core.prazo_plano z using (id_plano_acao)
left join core.parlamentar pa using (codigo_autor);

-- ===== Compras (PNCP) =====
create or replace table core.compra as
select id, so_digitos(orgao_cnpj) as orgao_cnpj, cast(ano as integer) as ano,
       cast(sequencial as integer) as sequencial, modalidade, modo_disputa, amparo, objeto,
       n(valor_estimado) as valor_estimado, try_cast(valor_homologado as double) as valor_homologado,
       try_cast(encerramento_propostas as timestamp) as encerramento_propostas,
       try_cast(publicado_em as timestamp) as publicado_em, situacao
from staging.pn_compras where id is not null;

create or replace table core.contrato as
select c.id, c.compra_id, so_digitos(c.orgao_cnpj) as orgao_cnpj, c.orgao_nome, c.unidade,
       cast(c.ano as integer) as ano, cast(c.sequencial as integer) as sequencial, c.tipo, c.categoria,
       c.processo, c.tipo_pessoa, so_digitos(c.fornecedor_ni) as fornecedor_ni, c.fornecedor_nome,
       -- MEI e empresário individual vêm como PJ, mas a razão social termina no CPF do dono
       -- ("FULANO DE TAL 12345678901"); contam como pessoa física. A fase 3 troca pela natureza jurídica.
       coalesce(c.tipo_pessoa = 'PF'
                or regexp_matches(coalesce(c.fornecedor_nome, ''), '(^|[^0-9])[0-9]{11}\s*$'), false)
         as pessoa_fisica,
       c.objeto, n(c.valor_inicial) as valor_inicial, n(c.valor_global) as valor_global,
       d(c.data_assinatura) as data_assinatura, d(c.vigencia_inicio) as vigencia_inicio,
       d(c.vigencia_fim) as vigencia_fim, try_cast(c.publicado_em as timestamp) as publicado_em,
       k.modalidade, k.amparo,
       coalesce(k.modalidade in ('Dispensa', 'Inexigibilidade')
                or k.amparo ilike '%art. 74%' or k.amparo ilike '%art. 75%', false) as contratacao_direta,
       coalesce(k.amparo ilike '%75, VIII%', false) as emergencial
from staging.pn_contratos c
left join core.compra k on k.id = c.compra_id
where c.id is not null
qualify row_number() over (partition by c.id order by c.publicado_em desc) = 1;

-- Os campos de qualificação do aditivo costumam vir vazios; o texto também é lido.
-- Só termo aditivo muda vigência: apostilamento serve pra reajuste e registros (Lei 14.133, art. 136)
-- e costuma citar "prazo" sem prorrogar nada (ex.: troca do fiscal durante as férias).
create or replace table core.aditivo as
select contrato_id, tipo, numero, d(data_assinatura) as data_assinatura,
       try_cast(publicado_em as timestamp) as publicado_em, d(vigencia_fim) as vigencia_fim,
       try_cast(prazo_aditado_dias as integer) as prazo_aditado_dias,
       try_cast(valor_acrescido as double) as valor_acrescido,
       try_cast(valor_global as double) as valor_global, objeto,
       coalesce(tipo ilike '%aditivo%', false) as eh_aditivo,
       coalesce(tipo ilike '%aditivo%', false) and (
         coalesce(try_cast(qualif_vigencia as boolean), false)
         or coalesce(try_cast(prazo_aditado_dias as integer), 0) > 0
         or regexp_matches(lower(coalesce(objeto, '')), 'prorroga|prazo|vig[eê]ncia|renova'))
         as altera_vigencia,
       coalesce(try_cast(qualif_acrescimo as boolean), false)
         or coalesce(try_cast(valor_acrescido as double), 0) > 0 as altera_valor
from staging.pn_termos where contrato_id is not null;

create or replace table core.fornecedor as
-- id curto pra links e nomes de arquivo: o CPF de pessoa física nunca vai pra URL nem pro nome do JSON
select left(md5(fornecedor_ni), 12) as id, fornecedor_ni as ni,
       any_value(fornecedor_nome) as nome, any_value(tipo_pessoa) as tipo_pessoa,
       bool_or(pessoa_fisica) as pessoa_fisica, count(*) as contratos, round(sum(valor_global), 2) as valor_total,
       round(sum(case when contratacao_direta then valor_global else 0 end), 2) as valor_direto,
       min(data_assinatura) as primeiro_contrato, max(data_assinatura) as ultimo_contrato
from core.contrato where fornecedor_ni is not null and fornecedor_ni <> '' group by fornecedor_ni;

-- ===== Contas (SICONFI) =====
create or replace table core.pessoal as
select cast(exercicio as integer) as exercicio, cast(periodo as integer) as periodo, anexo,
       coluna, cod_conta, conta, n(valor) as valor
from staging.sc_rgf;

create or replace table core.receita as
select cast(exercicio as integer) as exercicio, cast(periodo as integer) as periodo, anexo,
       coluna, cod_conta, conta, n(valor) as valor
from staging.sc_rreo;

-- Despesa com pessoal sobre a RCL, uma linha por quadrimestre, pra tela de Contas.
-- cod_conta e coluna conferidos nos 14 quadrimestres de 2022 a 2026 (RGF-Anexo 01, Poder Executivo).
-- Limites da LRF: alerta 48,6%, prudencial 51,3%, máximo 54% (arts. 20, 22 e 59).
create or replace table core.limite_pessoal as
select exercicio, periodo,
       max(valor) filter (where cod_conta = 'ReceitaCorrenteLiquidaLimiteLegal' and coluna = 'Valor') as rcl,
       max(valor) filter (where cod_conta = 'ReceitaCorrenteLiquidaAjustada' and coluna = 'Valor') as rcl_ajustada,
       max(valor) filter (where cod_conta = 'DespesaComPessoalTotal' and coluna = 'Valor') as despesa_pessoal,
       max(valor) filter (where cod_conta = 'DespesaComPessoalTotal' and coluna ilike '% sobre a RCL%') as pct_rcl,
       max(valor) filter (where cod_conta = 'LimiteDeAlertaDespesaComPessoalTotal' and coluna ilike '% sobre a RCL%') as limite_alerta,
       max(valor) filter (where cod_conta = 'LimitePrudencialDespesaComPessoalTotal' and coluna ilike '% sobre a RCL%') as limite_prudencial,
       max(valor) filter (where cod_conta = 'LimiteMaximoDespesaComPessoalTotal' and coluna ilike '% sobre a RCL%') as limite_maximo
from core.pessoal
where anexo = 'RGF-Anexo 01'
group by exercicio, periodo
having count(*) filter (where cod_conta = 'DespesaComPessoalTotal') > 0;

-- Receita realizada e despesa do ano, do último bimestre publicado (RREO Anexo 01).
-- Ano em curso aparece com o bimestre mais recente; a tela avisa que é parcial.
create or replace table core.resultado_anual as
with ultimo as (select exercicio, max(periodo) as periodo from core.receita group by 1)
select r.exercicio, u.periodo as bimestre,
       max(r.valor) filter (where r.cod_conta = 'TotalReceitas' and r.coluna ilike 'Até o Bimestre%') as receita_realizada,
       max(r.valor) filter (where r.cod_conta = 'TotalReceitas' and r.coluna ilike 'PREVISÃO ATUALIZADA%') as receita_prevista,
       max(r.valor) filter (where r.cod_conta = 'TotalDespesas' and r.coluna ilike 'DESPESAS EMPENHADAS ATÉ%') as despesa_empenhada,
       max(r.valor) filter (where r.cod_conta = 'TotalDespesas' and r.coluna ilike 'DESPESAS LIQUIDADAS ATÉ%') as despesa_liquidada,
       max(r.valor) filter (where r.cod_conta = 'TotalDespesas' and r.coluna ilike 'DESPESAS PAGAS ATÉ%') as despesa_paga
from core.receita r join ultimo u on u.exercicio = r.exercicio and u.periodo = r.periodo
group by r.exercicio, u.periodo;

-- ===== Câmara de Vereadores =====
create or replace table core.proposicao as
select cast(id as bigint) as id, cast(ano as integer) as ano, cast(numero as integer) as numero, especie,
       sigla_especie, trim(ementa) as ementa, url, destinatario,
       try_cast(atualizado_em as timestamp) as atualizado_em
from staging.cm_proposicoes
where id is not null
qualify row_number() over (partition by id order by atualizado_em desc nulls last) = 1;

-- Quem assina as proposições: vereadores, comissões, bancadas, Mesa Diretora, Executivo. O id do autor é
-- a chave. O cargo vem do cadastro da Câmara (/parlamentares), que só lista o mandato atual; para quem
-- já saiu, vem do tratamento no nome ("Ver.ª" é vereadora); para os outros proponentes, do começo do
-- nome. O tratamento sai do nome uma vez, aqui; o resto do painel lê o nome pronto desta tabela.
create or replace table core.vereador as
with assinou as (
  select cast(id_autor as bigint) as id, any_value(nome) as bruto, any_value(partido) as partido
  from staging.cm_autores where id_autor is not null group by 1
),
cadastro as (
  select cast("ID" as bigint) as id, any_value(cargo) as cargo, any_value(partido) as partido
  from staging.cm_parlamentares where "ID" is not null group by 1
)
select a.id,
       coalesce(nullif(trim(regexp_replace(a.bruto, '^\s*(Ver\.\s*ª|Ver\.|Vice-Prefeit[ao])\s*', '')), ''),
                a.bruto) as nome,
       coalesce(c.partido, a.partido) as partido,
       coalesce(c.cargo, case
         when regexp_matches(a.bruto, '^\s*Ver\.\s*ª') then 'Vereadora'
         when regexp_matches(a.bruto, '^\s*Ver\.') then 'Vereador'
         when regexp_matches(a.bruto, '^\s*Vice-Prefeita') then 'Vice-prefeita'
         when regexp_matches(a.bruto, '^\s*Vice-Prefeito') then 'Vice-prefeito'
         when regexp_matches(a.bruto, '^\s*Comiss') then 'Comissão'
         when regexp_matches(a.bruto, '^\s*Bancada') then 'Bancada'
         when regexp_matches(a.bruto, '^\s*Mesa Diretora') then 'Mesa Diretora'
         when regexp_matches(a.bruto, '^\s*Executivo Municipal') then 'Executivo municipal'
       end) as cargo
from assinou a left join cadastro c using (id);

create or replace table core.bairro as
select cast("ID" as bigint) as id, nome from staging.cm_bairros where "ID" is not null;

-- Pedidos à prefeitura: pedidos de providência e indicações. O tema sai de slf/temas.yaml: a primeira
-- regra (na ordem do arquivo) cuja expressão aparece na ementa; sem nenhuma, "Outros".
create or replace table core.pedido as
select p.id, p.ano, p.numero, p.especie, p.sigla_especie, p.ementa, p.url,
       coalesce((select t.tema from staging.cm_temas t
                 where regexp_matches(lower(coalesce(p.ementa, '')), t.padrao)
                 order by t.ordem limit 1), 'Outros') as tema
from core.proposicao p
where p.especie in ('Pedido de Providência', 'Indicação');

create or replace table core.pedido_autor as
select distinct cast(a.id_proposicao as bigint) as id_pedido, cast(a.id_autor as bigint) as id_vereador
from staging.cm_autores a
join core.pedido p on p.id = cast(a.id_proposicao as bigint);

-- Bairro do pedido: o que a API da Câmara liga (fonte "camara") e o que a ementa diz logo depois da
-- palavra "bairro" (fonte "ementa"), pelo nome oficial ou por um apelido de slf/bairros.yaml.
create or replace table core.pedido_bairro as
with padroes as (
  select id as id_bairro, strip_accents(lower(nome)) as padrao from core.bairro
  union all
  select b.id, a.padrao from staging.cm_bairro_apelido a
  join core.bairro b on strip_accents(lower(b.nome)) = strip_accents(lower(a.bairro))
),
pela_api as (
  select distinct cast(v.id_proposicao as bigint) as id_pedido, cast(v.id_bairro as bigint) as id_bairro
  from staging.cm_proposicao_bairro v
),
pelo_texto as (
  select distinct p.id as id_pedido, x.id_bairro
  from core.pedido p join padroes x
    on regexp_matches(strip_accents(lower(coalesce(p.ementa, ''))), 'bairro\s+(' || x.padrao || ')\b')
)
select id_pedido, id_bairro, min(fonte) as fonte from (
  select *, 'camara' as fonte from pela_api
  union all
  select *, 'ementa' as fonte from pelo_texto
) j
where id_pedido in (select id from core.pedido)
group by id_pedido, id_bairro;

create or replace table core.tema as
select ordem, tema from staging.cm_temas
union all select 999, 'Outros';
