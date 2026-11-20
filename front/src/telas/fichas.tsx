import { useState } from 'preact/hooks'
import { useCarregar } from '../componentes/carregar'
import { Carregado, ChipCargo, Fontes, Foto, ListaSinais, Rodape, Topo } from '../componentes/pecas'
import { dados } from '../dados'
import { brl, brlCurto, data, documento, linkPncp, num, pct, VAZIO } from '../formato'
import { link } from '../rotas'
import type { Fornecedor } from '../tipos'

function semAcento(t: string) {
  return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

export function TelaFichas({ lista, ordem }: { lista: 'parlamentares' | 'fornecedores'; ordem?: string }) {
  const [busca, setBusca] = useState('')
  const parlamentares = useCarregar(() => dados.parlamentares(), [])
  const fornecedores = useCarregar(() => dados.fornecedores(), [])
  const termo = semAcento(busca.trim())

  return (
    <>
      <Topo titulo="Fichas" sub="Quem mandou dinheiro e quem recebeu" />
      <main class="conteudo">
        <div class="filtros" role="group" aria-label="Tipo de ficha">
          <a class="filtro" aria-pressed={lista === 'parlamentares'} href={link.fichas('parlamentares')} style={{ textDecoration: 'none' }}>Parlamentares</a>
          <a class="filtro" aria-pressed={lista === 'fornecedores'} href={link.fichas('fornecedores')} style={{ textDecoration: 'none' }}>Fornecedores</a>
        </div>
        <label class="sr" for="busca">Buscar</label>
        <input id="busca" type="search" placeholder={lista === 'parlamentares' ? 'Buscar parlamentar' : 'Buscar fornecedor'}
          value={busca} onInput={(e) => setBusca((e.target as HTMLInputElement).value)} />

        {lista === 'parlamentares' ? (
          <Carregado estado={parlamentares} oque="os parlamentares">
            {(ps) => {
              const vis = ps.filter((p) => !termo || semAcento(p.nome).includes(termo))
              return vis.length ? (
                <>
                <p class="apagado pequeno">
                  Quanto cada deputado federal e senador indicou para a cidade em emendas Pix (transferências
                  especiais), do maior valor para o menor, e quanto disso já foi transferido.
                </p>
                <ul class="lista">
                  {vis.map((p) => (
                    <li key={p.codigo}>
                      <a href={link.parlamentar(p.codigo)}>
                        <span class="pessoa">
                          <Foto arquivo={p.foto} nome={p.nome} />
                          <span class="pessoa-corpo">
                            <span class="linha-topo"><span class="titulo">{p.nome} <ChipCargo cargo={p.cargo} /></span><ValorRotulado valor={p.indicado} rotulo="indicados" /></span>
                            <span class="apagado pequeno">
                              {p.transferido ? `${brlCurto(p.transferido)} transferidos` : 'nada transferido ainda'} · {p.emendas} {p.emendas === 1 ? 'emenda' : 'emendas'} · {p.planos} {p.planos === 1 ? 'plano' : 'planos'} · {p.primeiro_ano === p.ultimo_ano ? p.primeiro_ano : `${p.primeiro_ano} a ${p.ultimo_ano}`}
                            </span>
                          </span>
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
                </>
              ) : <p class="vazio">Ninguém com esse nome.</p>
            }}
          </Carregado>
        ) : (
          <Carregado estado={fornecedores} oque="os fornecedores">
            {(fs) => {
              // "pago-2025": pelo pago da prefeitura no ano (TCE-RS); sem ordem, pelo contratado (PNCP)
              const anoPago = ordem?.startsWith('pago-') ? ordem.slice(5) : null
              const anos = [...new Set(fs.flatMap((f) => Object.keys(f.pago_prefeitura ?? {})))].sort().reverse()
              const valor = (f: Fornecedor) => (anoPago ? f.pago_prefeitura?.[anoPago] ?? 0 : f.valor_total)
              const vis = fs
                .filter((f) => !termo || semAcento(f.nome).includes(termo) || (f.ni ?? '').includes(termo))
                // por pago, só quem a prefeitura pagou naquele ano; por contratado, todos (empresa só do TCE-RS entra com "–")
                .filter((f) => !anoPago || valor(f) !== 0)
                // por pago, as empresas vêm antes dos repasses: as 5 do topo são as 5 do cartão do Início
                .sort((a, b) => (anoPago ? Number(a.repasse) - Number(b.repasse) : 0) || valor(b) - valor(a)
                  || (a.id ?? '').localeCompare(b.id ?? ''))
              const mostrados = vis.slice(0, 100)
              return (
                <>
                  <label class="sr" for="ordem">Ordenar</label>
                  <select id="ordem" class="seletor" value={ordem ?? ''}
                    onChange={(e) => { location.hash = link.fichas('fornecedores', (e.target as HTMLSelectElement).value || undefined) }}>
                    <option value="">Maior contratado (PNCP)</option>
                    {anos.map((a) => <option key={a} value={`pago-${a}`}>Maior pago em {a} (TCE-RS)</option>)}
                  </select>
                  {vis.length ? (
                <>
                  <p class="apagado pequeno">
                    {anoPago
                      ? `Quanto a prefeitura pagou a cada credor em ${anoPago}, do maior para o menor (TCE-RS). Empresas primeiro; órgãos públicos e bancos vêm depois, com um selo: recebem repasses e retenções.`
                      : 'Quanto cada empresa ou pessoa tem em contratos com os órgãos da cidade (valor global, já com os aditivos), do maior para o menor.'}{' '}
                    {vis.length > mostrados.length ? `Mostrando os ${mostrados.length} maiores de ${num(vis.length)}; use a busca para achar os outros.` : `${num(vis.length)} fornecedores.`}
                  </p>
                  <ul class="lista">
                    {mostrados.map((f, i) => {
                      const conteudo = (
                        <>
                          <span class="linha-topo">
                            <span class="titulo">{f.nome}{f.repasse && <> <span class="chip cargo">órgão público ou banco</span></>}</span>
                            <ValorRotulado valor={valor(f)} rotulo={anoPago ? `pagos em ${anoPago}` : 'contratados'} />
                          </span>
                          <span class="apagado pequeno">
                            {f.contratos
                              ? `${f.contratos} ${f.contratos === 1 ? 'contrato' : 'contratos'} · ${pct(f.pct_direto)} sem licitação`
                              : 'sem contrato no PNCP'}
                            {f.pago_total ? ` · ${brlCurto(f.pago_total)} pagos (TCE-RS)` : ''}
                          </span>
                        </>
                      )
                      return (
                        <li key={f.id ?? `pf-${i}`}>
                          {f.id ? <a href={link.fornecedor(f.id)}>{conteudo}</a> : <div class="item">{conteudo}</div>}
                        </li>
                      )
                    })}
                  </ul>
                </>
                  ) : <p class="vazio">Nenhum fornecedor com esse nome.</p>}
                </>
              )
            }}
          </Carregado>
        )}
        <Rodape />
      </main>
    </>
  )
}

export function TelaParlamentar({ codigo }: { codigo: string }) {
  const ficha = useCarregar(() => dados.parlamentar(codigo), [codigo])
  return (
    <Carregado estado={ficha} oque="o parlamentar">
      {(p) => (
        <>
          <Topo titulo={p.nome} volta={link.fichas('parlamentares')} avatar={<Foto arquivo={p.foto} nome={p.nome} grande />} sub={
            <>
              <ChipCargo cargo={p.cargo} />{p.cargo && ' '}
              {[p.uf, `código de autor ${p.codigo}`].filter(Boolean).join(' · ')}
              {p.link && <> · <a href={p.link} target="_blank" rel="noopener">{p.cargo?.startsWith('Senador') ? 'perfil no Senado' : 'perfil na Câmara dos Deputados'}</a></>}
            </>
          } />
          <main class="conteudo">
            <div class="trio">
              <div class="cartao"><span class="rotulo">Emendas</span><span class="valor">{num(p.emendas)}</span></div>
              <div class="cartao"><span class="rotulo">Indicado</span><span class="valor">{brlCurto(p.indicado)}</span></div>
              <div class="cartao"><span class="rotulo">Transferido</span><span class="valor">{brlCurto(p.transferido)}</span></div>
            </div>
            <section class="secao">
              <span class="rotulo">Emendas para a cidade</span>
              <ul class="lista">
                {p.emendas_lista.map((e) => (
                  <li key={e.codigo_emenda}>
                    <a href={link.emenda(e.codigo_emenda)}>
                      <span class="linha-topo"><span class="mono"><strong>{e.codigo}</strong></span><span class="valor">{brl(e.indicado)}</span></span>
                      <span class="apagado pequeno">{e.ano} · {e.planos} {e.planos === 1 ? 'plano' : 'planos'} · {brl(e.transferido)} transferidos</span>
                    </a>
                  </li>
                ))}
              </ul>
            </section>
            <section class="secao">
              <span class="rotulo">Sinais nas emendas</span>
              <ListaSinais sinais={p.sinais} vazio="Nenhum sinal nas emendas deste parlamentar." />
            </section>
            <p class="apagado pequeno">Só emendas Pix (transferências especiais) por enquanto. As demais emendas federais e as estaduais entram nas próximas fases.</p>
            <Fontes fontes={p.fontes} />
            <Rodape />
          </main>
        </>
      )}
    </Carregado>
  )
}

export function TelaFornecedor({ id }: { id: string }) {
  const ficha = useCarregar(() => dados.fornecedor(id), [id])
  return (
    <Carregado estado={ficha} oque="o fornecedor">
      {(f) => (
        <>
          <Topo titulo={f.nome} sub={`${f.pessoa_fisica ? 'Pessoa física ou MEI' : 'CNPJ'} ${documento(f.ni)}`} volta={link.fichas('fornecedores')} />
          <main class="conteudo">
            <div class="trio">
              <div class="cartao"><span class="rotulo">Contratos</span><span class="valor">{num(f.contratos)}</span></div>
              <div class="cartao"><span class="rotulo">Contratado</span><span class="valor">{f.contratos ? brlCurto(f.valor_total) : VAZIO}</span></div>
              <div class="cartao"><span class="rotulo">Pago</span><span class="valor">{f.pago_total ? brlCurto(f.pago_total) : VAZIO}</span></div>
            </div>
            {f.repasse && <p class="apagado pequeno"><span class="chip cargo">órgão público ou banco</span> Recebe repasses ou retenções, não é venda de bem ou serviço.</p>}
            {f.pagos.length > 0 && (
              <section class="secao">
                <span class="rotulo">Pagamentos por ano (TCE-RS)</span>
                <ul class="lista">
                  {f.pagos.map((p) => (
                    <li key={`${p.orgao_nome}-${p.ano}`}>
                      <div class="item"><span class="linha-topo"><span>{p.ano} · {p.orgao_nome}</span><span class="valor">{brl(p.valor)}</span></span></div>
                    </li>
                  ))}
                </ul>
              </section>
            )}
            <section class="secao">
              <span class="rotulo">Sinais</span>
              <ListaSinais sinais={f.sinais} vazio="Nenhum sinal nos contratos deste fornecedor." />
            </section>
            <section class="secao">
              <span class="rotulo">Contratos</span>
              <ul class="lista">
                {f.contratos_lista.map((c) => {
                  const pncp = linkPncp(c.id)
                  return (
                    <li key={c.id}>
                      <div class="item">
                        <span class="titulo">{c.objeto}</span>
                        <span class="linha-topo pequeno">
                          <span class="apagado">{c.modalidade ?? 'modalidade não informada'} · {data(c.data_assinatura)}</span>
                          <span class="valor">{brl(c.valor_global)}</span>
                        </span>
                        <span class="chips">
                          {c.emergencial && <span class="chip atencao">emergencial</span>}
                          {c.contratacao_direta && <span class="chip">sem licitação</span>}
                          {c.valor_global !== c.valor_inicial && <span class="chip">inicial {brl(c.valor_inicial)}</span>}
                        </span>
                        <span class="apagado pequeno">{c.unidade || c.orgao_nome}</span>
                        {pncp && <a class="pequeno" href={pncp} target="_blank" rel="noopener">Contrato no PNCP ↗</a>}
                      </div>
                    </li>
                  )
                })}
              </ul>
            </section>
            {f.contratos > 0 && <p class="apagado pequeno">Primeiro contrato em {data(f.primeiro_contrato)}, último em {data(f.ultimo_contrato) ?? VAZIO}. Sem licitação: {pct(f.pct_direto)} do valor.</p>}
            <Fontes fontes={f.fontes} />
            <Rodape />
          </main>
        </>
      )}
    </Carregado>
  )
}

/** Valor da lista com o que ele é, embaixo: "R$ 2,69 mi / indicados" */
function ValorRotulado({ valor, rotulo }: { valor: number; rotulo: string }) {
  return (
    <span class="valor-rotulado">
      <span class="valor">{brlCurto(valor)}</span>
      <span class="rotulo-valor">{rotulo}</span>
    </span>
  )
}
