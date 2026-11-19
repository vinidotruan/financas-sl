import { useState } from 'preact/hooks'
import { useCarregar } from '../componentes/carregar'
import { Carregado, ChipSeveridade, ChipsFonte, Fontes, ListaSinais, Rodape, Topo } from '../componentes/pecas'
import { dados } from '../dados'
import { AREA, frase, num } from '../formato'
import { link } from '../rotas'
import type { Regra, Sinal } from '../tipos'

function classeFaixa(r: Regra) {
  if (!r.ativos) return 'zero'
  return r.severidade === 'alto' ? 'alto' : r.severidade === 'baixo' ? 'baixo' : ''
}

function CartaoRegra({ r }: { r: Regra }) {
  return (
    <a class={`cartao faixa ${classeFaixa(r)}`} href={link.regra(r.id)}>
      <ChipSeveridade severidade={r.severidade} area={r.area} />
      <h2>{r.nome}</h2>
      <p>
        <strong class="num">{num(r.ativos)}</strong> {r.ativos === 1 ? 'caso' : 'casos'}
        {r.novos > 0 && r.novos !== r.ativos && <span class="apagado"> · {num(r.novos)} sem revisão</span>}
        {r.novos > 0 && r.novos === r.ativos && <span class="apagado"> · nenhum revisado ainda</span>}
      </p>
      <p class="apagado pequeno limiar">{frase(r.limiar)}</p>
      <ChipsFonte fontes={r.fontes} />
    </a>
  )
}

export function TelaSinais() {
  const regras = useCarregar(() => dados.regras(), [])
  const fontes = useCarregar(() => dados.fontes(), [])
  const [area, setArea] = useState('todas')
  const publico = fontes.dados?.modo === 'publico'

  return (
    <>
      <Topo titulo="Sinais pra olhar" sub={`Pontos de atenção nos dados públicos de ${fontes.dados?.ente.nome ?? "da cidade"}`} />
      <main class="conteudo">
        {publico && (
          <p class="aviso info">
            Aparecem aqui só os sinais que já foram revisados e confirmados. Cada um traz o que pode explicá-lo
            sem irregularidade.
          </p>
        )}
        <Carregado estado={regras} oque="os sinais">
          {(lista) => {
            const areas = [...new Set(lista.map((r) => r.area))]
            const filtradas = lista.filter((r) => area === 'todas' || r.area === area)
            const com = filtradas.filter((r) => r.ativos > 0)
            const sem = filtradas.filter((r) => r.ativos === 0)
            return (
              <>
                <div class="filtros" role="group" aria-label="Filtrar por área">
                  {['todas', ...areas].map((a) => (
                    <button key={a} type="button" class="filtro" aria-pressed={area === a} onClick={() => setArea(a)}>
                      {a === 'todas' ? 'Todos' : AREA[a] ?? a}
                    </button>
                  ))}
                </div>
                {com.length ? com.map((r) => <CartaoRegra key={r.id} r={r} />)
                  : <p class="vazio">{publico ? 'Nenhum sinal revisado nesta área ainda.' : 'Nenhum sinal nesta área por enquanto.'}</p>}
                {sem.length > 0 && (
                  <section class="secao">
                    <span class="rotulo">{publico ? 'Regras sem sinal revisado' : 'Sem casos hoje'}</span>
                    <ul class="lista">
                      {sem.map((r) => (
                        <li key={r.id}>
                          <a href={link.regra(r.id)}>
                            <span class="titulo">{r.nome}</span>
                            <span class="apagado pequeno limiar">{frase(r.limiar)}</span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
              </>
            )
          }}
        </Carregado>
        <Rodape />
      </main>
    </>
  )
}

type Ordem = 'valor' | 'recente'

function ordenar(sinais: Sinal[], ordem: Ordem): Sinal[] {
  const copia = [...sinais]
  if (ordem === 'valor') copia.sort((a, b) => (b.valor_observado ?? -Infinity) - (a.valor_observado ?? -Infinity))
  else copia.sort((a, b) => (b.quando ?? '').localeCompare(a.quando ?? ''))
  return copia
}

export function TelaRegra({ id }: { id: string }) {
  const regras = useCarregar(() => dados.regras(), [])
  const sinais = useCarregar(() => dados.sinais(), [])
  const [ordem, setOrdem] = useState<Ordem>('valor')

  return (
    <Carregado estado={regras} oque="a regra">
      {(lista) => {
        const r = lista.find((x) => x.id === id)
        if (!r) {
          return (
            <>
              <Topo titulo="Regra não encontrada" volta={link.sinais()} />
              <main class="conteudo"><p class="vazio">Não existe a regra {id}.</p></main>
            </>
          )
        }
        return (
          <>
            <Topo titulo={r.nome} sub={<ChipSeveridade severidade={r.severidade} area={r.area} />} volta={link.sinais()} />
            <main class="conteudo">
              <div class="cartao">
                <div class="bloco"><span class="rotulo">Quando aparece</span><p>{frase(r.limiar)}</p></div>
                <div class="bloco"><span class="rotulo">Base legal</span><p>{r.base_legal}</p></div>
              </div>
              <div class="aviso info">
                <span class="rotulo">Pode ser normal se</span>
                <p>{r.pode_ser_normal_se}</p>
              </div>
              <div class="bloco"><span class="rotulo">Como verificar</span><p>{r.como_verificar}</p></div>

              <section class="secao">
                <div class="linha-topo">
                  <span class="rotulo">{num(r.ativos)} {r.ativos === 1 ? 'caso' : 'casos'}</span>
                  <div class="filtros" role="group" aria-label="Ordenar casos">
                    <button type="button" class="filtro" aria-pressed={ordem === 'valor'} onClick={() => setOrdem('valor')}>Maior valor</button>
                    <button type="button" class="filtro" aria-pressed={ordem === 'recente'} onClick={() => setOrdem('recente')}>Mais recente</button>
                  </div>
                </div>
                <Carregado estado={sinais} oque="os casos">
                  {(todos) => (
                    <ListaSinais
                      sinais={ordenar(todos.filter((s) => s.regra_id === r.id), ordem)}
                      formato={r.observado?.formato}
                      rotulo={r.observado?.rotulo}
                      vazio="Nenhum caso nos dados de hoje."
                    />
                  )}
                </Carregado>
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
