import { useCarregar } from '../componentes/carregar'
import { Carregado, Fontes, Rodape, Topo } from '../componentes/pecas'
import { dados } from '../dados'
import { brl, brlCurto, pctDireto } from '../formato'
import type { LimitePessoal, ResultadoAnual } from '../tipos'

const ESCALA_MAX = 60 // o medidor vai de 0% a 60% da RCL

function Medidor({ ultimo }: { ultimo: LimitePessoal }) {
  const pos = (v: number | null) => `${((v ?? 0) / ESCALA_MAX) * 100}%`
  return (
    <div class="cartao">
      <span class="rotulo">Pessoal sobre a RCL · {ultimo.periodo}º quadrimestre de {ultimo.exercicio}</span>
      <span class="valor-grande">{pctDireto(ultimo.pct_rcl)}</span>
      <div class="medidor" role="img"
        aria-label={`${pctDireto(ultimo.pct_rcl)} da receita corrente líquida. Limites da LRF: alerta ${pctDireto(ultimo.limite_alerta, 1)}, prudencial ${pctDireto(ultimo.limite_prudencial, 1)}, máximo ${pctDireto(ultimo.limite_maximo, 0)}.`}>
        <i style={{ width: pos(ultimo.pct_rcl) }} />
        <b style={{ left: pos(ultimo.limite_alerta) }} />
        <b style={{ left: pos(ultimo.limite_prudencial) }} />
        <b class="max" style={{ left: pos(ultimo.limite_maximo) }} />
      </div>
      <p class="apagado pequeno">
        Limites da LRF: alerta {pctDireto(ultimo.limite_alerta, 1)}, prudencial {pctDireto(ultimo.limite_prudencial, 1)},
        máximo {pctDireto(ultimo.limite_maximo, 0)} (arts. 20, 22 e 59).
      </p>
      <p class="pequeno">
        Despesa com pessoal de {brl(ultimo.despesa_pessoal)} sobre RCL ajustada de {brl(ultimo.rcl_ajustada)}.
      </p>
    </div>
  )
}

/** Série do percentual por quadrimestre, com as três linhas de limite. Tudo na mesma escala.
 *  O viewBox tem a largura de um celular, para o texto do eixo sair perto de 11px na tela. */
function Serie({ pontos }: { pontos: LimitePessoal[] }) {
  const L = 34, R = 286, T = 10, B = 176, W = 340, H = 200
  const valores = pontos.map((p) => p.pct_rcl ?? 0)
  const yMin = Math.floor(Math.min(30, ...valores) / 5) * 5
  const yMax = 56
  const y = (v: number) => T + ((yMax - v) / (yMax - yMin)) * (B - T)
  const x = (i: number) => (pontos.length === 1 ? (L + R) / 2 : L + (i * (R - L)) / (pontos.length - 1))
  const linha = pontos.map((p, i) => `${x(i).toFixed(1)},${y(p.pct_rcl ?? 0).toFixed(1)}`).join(' ')
  const grade = []
  for (let v = yMin; v <= 50; v += 5) grade.push(v)
  const ult = pontos[pontos.length - 1]
  const limites: [number | null, string, string, string][] = [
    [ult.limite_maximo, 'lim max', 'txt-alto', pctDireto(ult.limite_maximo, 0)],
    [ult.limite_prudencial, 'lim', 'txt-atencao', pctDireto(ult.limite_prudencial, 1)],
    [ult.limite_alerta, 'lim alerta', 'txt-atencao', pctDireto(ult.limite_alerta, 1)],
  ]
  return (
    <figure class="cartao grafico" style={{ margin: 0 }}>
      <span class="rotulo">Por quadrimestre</span>
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Pessoal sobre a RCL de ${pontos[0].periodo}º quadrimestre de ${pontos[0].exercicio} a ${ult.periodo}º de ${ult.exercicio}: mínimo ${pctDireto(Math.min(...valores))}, máximo ${pctDireto(Math.max(...valores))}, último ${pctDireto(ult.pct_rcl)}.`}>
        {grade.map((v) => (
          <g key={v}>
            <line class="grade" x1={L} x2={R} y1={y(v)} y2={y(v)} />
            <text class="eixo" x={L - 6} y={y(v) + 4} text-anchor="end">{v}%</text>
          </g>
        ))}
        {limites.map(([v, classe, txt, rotulo]) => v != null && (
          <g key={rotulo}>
            <line class={classe} x1={L} x2={R} y1={y(v)} y2={y(v)} />
            <text class={`eixo ${txt}`} x={R + 8} y={y(v) + 4}>{rotulo}</text>
          </g>
        ))}
        <path class="area" d={`M${x(0)} ${B} L${linha.split(' ').join(' L')} L${x(pontos.length - 1)} ${B} Z`} />
        <polyline class="linha-dado" points={linha} />
        {pontos.map((p, i) => (
          <circle key={i} class={`ponto-dado ${i === pontos.length - 1 ? 'fim' : ''}`} cx={x(i)} cy={y(p.pct_rcl ?? 0)} r={i === pontos.length - 1 ? 4 : 3} />
        ))}
        {pontos.map((p, i) => p.periodo === 1 && (
          <text key={`a${i}`} class="eixo" x={x(i)} y={H - 6} text-anchor="middle">{p.exercicio}</text>
        ))}
      </svg>
      <figcaption class="apagado pequeno">
        Linhas: máximo (vermelha), prudencial (contínua) e alerta (tracejada).
      </figcaption>
    </figure>
  )
}

function Anual({ linhas }: { linhas: ResultadoAnual[] }) {
  return (
    <section class="secao">
      <span class="rotulo">Receita e despesa do ano</span>
      <div class="tabela">
        <table class="compacta">
          <thead><tr><th>Ano</th><th class="num">Receita</th><th class="num">Despesa paga</th></tr></thead>
          <tbody>
            {linhas.map((l) => (
              <tr key={l.exercicio}>
                <td class="mono">{l.exercicio}{l.bimestre < 6 && <span class="apagado pequeno"><br />até {l.bimestre}º bim.</span>}</td>
                <td class="num">{brlCurto(l.receita_realizada)}</td>
                <td class="num">{brlCurto(l.despesa_paga)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p class="apagado pequeno">RREO Anexo 01, receita realizada e despesa paga até o último bimestre publicado de cada ano.</p>
    </section>
  )
}

export function TelaContas() {
  const contas = useCarregar(() => dados.contas(), [])
  return (
    <>
      <Topo titulo="Contas da cidade" sub="Prefeitura, dados que ela mesma declara ao Tesouro (SICONFI)" />
      <main class="conteudo">
        <Carregado estado={contas} oque="as contas">
          {(c) => {
            const serie = [...c.limite_pessoal].sort((a, b) => a.exercicio - b.exercicio || a.periodo - b.periodo)
            return (
              <>
                {serie.length ? <><Medidor ultimo={serie[serie.length - 1]} /><Serie pontos={serie} /></>
                  : <p class="vazio">O SICONFI ainda não trouxe o RGF.</p>}
                {serie.length > 0 && (
                  <div class="tabela">
                    <table class="compacta">
                      <thead><tr><th>Quadr.</th><th class="num">% da RCL</th><th class="num">Pessoal</th></tr></thead>
                      <tbody>
                        {[...serie].reverse().map((p) => (
                          <tr key={`${p.exercicio}-${p.periodo}`}>
                            <td class="mono">{p.periodo}º/{p.exercicio}</td>
                            <td class="num">{pctDireto(p.pct_rcl)}</td>
                            <td class="num">{brlCurto(p.despesa_pessoal)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
                {c.resultado_anual.length > 0 && <Anual linhas={c.resultado_anual} />}
                <Fontes fontes={c.fontes} />
              </>
            )
          }}
        </Carregado>
        <Rodape />
      </main>
    </>
  )
}
