import { brlCurto, num, pct } from '../formato'
import type { Emenda } from '../tipos'

/* Pizza das emendas por área (função do orçamento que o Transferegov põe no plano de ação).
   Até 5 fatias com cor; o resto vai para "Outras", e a legenda lista o que está dentro dela, para
   nenhuma categoria da fonte sumir. As cores ficam presas às 5 maiores áreas de todas as emendas, não
   do filtro: trocar o ano não repinta uma área com a cor de outra. */

const FATIAS_COM_COR = 5

function somarPorArea(emendas: Emenda[]): Map<string, number> {
  const total = new Map<string, number>()
  for (const e of emendas) {
    for (const a of e.areas ?? []) total.set(a.area, (total.get(a.area) ?? 0) + a.indicado)
  }
  return total
}

function maiores(total: Map<string, number>): [string, number][] {
  return [...total].filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
}

function fatia(cx: number, cy: number, r: number, de: number, ate: number): string {
  const x1 = cx + r * Math.cos(de), y1 = cy + r * Math.sin(de)
  const x2 = cx + r * Math.cos(ate), y2 = cy + r * Math.sin(ate)
  const grande = ate - de > Math.PI ? 1 : 0
  return `M${cx},${cy} L${x1.toFixed(2)},${y1.toFixed(2)} A${r},${r} 0 ${grande} 1 ${x2.toFixed(2)},${y2.toFixed(2)} Z`
}

interface Fatia { nome: string; valor: number; cor: string; dentro?: [string, number][] }

export function PizzaAreas({ emendas, todas }: { emendas: Emenda[]; todas: Emenda[] }) {
  const cor = new Map(maiores(somarPorArea(todas)).slice(0, FATIAS_COM_COR).map(([a], i) => [a, `var(--s${i + 1})`]))
  const areas = maiores(somarPorArea(emendas))
  const total = areas.reduce((s, [, v]) => s + v, 0)
  if (!total) return null

  const fatias: Fatia[] = areas.filter(([a]) => cor.has(a)).map(([nome, valor]) => ({ nome, valor, cor: cor.get(nome)! }))
  const resto = areas.filter(([a]) => !cor.has(a))
  if (resto.length) {
    fatias.push({
      nome: resto.length === 1 ? resto[0][0] : `Outras ${resto.length} áreas`,
      valor: resto.reduce((s, [, v]) => s + v, 0),
      cor: 'var(--s-outras)',
      dentro: resto.length > 1 ? resto : undefined,
    })
  }

  let angulo = -Math.PI / 2
  const desenho = fatias.map((f) => {
    const de = angulo
    angulo += (2 * Math.PI * f.valor) / total
    const titulo = `${f.nome}: ${brlCurto(f.valor)} (${pct(f.valor / total)})`
    return fatias.length === 1
      ? <circle key={f.nome} cx="100" cy="100" r="96" fill={f.cor}><title>{titulo}</title></circle>
      : <path key={f.nome} d={fatia(100, 100, 96, de, angulo)} fill={f.cor}><title>{titulo}</title></path>
  })

  return (
    <div class="cartao pizza">
      <svg viewBox="0 0 200 200" role="img"
        aria-label={`Indicado por área: ${fatias.map((f) => `${f.nome} ${pct(f.valor / total)}`).join(', ')}`}>
        {desenho}
      </svg>
      <ul class="legenda">
        {fatias.map((f) => (
          <li key={f.nome}>
            <i style={{ background: f.cor }} aria-hidden="true" />
            <span class="nome">{f.nome}</span>
            <span class="num">{brlCurto(f.valor)}</span>
            <span class="num apagado">{pct(f.valor / total)}</span>
            {f.dentro && (
              <ul class="dentro">
                {f.dentro.map(([nome, valor]) => (
                  <li key={nome}><span class="nome">{nome}</span><span class="num">{brlCurto(valor)}</span><span class="num apagado">{pct(valor / total)}</span></li>
                ))}
              </ul>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

/* Quanto cada cargo indicou. São duas partes (deputados federais e senadores), então números dizem
   mais que um gráfico. Autor sem cadastro no Congresso aparece à parte, sem cargo. */

function grupo(cargo: string | null): string {
  if (cargo?.startsWith('Deputad')) return 'Deputados federais'
  if (cargo?.startsWith('Senador')) return 'Senadores'
  return 'Sem cargo identificado'
}

const ORDEM = ['Deputados federais', 'Senadores', 'Sem cargo identificado']

export function CargosEmendas({ emendas }: { emendas: Emenda[] }) {
  const total = emendas.reduce((s, e) => s + e.indicado, 0)
  if (!total) return null
  const grupos = new Map<string, { indicado: number; transferido: number; planos: number; autores: Set<string> }>()
  for (const e of emendas) {
    const g = grupo(e.cargo)
    const atual = grupos.get(g) ?? { indicado: 0, transferido: 0, planos: 0, autores: new Set<string>() }
    atual.indicado += e.indicado
    atual.transferido += e.transferido
    atual.planos += e.planos
    atual.autores.add(e.codigo_autor)
    grupos.set(g, atual)
  }
  return (
    <div class="duo">
      {ORDEM.filter((g) => grupos.has(g)).map((g) => {
        const v = grupos.get(g)!
        return (
          <div key={g} class="cartao">
            <span class="rotulo">{g}</span>
            <span class="valor">{brlCurto(v.indicado)}</span>
            <span class="pequeno apagado">{pct(v.indicado / total)} do indicado · {brlCurto(v.transferido)} transferidos</span>
            <span class="pequeno apagado">
              {num(v.autores.size)} {v.autores.size === 1 ? 'parlamentar' : 'parlamentares'} · {num(v.planos)} {v.planos === 1 ? 'plano' : 'planos'}
            </span>
          </div>
        )
      })}
    </div>
  )
}
