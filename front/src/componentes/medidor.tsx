import { pctDireto } from '../formato'
import type { LimitePessoal } from '../tipos'

const ESCALA_MAX = 60 // o medidor vai de 0% a 60% da RCL

/** Barra do gasto com pessoal sobre a RCL, com as marcas de alerta, prudencial e máximo da LRF. */
export function MedidorLRF({ ultimo }: { ultimo: LimitePessoal }) {
  const pos = (v: number | null) => `${((v ?? 0) / ESCALA_MAX) * 100}%`
  return (
    <div class="medidor" role="img"
      aria-label={`${pctDireto(ultimo.pct_rcl)} da receita corrente líquida. Limites da LRF: alerta ${pctDireto(ultimo.limite_alerta, 1)}, prudencial ${pctDireto(ultimo.limite_prudencial, 1)}, máximo ${pctDireto(ultimo.limite_maximo, 0)}.`}>
      <i style={{ width: pos(ultimo.pct_rcl) }} />
      <b style={{ left: pos(ultimo.limite_alerta) }} />
      <b style={{ left: pos(ultimo.limite_prudencial) }} />
      <b class="max" style={{ left: pos(ultimo.limite_maximo) }} />
    </div>
  )
}
