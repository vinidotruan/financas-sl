import { useState } from 'preact/hooks'
import { useCarregar } from '../componentes/carregar'
import { Carregado, ChipCargo, Fontes, Rodape, Topo } from '../componentes/pecas'
import { dados } from '../dados'
import { num } from '../formato'
import { link } from '../rotas'
import type { Pedido, Pedidos } from '../tipos'

type Ano = number | 'todos'
const TODOS = 'Todos os temas'

interface Linha { chave: string; nome: string; cargo?: string | null; detalhe?: string; n: number; href?: string }

function somar<T extends { ano: number; tema: string; pedidos: number }>(
  linhas: T[], ano: Ano, tema: string | undefined, chave: (l: T) => string, rotulo: (l: T) => Omit<Linha, 'n' | 'chave'>,
): Linha[] {
  const acc = new Map<string, Linha>()
  for (const l of linhas) {
    if (ano !== 'todos' && l.ano !== ano) continue
    if (tema && l.tema !== tema) continue
    const k = chave(l)
    const atual = acc.get(k) ?? { chave: k, ...rotulo(l), n: 0 }
    atual.n += l.pedidos
    acc.set(k, atual)
  }
  return [...acc.values()].sort((a, b) => b.n - a.n || a.nome.localeCompare(b.nome))
}

function Ranking({ linhas, vazio, limite }: { linhas: Linha[]; vazio: string; limite?: number }) {
  if (!linhas.length) return <p class="vazio">{vazio}</p>
  const max = linhas[0].n
  const mostradas = limite ? linhas.slice(0, limite) : linhas
  return (
    <ul class="lista">
      {mostradas.map((l) => {
        const conteudo = (
          <>
            <span class="linha-topo">
              <span class="titulo">{l.nome}{l.cargo && <> <ChipCargo cargo={l.cargo} /></>}{l.detalhe && <span class="apagado"> · {l.detalhe}</span>}</span>
              <span class="valor">{num(l.n)}</span>
            </span>
            <div class="barra" aria-hidden="true"><i style={{ width: `${(l.n / max) * 100}%` }} /></div>
          </>
        )
        return <li key={l.chave}>{l.href ? <a href={l.href}>{conteudo}</a> : <div class="item">{conteudo}</div>}</li>
      })}
    </ul>
  )
}

function FiltroAno({ anos, ano, mudar }: { anos: number[]; ano: Ano; mudar: (a: Ano) => void }) {
  return (
    <div class="filtros" role="group" aria-label="Filtrar por ano">
      <button type="button" class="filtro" aria-pressed={ano === 'todos'} onClick={() => mudar('todos')}>Todos</button>
      {anos.map((a) => (
        <button key={a} type="button" class="filtro mono" aria-pressed={ano === a} onClick={() => mudar(a)}>{a}</button>
      ))}
    </div>
  )
}

function FiltroTema({ temas, tema, mudar }: { temas: string[]; tema?: string; mudar: (t?: string) => void }) {
  return (
    <>
      <label class="sr" for="tema">Tema</label>
      <select id="tema" class="seletor" value={tema ?? TODOS}
        onChange={(e) => { const v = (e.target as HTMLSelectElement).value; mudar(v === TODOS ? undefined : v) }}>
        <option>{TODOS}</option>
        {temas.map((t) => <option key={t}>{t}</option>)}
      </select>
    </>
  )
}

export function TelaPedidos({ tema }: { tema?: string }) {
  const pedidos = useCarregar(() => dados.pedidos(), [])
  const [ano, setAno] = useState<Ano>('todos')

  return (
    <>
      <Topo titulo="Pedidos à prefeitura" sub="O que os vereadores pediram: obras, placas, limpeza, iluminação" />
      <main class="conteudo">
        <Carregado estado={pedidos} oque="os pedidos">
          {(p: Pedidos) => {
            if (!p.total) return <p class="vazio">Ainda não há pedidos coletados da Câmara.</p>
            const filtro = (l: { ano: number; tema: string }) => (ano === 'todos' || l.ano === ano) && (!tema || l.tema === tema)
            const total = p.por_tema.filter(filtro).reduce((s, l) => s + l.pedidos, 0)
            const semBairro = p.sem_bairro.filter(filtro).reduce((s, l) => s + l.pedidos, 0)
            const vereadores = somar(p.por_vereador, ano, tema, (l) => String(l.id),
              (l) => ({ nome: l.nome, cargo: l.cargo, detalhe: l.partido ?? undefined, href: link.vereador(l.id) }))
            const temas = somar(p.por_tema, ano, undefined, (l) => l.tema,
              (l) => ({ nome: l.tema, href: link.pedidos(l.tema) }))
            const bairros = somar(p.por_bairro, ano, tema, (l) => String(l.id), (l) => ({ nome: l.nome }))
            return (
              <>
                <FiltroAno anos={p.anos} ano={ano} mudar={setAno} />
                <FiltroTema temas={p.temas} tema={tema} mudar={(t) => { location.hash = link.pedidos(t) }} />
                <div class="cartao">
                  <span class="rotulo">{tema ?? 'Todos os temas'} · {ano === 'todos' ? 'todos os anos' : ano}</span>
                  <span class="valor-grande">{num(total)}</span>
                  <span class="apagado pequeno">pedidos de providência e indicações</span>
                </div>

                <section class="secao">
                  <span class="rotulo">Quem mais pediu</span>
                  <Ranking linhas={vereadores} vazio="Nenhum pedido com esse filtro." />
                  <p class="apagado pequeno">Pedido assinado por mais de um vereador conta para cada um, então a soma pode passar do total.</p>
                </section>

                {!tema && (
                  <section class="secao">
                    <span class="rotulo">Por tema</span>
                    <Ranking linhas={temas} vazio="Nenhum pedido nesse ano." />
                  </section>
                )}

                <section class="secao">
                  <span class="rotulo">Por bairro</span>
                  <Ranking linhas={bairros} vazio="Nenhum pedido com bairro identificado." />
                  {semBairro > 0 && <p class="apagado pequeno">{num(semBairro)} pedidos sem bairro identificado pela Câmara.</p>}
                </section>

                <p class="aviso info pequeno">
                  O tema vem de palavras da ementa (arquivo <code>slf/temas.yaml</code>) e pode errar. Um pedido feito não diz se a
                  prefeitura atendeu: a Câmara não publica essa resposta junto.
                </p>
                <Fontes fontes={p.fontes} />
              </>
            )
          }}
        </Carregado>
        <Rodape />
      </main>
    </>
  )
}

const LIMITE = 100

function ItemPedido({ p }: { p: Pedido }) {
  return (
    <li>
      <div class="item">
        <span class="linha-topo apagado pequeno">
          <span>{p.especie} <span class="mono">{p.numero}/{p.ano}</span></span>
        </span>
        <span>{p.ementa}</span>
        <span class="chips">
          <a class="chip" href={link.pedidos(p.tema)} style={{ textDecoration: 'none' }}>{p.tema}</a>
          {p.bairros && <span class="chip">{p.bairros}</span>}
        </span>
        {p.url && <a class="pequeno" href={p.url} target="_blank" rel="noopener">Ver na Câmara ↗</a>}
      </div>
    </li>
  )
}

export function TelaVereador({ id }: { id: string }) {
  const v = useCarregar(() => dados.vereador(id), [id])
  const [ano, setAno] = useState<Ano>('todos')
  const [tema, setTema] = useState<string | undefined>(undefined)

  return (
    <Carregado estado={v} oque="o vereador">
      {(ver) => {
        const anos = [...new Set(ver.pedidos.map((p) => p.ano))].sort((a, b) => b - a)
        const temasPresentes = [...new Set(ver.pedidos.map((p) => p.tema))].sort()
        const filtrados = ver.pedidos.filter((p) => (ano === 'todos' || p.ano === ano) && (!tema || p.tema === tema))
        const porTema = new Map<string, number>()
        for (const p of ver.pedidos.filter((p) => ano === 'todos' || p.ano === ano)) porTema.set(p.tema, (porTema.get(p.tema) ?? 0) + 1)
        const temas: Linha[] = [...porTema.entries()].map(([t, n]) => ({ chave: t, nome: t, n })).sort((a, b) => b.n - a.n)
        const mostrados = filtrados.slice(0, LIMITE)
        return (
          <>
            <Topo titulo={ver.nome} volta={link.pedidos()}
              sub={<><ChipCargo cargo={ver.cargo} />{ver.cargo && ver.partido && ' '}{ver.partido}</>} />
            <main class="conteudo">
              <FiltroAno anos={anos} ano={ano} mudar={setAno} />
              <div class="cartao">
                <span class="rotulo">Pedidos {ano === 'todos' ? 'em todos os anos' : `em ${ano}`}</span>
                <span class="valor-grande">{num(temas.reduce((s, t) => s + t.n, 0))}</span>
              </div>
              <section class="secao">
                <span class="rotulo">Por tema</span>
                <Ranking linhas={temas} vazio="Nenhum pedido nesse ano." />
              </section>
              <section class="secao">
                <span class="rotulo">Pedidos</span>
                <FiltroTema temas={temasPresentes} tema={tema} mudar={setTema} />
                <p class="apagado pequeno">
                  {filtrados.length > LIMITE
                    ? `Mostrando os ${LIMITE} mais recentes de ${num(filtrados.length)}. Filtre por ano ou tema para ver os outros.`
                    : `${num(filtrados.length)} ${filtrados.length === 1 ? 'pedido' : 'pedidos'}, do mais recente para o mais antigo.`}
                </p>
                {mostrados.length ? <ul class="lista">{mostrados.map((p) => <ItemPedido key={p.id} p={p} />)}</ul>
                  : <p class="vazio">Nenhum pedido com esse filtro.</p>}
              </section>
              <Fontes fontes={ver.fontes} />
              <Rodape />
            </main>
          </>
        )
      }}
    </Carregado>
  )
}
