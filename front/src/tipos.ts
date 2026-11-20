// Formas que a API devolve (e que `slf exportar` grava em JSON). Datas chegam em ISO.

export type Severidade = 'alto' | 'atencao' | 'baixo'
export type Status = 'novo' | 'em análise' | 'descartado' | 'confirmado' | 'encaminhado'
export type Formato = 'brl' | 'pct' | 'dias' | 'data' | 'datahora' | 'int' | 'texto' | 'frase' | 'doc'

export interface FonteRef {
  nome: string
  link: string | null
  coletado_em: string | null
}

export interface Regra {
  id: string
  nome: string
  versao: number
  area: string
  severidade: Severidade
  base_legal: string
  limiar: string
  pode_ser_normal_se: string
  como_verificar: string
  fontes: FonteRef[]
  observado: { rotulo: string; formato: Formato } | null
  resumo: string | null
  ativos: number
  novos: number
}

export type Evidencia = Record<string, unknown>

export interface Sinal {
  id: string
  regra_id: string
  nome: string
  area: string
  severidade: Severidade
  chave: string
  titulo: string
  valor_observado: number | null
  quando: string | null
  primeira_vez: string | null
  ultima_vez: string | null
  ativo: boolean
  status: Status
  nota: string | null
  evidencia: Evidencia
}

export interface ContratoLigado {
  id: string
  objeto: string
  valor_global: number
  fornecedor_id: string | null
  fornecedor_nome: string
}

export interface SinalDetalhe extends Sinal {
  regra_versao: number
  base_legal: string
  limiar: string
  pode_ser_normal_se: string
  como_verificar: string
  fontes: FonteRef[]
  observado: { rotulo: string; formato: Formato } | null
  resumo: string | null
  ligacoes: { emenda?: string; contratos?: ContratoLigado[] }
}

export interface Emenda {
  codigo_emenda: string
  codigo: string
  parlamentar: string
  cargo: string | null
  codigo_autor: string
  ano: number
  planos: number
  indicado: number
  transferido: number
  executado_relatorio: number | null
  /** valor indicado por área (função do orçamento no plano de ação), maior primeiro */
  areas: { area: string; indicado: number }[]
}

export interface Plano {
  id_plano_acao: number
  codigo_plano: string
  codigo_formatado: string
  ano: number
  situacao: string
  motivo_impedimento: string | null
  parlamentar: string
  valor_custeio: number
  valor_investimento: number
  valor_indicado: number
  transferido: number
  primeira_ob: string | null
  ultima_ob: string | null
  executado_relatorio: number | null
  tipo_relatorio: string | null
  data_relatorio: string | null
  relatorios_entregues: number
  relatorios_em_elaboracao: number
  prazo_relatorio_parcial: string | null
  prazo_inicio: string | null
  prazo_fim: string | null
  situacao_plano_trabalho: string | null
}

export interface Rastro {
  codigo: string
  codigo_formatado: string
  parlamentar: { codigo: string; nome: string; cargo: string | null }
  ano: number
  valores: { etapa: string; fonte: string; valor: number | null; nota?: string | null }[]
  planos: Plano[]
  transferencias: { id_plano_acao: number; numero_empenho: string; numero_ob: string; data_ob: string; valor: number }[]
  metas: { id_plano_acao: number; executor: string; objeto: string; nome_meta: string | null; desc_meta: string | null }[]
  sinais: Sinal[]
  fontes: FonteRef[]
}

export interface Parlamentar {
  codigo: string
  nome: string
  /** Deputado(a) federal ou Senador(a), pelo cadastro do Congresso; null quando o nome não casou */
  cargo: string | null
  uf: string | null
  /** perfil oficial na Câmara dos Deputados ou no Senado */
  link: string | null
  /** foto oficial reduzida (camara-{id}.jpg, senado-{codigo}.jpg); null fora da UF ou sem foto */
  foto: string | null
  emendas: number
  planos: number
  indicado: number
  transferido: number
  primeiro_ano: number
  ultimo_ano: number
}

export interface ParlamentarFicha extends Parlamentar {
  emendas_lista: Emenda[]
  sinais: Sinal[]
  fontes: FonteRef[]
}

export interface Fornecedor {
  id: string | null
  ni: string | null
  nome: string
  tipo_pessoa: string | null
  pessoa_fisica: boolean
  contratos: number
  valor_total: number
  valor_direto: number
  pct_direto: number | null
  primeiro_contrato: string | null
  ultimo_contrato: string | null
  /** pago por todos os órgãos coletados no TCE-RS, todos os anos (D44) */
  pago_total: number
  /** pago pela prefeitura em cada ano: { "2025": 400000 } */
  pago_prefeitura: Record<string, number>
  /** órgão público, banco, previdência ou tributo retido (slf/repasses.yaml) */
  repasse: boolean
}

export interface ContratoFicha {
  id: string
  compra_id: string | null
  orgao_nome: string
  unidade: string
  ano: number
  objeto: string
  categoria: string
  modalidade: string | null
  amparo: string | null
  contratacao_direta: boolean
  emergencial: boolean
  valor_inicial: number
  valor_global: number
  data_assinatura: string | null
  vigencia_fim: string | null
}

export interface FornecedorFicha extends Fornecedor {
  contratos_lista: ContratoFicha[]
  pagos: { orgao_nome: string; ano: number; valor: number }[]
  sinais: Sinal[]
  fontes: FonteRef[]
}

export interface LimitePessoal {
  exercicio: number
  periodo: number
  rcl: number | null
  rcl_ajustada: number | null
  despesa_pessoal: number | null
  pct_rcl: number | null
  limite_alerta: number | null
  limite_prudencial: number | null
  limite_maximo: number | null
}

export interface ResultadoAnual {
  exercicio: number
  bimestre: number
  receita_realizada: number | null
  receita_prevista: number | null
  despesa_empenhada: number | null
  despesa_liquidada: number | null
  despesa_paga: number | null
}

export interface Contas {
  limite_pessoal: LimitePessoal[]
  resultado_anual: ResultadoAnual[]
  fontes: FonteRef[]
}

export interface Fontes {
  modo: 'privado' | 'publico'
  ente: { nome: string; uf: string | null; ibge: number | null }
  fontes: { fonte: string; coleta: string | null; coletado_em: string | null; arquivos: number; linhas: number; link: string | null }[]
  erros_de_regra: { regra_id: string; mensagem: string }[]
}

export interface Pedidos {
  total: number
  temas: string[]
  anos: number[]
  por_tema: { ano: number; tema: string; pedidos: number }[]
  por_vereador: { id: number; nome: string; partido: string | null; cargo: string | null; foto: string | null; ano: number; tema: string; pedidos: number }[]
  por_bairro: { id: number; nome: string; ano: number; tema: string; pedidos: number }[]
  sem_bairro: { ano: number; tema: string; pedidos: number }[]
  fontes: FonteRef[]
}

export interface Pedido {
  id: number
  ano: number
  numero: number
  especie: string
  ementa: string
  url: string | null
  tema: string
  bairros: string | null
  /** último passo de tramitação na Câmara ("Encaminhado para o Executivo"...); não diz se a prefeitura atendeu */
  situacao: string | null
  situacao_data: string | null
}

export interface Vereador {
  id: number
  nome: string
  partido: string | null
  /** Vereador, Vereadora, Comissão, Bancada, Mesa Diretora, Executivo municipal... */
  cargo: string | null
  /** arquivo da foto reduzida (vereador-{id}.jpg); sem foto na fonte, null */
  foto: string | null
  pedidos: Pedido[]
  fontes: FonteRef[]
}

/** A aba Início (D44): /api/inicio e inicio.json */
export interface Inicio {
  data_referencia: string
  /** null quando o TCE-RS ainda não trouxe um ano com dezembro */
  recebeu: {
    ano: number
    total: number
    empresas: { id: string; nome: string; valor: number }[]
    ano_corrente: number
    ate: string | null
  } | null
  emendas: { indicado: number; transferido: number }
  parados: { dias: number; total: number; por_situacao: { situacao: string; pedidos: number }[]; sem_situacao: number }
  partidos: { partido: string; pedidos: number }[]
  bairros: { id: number; nome: string; pedidos: number }[]
  folha: LimitePessoal | null
  fontes: FonteRef[]
}
