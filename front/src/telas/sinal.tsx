import { Fragment } from 'preact'
import { useEffect, useState } from 'preact/hooks'
import { useCarregar } from '../componentes/carregar'
import { Carregado, ChipSeveridade, ChipStatus, Fontes, Rodape, Topo } from '../componentes/pecas'
import { dados, podeRevisar, revisar } from '../dados'
import { brl, CAMPOS, data, formatar, frase, linkPncp, preencher } from '../formato'
import { link } from '../rotas'
import type { SinalDetalhe, Status } from '../tipos'

const STATUS: Status[] = ['novo', 'em análise', 'descartado', 'confirmado', 'encaminhado']

function Evidencia({ s }: { s: SinalDetalhe }) {
  const linhas = Object.entries(s.evidencia).filter(([campo, v]) => CAMPOS[campo] !== null && v != null && v !== '')
  if (!linhas.length) return null
  return (
    <section class="secao">
      <span class="rotulo">Evidência</span>
      <div class="cartao">
        <dl class="kv">
          {linhas.map(([campo, v]) => {
            const [rotulo, fmt] = CAMPOS[campo] ?? [campo.replace(/_/g, ' '), 'texto']
            return (
              <Fragment key={campo}>
                <dt>{rotulo}</dt>
                <dd class={fmt === 'texto' || fmt === 'frase' ? '' : 'num'}>{formatar(v, fmt)}</dd>
              </Fragment>
            )
          })}
        </dl>
      </div>
    </section>
  )
}

function Ligacoes({ s }: { s: SinalDetalhe }) {
  const { emenda, contratos } = s.ligacoes
  if (!emenda && !contratos?.length) return null
  return (
    <section class="secao">
      <span class="rotulo">Seguir</span>
      {emenda && <a class="botao cheio" href={link.emenda(emenda)}>Seguir o rastro da emenda</a>}
      {contratos?.length ? (
        <ul class="lista">
          {contratos.map((c) => {
            const pncp = linkPncp(c.id)
            return (
              <li key={c.id}>
                <div class="item">
                  <span class="titulo">{c.objeto}</span>
                  <span class="linha-topo pequeno">
                    {c.fornecedor_id
                      ? <a href={link.fornecedor(c.fornecedor_id)}>{c.fornecedor_nome}</a>
                      : <span class="apagado">{c.fornecedor_nome}</span>}
                    <span class="valor">{brl(c.valor_global)}</span>
                  </span>
                  {pncp && <a class="pequeno" href={pncp} target="_blank" rel="noopener">Contrato no PNCP ↗</a>}
                </div>
              </li>
            )
          })}
        </ul>
      ) : null}
    </section>
  )
}

function Revisao({ s }: { s: SinalDetalhe }) {
  const [status, setStatus] = useState<Status>(s.status)
  const [nota, setNota] = useState(s.nota ?? '')
  const [estado, setEstado] = useState<'parado' | 'salvando' | 'salvo' | 'erro'>('parado')
  const [mensagem, setMensagem] = useState('')
  const mudou = status !== s.status || (nota || null) !== (s.nota || null)

  async function salvar(e: Event) {
    e.preventDefault()
    setEstado('salvando')
    try {
      await revisar(s.id, status, nota.trim() || null)
      s.status = status
      s.nota = nota.trim() || null
      setEstado('salvo')
    } catch (erro) {
      setMensagem((erro as Error).message)
      setEstado('erro')
    }
  }

  return (
    <form class="secao" onSubmit={salvar}>
      <span class="rotulo">Sua revisão</span>
      <div class="status-opcoes" role="group" aria-label="Status">
        {STATUS.map((st) => (
          <button key={st} type="button" aria-pressed={status === st} onClick={() => { setStatus(st); setEstado('parado') }}>
            {st}
          </button>
        ))}
      </div>
      <label class="sr" for="nota">Nota</label>
      <textarea id="nota" placeholder="Nota (só aparece no modo privado)" value={nota}
        onInput={(e) => { setNota((e.target as HTMLTextAreaElement).value); setEstado('parado') }} />
      <button class="botao cheio" type="submit" disabled={!mudou || estado === 'salvando'}>
        {estado === 'salvando' ? 'Salvando…' : 'Salvar revisão'}
      </button>
      {estado === 'salvo' && <p class="apagado pequeno" role="status">Salvo. Vale na tela agora e no banco na próxima atualização.</p>}
      {estado === 'erro' && <p class="aviso" role="alert">Não salvou: {mensagem}</p>}
      <p class="apagado pequeno">
        Só sinais confirmados ou encaminhados aparecem no modo público. Descartado volta a novo se o valor mudar.
      </p>
    </form>
  )
}

export function TelaSinal({ id }: { id: string }) {
  const sinal = useCarregar(() => dados.sinal(id), [id])
  const [revisavel, setRevisavel] = useState(false)
  useEffect(() => { podeRevisar().then(setRevisavel) }, [])

  return (
    <Carregado estado={sinal} oque="o sinal">
      {(s) => (
        <>
          <Topo titulo={s.nome} sub={s.titulo} volta={link.regra(s.regra_id)} />
          <main class="conteudo">
            <div class="chips">
              <ChipSeveridade severidade={s.severidade} area={s.area} />
              <ChipStatus status={s.status} />
              {!s.ativo && <span class="chip">não aparece mais nos dados</span>}
            </div>

            <div class="cartao">
              <span class="rotulo">O que foi visto</span>
              <p>{s.resumo ? preencher(s.resumo, s.evidencia) : s.titulo}</p>
              {s.observado && s.valor_observado != null && (
                <div class="bloco">
                  <span class="apagado pequeno">{s.observado.rotulo}</span>
                  <span class="valor-grande">{formatar(s.valor_observado, s.observado.formato)}</span>
                </div>
              )}
            </div>

            <div class="aviso info">
              <span class="rotulo">Pode ser normal se</span>
              <p>{s.pode_ser_normal_se}</p>
            </div>

            <Evidencia s={s} />

            <section class="secao">
              <span class="rotulo">Regra</span>
              <a class="cartao" href={link.regra(s.regra_id)}>
                <span class="linha-topo"><strong>{s.nome}</strong><span class="mono apagado pequeno">{s.regra_id} v{s.regra_versao}</span></span>
                <p class="pequeno">{frase(s.limiar)}</p>
                <p class="apagado pequeno">{s.base_legal}</p>
              </a>
              <div class="bloco"><span class="rotulo">Como verificar</span><p>{s.como_verificar}</p></div>
            </section>

            <Ligacoes s={s} />

            <section class="secao">
              <span class="rotulo">Datas</span>
              <div class="cartao">
                <dl class="kv">
                  <dt>Data do fato</dt><dd class="num">{data(s.quando)}</dd>
                  <dt>Visto pela primeira vez</dt><dd class="num">{data(s.primeira_vez)}</dd>
                  <dt>Visto por último</dt><dd class="num">{data(s.ultima_vez)}</dd>
                </dl>
              </div>
            </section>

            <Fontes fontes={s.fontes} />
            {revisavel && <Revisao s={s} />}
            {!revisavel && s.nota && <div class="bloco"><span class="rotulo">Nota</span><p>{s.nota}</p></div>}
            <Rodape />
          </main>
        </>
      )}
    </Carregado>
  )
}
