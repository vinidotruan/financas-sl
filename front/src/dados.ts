// Camada de dados única. Em desenvolvimento e no `slf servir` lê a API local (/api/...);
// no site publicado lê os arquivos JSON que `slf exportar` grava em data/. Troca por configuração:
// VITE_DADOS=estatico (npm run build:estatico) ou api (padrão).
import type {
  Contas, Emenda, Fontes, Inicio, Pedidos, Vereador, Fornecedor, FornecedorFicha, Parlamentar, ParlamentarFicha, Rastro, Regra, Sinal,
  SinalDetalhe, Status,
} from './tipos'

export const MODO_DADOS: 'api' | 'estatico' = import.meta.env.VITE_DADOS === 'estatico' ? 'estatico' : 'api'
const BASE_ESTATICA = (import.meta.env.VITE_BASE_DADOS as string | undefined) ?? 'data/'

interface Rota { api: string; arquivo: string }

const rota = {
  fontes: (): Rota => ({ api: 'api/fontes', arquivo: 'fontes.json' }),
  inicio: (): Rota => ({ api: 'api/inicio', arquivo: 'inicio.json' }),
  regras: (): Rota => ({ api: 'api/regras', arquivo: 'regras.json' }),
  sinais: (): Rota => ({ api: 'api/sinais', arquivo: 'sinais.json' }),
  sinal: (id: string): Rota => ({ api: `api/sinais/${id}`, arquivo: `sinais/${id}.json` }),
  emendas: (): Rota => ({ api: 'api/emendas', arquivo: 'emendas.json' }),
  rastro: (codigo: string): Rota => ({ api: `api/emendas/${codigo}/rastro`, arquivo: `rastro/${codigo}.json` }),
  parlamentares: (): Rota => ({ api: 'api/parlamentares', arquivo: 'parlamentares.json' }),
  parlamentar: (codigo: string): Rota => ({ api: `api/parlamentares/${codigo}`, arquivo: `parlamentares/${codigo}.json` }),
  fornecedores: (): Rota => ({ api: 'api/fornecedores', arquivo: 'fornecedores.json' }),
  fornecedor: (id: string): Rota => ({ api: `api/fornecedores/${id}`, arquivo: `fornecedores/${id}.json` }),
  contas: (): Rota => ({ api: 'api/contas', arquivo: 'contas.json' }),
  pedidos: (): Rota => ({ api: 'api/pedidos', arquivo: 'pedidos.json' }),
  vereador: (id: string): Rota => ({ api: `api/vereadores/${id}`, arquivo: `vereadores/${id}.json` }),
}

export class ErroDados extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}

const cache = new Map<string, Promise<unknown>>()

async function buscar<T>(r: Rota): Promise<T> {
  const url = MODO_DADOS === 'api' ? r.api : BASE_ESTATICA + r.arquivo
  if (!cache.has(url)) {
    const pedido = fetch(url, { headers: { Accept: 'application/json' } }).then(async (resp) => {
      if (resp.ok) return resp.json()
      let detalhe = ''
      try { detalhe = (await resp.json()).detail ?? '' } catch { /* corpo sem JSON */ }
      if (resp.status === 404) throw new ErroDados(detalhe || 'Não encontrado.', 404)
      if (resp.status === 503) throw new ErroDados(detalhe || 'O banco ainda não foi montado.', 503)
      throw new ErroDados(detalhe || `A fonte de dados respondeu ${resp.status}.`, resp.status)
    })
    pedido.catch(() => cache.delete(url))  // erro não fica guardado: a próxima tentativa busca de novo
    cache.set(url, pedido)
  }
  return cache.get(url) as Promise<T>
}

/** Endereço de uma foto reduzida: a API serve em api/fotos, o site publicado em data/fotos. */
export function urlFoto(arquivo: string): string {
  return MODO_DADOS === 'api' ? `api/fotos/${arquivo}` : `${BASE_ESTATICA}fotos/${arquivo}`
}

export const dados = {
  fontes: () => buscar<Fontes>(rota.fontes()),
  inicio: () => buscar<Inicio>(rota.inicio()),
  regras: () => buscar<Regra[]>(rota.regras()),
  sinais: () => buscar<Sinal[]>(rota.sinais()),
  sinal: (id: string) => buscar<SinalDetalhe>(rota.sinal(id)),
  emendas: () => buscar<Emenda[]>(rota.emendas()),
  rastro: (codigo: string) => buscar<Rastro>(rota.rastro(codigo)),
  parlamentares: () => buscar<Parlamentar[]>(rota.parlamentares()),
  parlamentar: (codigo: string) => buscar<ParlamentarFicha>(rota.parlamentar(codigo)),
  fornecedores: () => buscar<Fornecedor[]>(rota.fornecedores()),
  fornecedor: (id: string) => buscar<FornecedorFicha>(rota.fornecedor(id)),
  contas: () => buscar<Contas>(rota.contas()),
  pedidos: () => buscar<Pedidos>(rota.pedidos()),
  vereador: (id: string) => buscar<Vereador>(rota.vereador(id)),
}

/** Revisão só existe com a API local no modo privado. No site estático ninguém grava nada. */
export async function podeRevisar(): Promise<boolean> {
  if (MODO_DADOS !== 'api') return false
  try {
    return (await dados.fontes()).modo === 'privado'
  } catch {
    return false
  }
}

export async function revisar(id: string, status: Status, nota: string | null): Promise<void> {
  const resp = await fetch(`api/sinais/${id}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status, nota }),
  })
  if (!resp.ok) {
    let detalhe = ''
    try { detalhe = (await resp.json()).detail ?? '' } catch { /* corpo sem JSON */ }
    throw new ErroDados(detalhe || `A API respondeu ${resp.status}.`, resp.status)
  }
  // o que depende do status volta a ser buscado
  for (const chave of [...cache.keys()]) {
    if (chave.includes('sinais') || chave.includes('regras') || chave.includes('rastro')
        || chave.includes('parlamentares/') || chave.includes('fornecedores/')) cache.delete(chave)
  }
}
