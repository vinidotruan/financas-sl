-- Core: entidades ligadas pelas chaves que as fontes compartilham.
-- d() e n() convertem com segurança: a fonte pode mandar texto, número ou nulo.
create or replace macro d(x) as try_cast(left(cast(x as varchar), 10) as date);
create or replace macro n(x) as coalesce(try_cast(x as double), 0);
create or replace macro so_digitos(x) as regexp_replace(cast(x as varchar), '[^0-9]', '', 'g');

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
  n(valor_custeio_plano_acao) + n(valor_investimento_plano_acao) as valor_indicado
from staging.tg_plano_acao_especial;

create or replace table core.emenda as
select codigo_emenda, any_value(codigo_formatado) as codigo_formatado, any_value(parlamentar) as parlamentar,
       any_value(codigo_autor) as codigo_autor, min(ano) as ano, count(*) as planos,
       sum(valor_indicado) as valor_indicado
from core.plano_acao group by codigo_emenda;

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
select p.*,
       coalesce(t.transferido, 0) as transferido, t.primeira_ob, t.ultima_ob,
       r.valor_executado as executado_relatorio, r.tipo as tipo_relatorio, r.data as data_relatorio,
       coalesce(q.relatorios_entregues, 0) as relatorios_entregues,
       coalesce(q.relatorios_em_elaboracao, 0) as relatorios_em_elaboracao,
       coalesce(q.tem_final, false) as tem_relatorio_final,
       case when t.primeira_ob is not null
            then make_date(greatest(year(t.primeira_ob) + 1, 2025), 6, 30) end as prazo_relatorio_parcial,
       z.inicio as prazo_inicio, z.fim as prazo_fim, z.situacao as situacao_plano_trabalho
from core.plano_acao p
left join (select id_plano_acao, sum(valor) as transferido, min(data_ob) as primeira_ob,
                  max(data_ob) as ultima_ob
           from core.transferencia group by 1) t using (id_plano_acao)
left join (select * from core.relatorio_gestao where entregue
           qualify row_number() over (partition by id_plano_acao order by data desc nulls last) = 1
          ) r using (id_plano_acao)
left join (select id_plano_acao, count(*) filter (where entregue) as relatorios_entregues,
                  count(*) filter (where not entregue) as relatorios_em_elaboracao,
                  bool_or(entregue and lower(tipo) like '%final%') as tem_final
           from core.relatorio_gestao group by 1) q using (id_plano_acao)
left join core.prazo_plano z using (id_plano_acao);

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
create or replace table core.aditivo as
select contrato_id, tipo, numero, d(data_assinatura) as data_assinatura,
       try_cast(publicado_em as timestamp) as publicado_em, d(vigencia_fim) as vigencia_fim,
       try_cast(prazo_aditado_dias as integer) as prazo_aditado_dias,
       try_cast(valor_acrescido as double) as valor_acrescido,
       try_cast(valor_global as double) as valor_global, objeto,
       coalesce(try_cast(qualif_vigencia as boolean), false)
         or coalesce(try_cast(prazo_aditado_dias as integer), 0) > 0
         or regexp_matches(lower(coalesce(objeto, '')), 'prorroga|prazo|vig[eê]ncia|renova')
         as altera_vigencia,
       coalesce(try_cast(qualif_acrescimo as boolean), false)
         or coalesce(try_cast(valor_acrescido as double), 0) > 0 as altera_valor
from staging.pn_termos where contrato_id is not null;

create or replace table core.fornecedor as
select fornecedor_ni as ni, any_value(fornecedor_nome) as nome, any_value(tipo_pessoa) as tipo_pessoa,
       count(*) as contratos, sum(valor_global) as valor_total,
       sum(case when contratacao_direta then valor_global else 0 end) as valor_direto,
       min(data_assinatura) as primeiro_contrato, max(data_assinatura) as ultimo_contrato
from core.contrato where fornecedor_ni is not null and fornecedor_ni <> '' group by 1;

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
