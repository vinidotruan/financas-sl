import { useCallback, useEffect, useState } from 'preact/hooks'

export interface Estado<T> {
  dados: T | null
  erro: Error | null
  carregando: boolean
  tentarDeNovo: () => void
}

/** Carrega um recurso e refaz quando as dependências mudam. */
export function useCarregar<T>(buscar: () => Promise<T>, deps: unknown[]): Estado<T> {
  const [estado, setEstado] = useState<{ dados: T | null; erro: Error | null; carregando: boolean }>(
    { dados: null, erro: null, carregando: true })
  const [vez, setVez] = useState(0)
  useEffect(() => {
    let vivo = true
    setEstado((e) => ({ ...e, erro: null, carregando: true }))
    buscar().then(
      (dados) => { if (vivo) setEstado({ dados, erro: null, carregando: false }) },
      (erro: Error) => { if (vivo) setEstado({ dados: null, erro, carregando: false }) },
    )
    return () => { vivo = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, vez])
  const tentarDeNovo = useCallback(() => setVez((v) => v + 1), [])
  return { ...estado, tentarDeNovo }
}
