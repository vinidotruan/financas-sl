import { useState } from 'preact/hooks'
import { useCarregar } from '../componentes/carregar'
import { Carregado, ChipCargo, ChipsFonte, Fontes, ListaSinais, Rodape, Topo } from '../componentes/pecas'
import { dados } from '../dados'
import { brl, brlCurto, data, FONTE, num, pct, VAZIO } from '../formato'
import { link } from '../rotas'
import type { Emenda, Plano, Rastro } from '../tipos'

function fracao(parte: number | null, todo: number): number {
  return parte == null || !todo ? 0 : Math.min(1, Math.max(0, parte / todo))
}

function CartaoEmenda({ e }: { e: Emenda }) {
  return (
    <a class="cartao" href={link.emenda(e.codigo_emenda)}>
      <span class="linha-topo"><span class="mono"><strong>{e.codigo}</strong></span><span class="valor">{brlCurto(e.indicado)}</span></span>
      <span class="apagado pequeno">{e.parlamentar} <ChipCargo cargo={e.cargo} /> · {e.ano} · {e.planos} {e.planos === 1 ? 'plano' : 'planos'}</span>
      <div class="barra" aria-hidden="true"><i style={{ width: `${fracao(e.transferido, e.indicado) * 100}%` }} /></div>
      <span class="pequeno">
        {e.transferido ? <>{brlCurto(e.transferido)} transferidos ({pct(fracao(e.transferido, e.indicado))})</> : 'Nada transferido ainda'}
        {e.executado_relatorio != null && <span class="apagado"> · {brlCurto(e.executado_relatorio)} executados no relatório</span>}
      </span>
    </a>
  )
}

export function TelaEmendas() {
  const emendas = useCarregar(() => dados.emendas(), [])
  const [ano, setAno] = useState<number | 'todos'>('todos')
  return (
    <>
      <Topo titulo="Emendas" sub="Transferências especiais (emendas Pix) para a prefeitura" />
      <main class="conteudo">
        <Carregado estado={emendas} oque="as emendas">
          {(lista) => {
            const anos = [...new Set(lista.map((e) => e.ano))].sort((a, b) => b - a)
            const filtradas = lista.filter((e) => ano === 'todos' || e.ano === ano)
            const indicado = filtradas.reduce((s, e) => s + e.indicado, 0)
            const transferido = filtradas.reduce((s, e) => s + e.transferido, 0)
            const planos = filtradas.reduce((s, e) => s + e.planos, 0)
            return (
              <>
                <div class="filtros" role="group" aria-label="Filtrar por ano">
                  <button type="button" class="filtro" aria-pressed={ano === 'todos'} onClick={() => setAno('todos')}>Todos</button>
                  {anos.map((a) => (
                    <button key={a} type="button" class="filtro mono" aria-pressed={ano === a} onClick={() => setAno(a)}>{a}</button>
                  ))}
                </div>
                <div class="trio">
                  <div class="cartao"><span class="rotulo">Planos</span><span class="valor">{num(planos)}</span></div>
                  <div class="cartao"><span class="rotulo">Indicado</span><span class="valor">{brlCurto(indicado)}</span></div>
                  <div class="cartao"><span class="rotulo">Transferido</span><span class="valor">{brlCurto(transferido)}</span></div>
                </div>
                {filtradas.map((e) => <CartaoEmenda key={e.codigo_emenda} e={e} />)}
              </>
            )
          }}
        </Carregado>
        <Rodape />
      </main>
    </>
  )
}

function CartaoPlano({ p, metas }: { p: Plano; metas: Rastro['metas'] }) {
  const doPlano = metas.filter((m) => m.id_plano_acao === p.id_plano_acao)
  return (
    <div class="cartao">
      <span class="linha-topo"><span class="mono pequeno">{p.codigo_plano}</span><span class="valor">{brl(p.valor_indicado)}</span></span>
      <dl class="kv">
        <dt>Situação do plano de ação</dt><dd>{p.situacao}{p.motivo_impedimento ? ` (${p.motivo_impedimento})` : ''}</dd>
        <dt>Plano de trabalho</dt><dd>{p.situacao_plano_trabalho ?? VAZIO}</dd>
        <dt>Execução prevista</dt><dd class="num">{data(p.prazo_inicio)} a {data(p.prazo_fim)}</dd>
        <dt>Transferido</dt><dd class="num">{brl(p.transferido)}{p.primeira_ob ? ` em ${data(p.primeira_ob)}` : ''}</dd>
        <dt>Relatórios de gestão</dt>
        <dd>
          {p.relatorios_entregues ? `${p.relatorios_entregues} entregue(s), último ${p.tipo_relatorio} de ${data(p.data_relatorio)}` : 'Nenhum entregue'}
          {p.relatorios_em_elaboracao ? ` · ${p.relatorios_em_elaboracao} em elaboração` : ''}
        </dd>
        {p.transferido > 0 && <><dt>Prazo do relatório parcial</dt><dd class="num">{data(p.prazo_relatorio_parcial)}</dd></>}
      </dl>
      {doPlano.length > 0 && (
        <details>
          <summary class="pequeno">{doPlano.length} {doPlano.length === 1 ? 'meta' : 'metas'} · {doPlano[0].objeto}</summary>
          <ul class="pequeno">
            {doPlano.map((m, i) => <li key={i}>{m.nome_meta}{m.desc_meta ? `: ${m.desc_meta}` : ''}</li>)}
          </ul>
        </details>
      )}
    </div>
  )
}

export function TelaRastro({ codigo }: { codigo: string }) {
  const rastro = useCarregar(() => dados.rastro(codigo), [codigo])
  return (
    <Carregado estado={rastro} oque="a emenda">
      {(r) => {
        const executado = r.valores.find((v) => v.etapa.startsWith('Executado'))
        return (
          <>
            <Topo titulo={`Emenda ${r.codigo_formatado}`}
              sub={<><a href={link.parlamentar(r.parlamentar.codigo)}>{r.parlamentar.nome}</a> <ChipCargo cargo={r.parlamentar.cargo} /></>}
              volta={link.emendas()} />
            <main class="conteudo">
              <section class="secao">
                <span class="rotulo">O valor em cada fonte</span>
                <ul class="lista">
                  {r.valores.map((v) => (
                    <li key={v.etapa}>
                      <div class="item">
                        <span class="linha-topo">
                          <span>{v.etapa}</span>
                          {v.valor != null && <span class="valor">{brl(v.valor)}</span>}
                        </span>
                        <span class="linha-topo">
                          <span class="chip fonte">{FONTE[v.fonte] ?? v.fonte}</span>
                          {v.valor == null && <span class="apagado pequeno">{v.nota ?? VAZIO}</span>}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              </section>

              <section class="secao">
                <span class="rotulo">Rastro</span>
                <ol class="passos">
                  <li class="passo">
                    <span class="ponto">1</span>
                    <div class="texto">
                      <ChipsFonte fontes={['transferegov']} />
                      <span>Indicada por <a href={link.parlamentar(r.parlamentar.codigo)}>{r.parlamentar.nome}</a> em {r.ano}: {r.planos.length} {r.planos.length === 1 ? 'plano de ação' : 'planos de ação'} somando {brl(r.valores[0].valor)}.</span>
                    </div>
                  </li>
                  <li class="passo">
                    <span class="ponto">2</span>
                    <div class="texto">
                      <ChipsFonte fontes={['transferegov']} />
                      {r.transferencias.length ? (
                        <>
                          <span>Transferida à prefeitura em {r.transferencias.length} {r.transferencias.length === 1 ? 'ordem bancária' : 'ordens bancárias'}:</span>
                          <ul class="pequeno">
                            {r.transferencias.map((t) => <li key={t.numero_ob} class="num">{data(t.data_ob)} · {brl(t.valor)}</li>)}
                          </ul>
                        </>
                      ) : <span>Nenhuma ordem bancária ainda.</span>}
                    </div>
                  </li>
                  <li class={`passo ${executado?.valor == null ? 'incerto' : ''}`}>
                    <span class="ponto">3</span>
                    <div class="texto">
                      <ChipsFonte fontes={['transferegov']} />
                      <span>{executado?.valor != null ? `${brl(executado.valor)} executados segundo o relatório de gestão.` : 'Nenhum relatório de gestão entregue, então a execução não aparece aqui.'}</span>
                    </div>
                  </li>
                  <li class="passo incerto">
                    <span class="ponto">4</span>
                    <div class="texto">
                      <ChipsFonte fontes={['prefeitura']} />
                      <span class="apagado">Empenhos, pagamentos e quem recebeu vêm do portal da prefeitura, na fase 2.</span>
                    </div>
                  </li>
                </ol>
              </section>

              <section class="secao">
                <span class="rotulo">{r.planos.length === 1 ? 'Plano de ação' : 'Planos de ação'}</span>
                {r.planos.map((p) => <CartaoPlano key={p.id_plano_acao} p={p} metas={r.metas} />)}
              </section>

              <section class="secao">
                <span class="rotulo">Sinais ligados</span>
                <ListaSinais sinais={r.sinais} vazio="Nenhum sinal nesta emenda." />
              </section>
              <Fontes fontes={r.fontes} />
              <Rodape />
            </main>
          </>
        )
      }}
    </Carregado>
  )
}
