import { useState } from 'preact/hooks'
import { useCarregar } from '../componentes/carregar'
import { Carregado, ChipCargo, Fontes, ListaSinais, Rodape, Topo } from '../componentes/pecas'
import { dados } from '../dados'
import { brl, brlCurto, data, documento, linkPncp, num, pct, VAZIO } from '../formato'
import { link } from '../rotas'

function semAcento(t: string) {
  return t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

export function TelaFichas({ lista }: { lista: 'parlamentares' | 'fornecedores' }) {
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
                <ul class="lista">
                  {vis.map((p) => (
                    <li key={p.codigo}>
                      <a href={link.parlamentar(p.codigo)}>
                        <span class="linha-topo"><span class="titulo">{p.nome} <ChipCargo cargo={p.cargo} /></span><span class="valor">{brlCurto(p.indicado)}</span></span>
                        <span class="apagado pequeno">
                          {p.emendas} {p.emendas === 1 ? 'emenda' : 'emendas'} · {p.planos} {p.planos === 1 ? 'plano' : 'planos'} · {p.primeiro_ano === p.ultimo_ano ? p.primeiro_ano : `${p.primeiro_ano} a ${p.ultimo_ano}`}
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : <p class="vazio">Ninguém com esse nome.</p>
            }}
          </Carregado>
        ) : (
          <Carregado estado={fornecedores} oque="os fornecedores">
            {(fs) => {
              const vis = fs.filter((f) => !termo || semAcento(f.nome).includes(termo) || (f.ni ?? '').includes(termo))
              const mostrados = vis.slice(0, 100)
              return vis.length ? (
                <>
                  <p class="apagado pequeno">
                    {vis.length > mostrados.length ? `Mostrando os ${mostrados.length} maiores de ${num(vis.length)}. Use a busca para achar os outros.` : `${num(vis.length)} fornecedores, do maior valor contratado para o menor.`}
                  </p>
                  <ul class="lista">
                    {mostrados.map((f, i) => {
                      const conteudo = (
                        <>
                          <span class="linha-topo"><span class="titulo">{f.nome}</span><span class="valor">{brlCurto(f.valor_total)}</span></span>
                          <span class="apagado pequeno">
                            {f.contratos} {f.contratos === 1 ? 'contrato' : 'contratos'} · {pct(f.pct_direto)} sem licitação
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
              ) : <p class="vazio">Nenhum fornecedor com esse nome.</p>
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
          <Topo titulo={p.nome} volta={link.fichas('parlamentares')} sub={
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
              <div class="cartao"><span class="rotulo">Valor</span><span class="valor">{brlCurto(f.valor_total)}</span></div>
              <div class="cartao"><span class="rotulo">Sem licitação</span><span class="valor">{pct(f.pct_direto)}</span></div>
            </div>
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
            <p class="apagado pequeno">Primeiro contrato em {data(f.primeiro_contrato)}, último em {data(f.ultimo_contrato) ?? VAZIO}.</p>
            <Fontes fontes={f.fontes} />
            <Rodape />
          </main>
        </>
      )}
    </Carregado>
  )
}
