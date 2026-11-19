import type { Evidencia, Formato } from './tipos'

const reais = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' })
const inteiro = new Intl.NumberFormat('pt-BR')
const decimal1 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const decimal2 = new Intl.NumberFormat('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })

export const VAZIO = '–'

/** R$ 1.234.567,89 */
export function brl(v: number | null | undefined): string {
  return v == null ? VAZIO : reais.format(v)
}

/** R$ 4,77 mi, para números grandes em pouco espaço */
export function brlCurto(v: number | null | undefined): string {
  if (v == null) return VAZIO
  const abs = Math.abs(v)
  if (abs >= 1e9) return `R$ ${decimal2.format(v / 1e9)} bi`
  if (abs >= 1e6) return `R$ ${decimal2.format(v / 1e6)} mi`
  if (abs >= 1e4) return `R$ ${inteiro.format(Math.round(v / 1e3))} mil`
  return reais.format(v)
}

/** fração (0,678) para 67,8% */
export function pct(v: number | null | undefined): string {
  return v == null ? VAZIO : `${decimal1.format(v * 100)}%`
}

/** número que já vem em percentual (40,78) para 40,78% */
export function pctDireto(v: number | null | undefined, casas = 2): string {
  if (v == null) return VAZIO
  return `${new Intl.NumberFormat('pt-BR', { minimumFractionDigits: casas, maximumFractionDigits: casas }).format(v)}%`
}

export function num(v: number | null | undefined): string {
  return v == null ? VAZIO : inteiro.format(v)
}

/** 2025-06-30 (ou 2025-06-30T10:00:00) para 30/06/2025, sem passar por fuso horário */
export function data(v: unknown): string {
  if (typeof v !== 'string' || v.length < 10) return VAZIO
  const [a, m, d] = v.slice(0, 10).split('-')
  return `${d}/${m}/${a}`
}

/** 2026-11-18T22:12:02 para 18/11/2026 22:12 */
export function dataHora(v: unknown): string {
  if (typeof v !== 'string' || v.length < 16) return data(v)
  return `${data(v)} ${v.slice(11, 16)}`
}

export function dias(v: unknown): string {
  if (typeof v !== 'number') return VAZIO
  return v === 1 ? '1 dia' : `${inteiro.format(v)} dias`
}

/** CNPJ com máscara; CPF já chega mascarado da API (***.456.789-**) e passa como está */
export function documento(v: unknown): string {
  if (typeof v !== 'string') return VAZIO
  if (/^\d{14}$/.test(v)) return v.replace(/^(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})$/, '$1.$2.$3/$4-$5')
  return v
}

export function frase(v: unknown): string {
  if (typeof v !== 'string' || !v) return VAZIO
  return v.charAt(0).toUpperCase() + v.slice(1)
}

export function formatar(v: unknown, formato: Formato): string {
  if (v == null || v === '') return VAZIO
  switch (formato) {
    case 'brl': return brl(Number(v))
    case 'pct': return pct(Number(v))
    case 'dias': return dias(Number(v))
    case 'data': return data(v)
    case 'datahora': return dataHora(v)
    case 'int': return num(Number(v))
    case 'doc': return documento(v)
    case 'frase': return frase(v)
    default: return String(v)
  }
}

/** Preenche o "resumo" da regra: "{transferido|brl} em {prazo|data}" com os campos da evidência. */
export function preencher(modelo: string, evidencia: Evidencia): string {
  return modelo.replace(/\{(\w+)(?:\|(\w+))?\}/g, (_, campo: string, fmt?: string) =>
    formatar(evidencia[campo], (fmt as Formato) ?? 'texto'))
}

// Rótulo e formato de cada campo de evidência que as regras gravam. Campo sem rótulo aparece com o
// nome técnico; campos marcados como null não aparecem (servem só para a lógica de privacidade).
export const CAMPOS: Record<string, [string, Formato] | null> = {
  transferido: ['Valor transferido', 'brl'],
  executado_relatorio: ['Executado segundo o relatório', 'brl'],
  ultimo_relatorio: ['Último relatório', 'texto'],
  data_relatorio: ['Data do relatório', 'data'],
  primeira_transferencia: ['Primeira transferência', 'data'],
  dias_desde_a_transferencia: ['Desde a transferência', 'dias'],
  situacao_plano_trabalho: ['Situação do plano de trabalho', 'texto'],
  id_plano_acao: ['Plano de ação (id no Transferegov)', 'texto'],
  motivo: ['Motivo', 'frase'],
  prazo_vencido: ['Prazo vencido', 'data'],
  dias_em_atraso: ['Atraso', 'dias'],
  relatorios_entregues: ['Relatórios entregues', 'int'],
  relatorios_em_elaboracao: ['Relatórios em elaboração', 'int'],
  prazo_plano: ['Prazo do plano de trabalho', 'data'],
  contrato: ['Contrato no PNCP', 'texto'],
  compra: ['Compra no PNCP', 'texto'],
  amparo: ['Amparo legal', 'texto'],
  modalidade: ['Modalidade', 'texto'],
  valor_inicial: ['Valor inicial', 'brl'],
  valor_global: ['Valor global atual', 'brl'],
  valor_estimado: ['Valor estimado', 'brl'],
  aditivos_de_prazo: ['Aditivos que mudam a vigência', 'int'],
  vigencia_inicio: ['Início da vigência', 'data'],
  ultimo_aditivo: ['Último aditivo de prazo', 'data'],
  dias_aditados: ['Dias acrescidos nos aditivos', 'dias'],
  encerramento: ['Fim das propostas', 'datahora'],
  publicado: ['Primeira publicação no PNCP', 'datahora'],
  contratos: ['Contratos no ano', 'int'],
  diretos: ['Contratos sem licitação', 'int'],
  valor_total: ['Valor contratado no ano', 'brl'],
  valor_direto: ['Valor sem licitação', 'brl'],
  fornecedor: ['Fornecedor (CNPJ ou CPF)', 'doc'],
  tipo_pessoa: null,
  pessoa_fisica: null,
}

/** Link do contrato ou da compra no site do PNCP, a partir do número de controle */
export function linkPncp(numeroControle: string): string | null {
  const m = numeroControle.match(/^(\d{14})-(\d)-0*(\d+)\/(\d{4})$/)
  if (!m) return null
  const [, cnpj, tipo, seq, ano] = m
  const caminho = tipo === '1' ? 'editais' : 'contratos'
  return `https://pncp.gov.br/app/${caminho}/${cnpj}/${ano}/${seq}`
}

export const SEVERIDADE: Record<string, string> = { alto: 'Alto', atencao: 'Atenção', baixo: 'Baixo' }
export const AREA: Record<string, string> = { emendas: 'Emendas', compras: 'Compras', contas: 'Contas' }
export const FONTE: Record<string, string> = {
  transferegov: 'Transferegov', siconfi: 'SICONFI', pncp: 'PNCP', prefeitura: 'Prefeitura',
}
