import { useEffect, useState } from 'preact/hooks'

// Rotas no hash (#/regra/R05): funcionam igual no `slf servir` e num site estático, sem servidor.
export type Aba = 'sinais' | 'emendas' | 'fichas' | 'contas' | 'fontes'

export type Rota =
  | { tela: 'sinais' }
  | { tela: 'regra'; id: string }
  | { tela: 'sinal'; id: string }
  | { tela: 'emendas' }
  | { tela: 'emenda'; codigo: string }
  | { tela: 'fichas'; lista: 'parlamentares' | 'fornecedores' }
  | { tela: 'parlamentar'; codigo: string }
  | { tela: 'fornecedor'; id: string }
  | { tela: 'contas' }
  | { tela: 'fontes' }

export function lerRota(hash: string): Rota {
  const [tela, arg] = hash.replace(/^#\/?/, '').split('/').map(decodeURIComponent)
  switch (tela) {
    case 'regra': return arg ? { tela, id: arg } : { tela: 'sinais' }
    case 'sinal': return arg ? { tela, id: arg } : { tela: 'sinais' }
    case 'emendas': return { tela }
    case 'emenda': return arg ? { tela, codigo: arg } : { tela: 'emendas' }
    case 'fichas': return { tela, lista: arg === 'fornecedores' ? 'fornecedores' : 'parlamentares' }
    case 'parlamentar': return arg ? { tela, codigo: arg } : { tela: 'fichas', lista: 'parlamentares' }
    case 'fornecedor': return arg ? { tela, id: arg } : { tela: 'fichas', lista: 'fornecedores' }
    case 'contas': return { tela }
    case 'fontes': return { tela }
    default: return { tela: 'sinais' }
  }
}

/** A aba de baixo que fica acesa em cada tela */
export function abaDa(rota: Rota): Aba {
  switch (rota.tela) {
    case 'regra': case 'sinal': return 'sinais'
    case 'emenda': return 'emendas'
    case 'parlamentar': case 'fornecedor': return 'fichas'
    default: return rota.tela
  }
}

export const link = {
  sinais: () => '#/sinais',
  regra: (id: string) => `#/regra/${id}`,
  sinal: (id: string) => `#/sinal/${id}`,
  emendas: () => '#/emendas',
  emenda: (codigo: string) => `#/emenda/${codigo.replace(/\D/g, '')}`,
  fichas: (lista: 'parlamentares' | 'fornecedores' = 'parlamentares') => `#/fichas/${lista}`,
  parlamentar: (codigo: string) => `#/parlamentar/${codigo}`,
  fornecedor: (id: string) => `#/fornecedor/${id}`,
  contas: () => '#/contas',
  fontes: () => '#/fontes',
}

// Quantas telas a pessoa abriu dentro do app desde que carregou a página.
let navegacoes = 0

export function useRota(): Rota {
  const [rota, setRota] = useState(() => lerRota(location.hash))
  useEffect(() => {
    const mudou = () => {
      navegacoes += 1
      setRota(lerRota(location.hash))
      window.scrollTo(0, 0)
    }
    addEventListener('hashchange', mudou)
    return () => removeEventListener('hashchange', mudou)
  }, [])
  return rota
}

/** Voltar pelo histórico quando a pessoa navegou aqui dentro; se abriu um link direto, vai para a lista. */
export function voltar(padrao: string) {
  if (navegacoes > 0) history.back()
  else location.hash = padrao
}
