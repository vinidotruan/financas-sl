import { num } from '../formato'
import { ChipCargo, Foto } from './pecas'

/** Uma linha do ranking: nome, número e barra proporcional ao maior. */
export interface Linha {
  chave: string; nome: string; cargo?: string | null; detalhe?: string; n: number; href?: string
  /** só no ranking de pessoas: arquivo da foto, ou null para as iniciais */
  foto?: string | null
}

/** Ranking com barra; com `foto` definida (mesmo null), a linha ganha a foto ou as iniciais. */
export function Ranking({ linhas, vazio, limite }: { linhas: Linha[]; vazio: string; limite?: number }) {
  if (!linhas.length) return <p class="vazio">{vazio}</p>
  const max = linhas[0].n
  const mostradas = limite ? linhas.slice(0, limite) : linhas
  return (
    <ul class="lista">
      {mostradas.map((l) => {
        const texto = (
          <>
            <span class="linha-topo">
              <span class="titulo">{l.nome}{l.cargo && <> <ChipCargo cargo={l.cargo} /></>}{l.detalhe && <span class="apagado"> · {l.detalhe}</span>}</span>
              <span class="valor">{num(l.n)}</span>
            </span>
            <div class="barra" aria-hidden="true"><i style={{ width: `${(l.n / max) * 100}%` }} /></div>
          </>
        )
        const conteudo = l.foto === undefined ? texto
          : <span class="pessoa"><Foto arquivo={l.foto} nome={l.nome} /><span class="pessoa-corpo">{texto}</span></span>
        return <li key={l.chave}>{l.href ? <a href={l.href}>{conteudo}</a> : <div class="item">{conteudo}</div>}</li>
      })}
    </ul>
  )
}
