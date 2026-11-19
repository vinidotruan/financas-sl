import type { ComponentChildren } from 'preact'
import { ErroDados } from '../dados'
import { AREA, data, dataHora, FONTE, formatar, SEVERIDADE } from '../formato'
import { link, voltar } from '../rotas'
import type { FonteRef, Formato, Severidade, Sinal, Status } from '../tipos'
import type { Estado } from './carregar'

export function Topo(props: { titulo: string; sub?: ComponentChildren; volta?: string }) {
  return (
    <header class="topo">
      <div class="topo-dentro">
        {props.volta && (
          <button class="voltar" type="button" onClick={() => voltar(props.volta!)}>
            <span aria-hidden="true">‹</span> Voltar
          </button>
        )}
        <h1>{props.titulo}</h1>
        {props.sub && <p class="sub">{props.sub}</p>}
      </div>
    </header>
  )
}

/** Mostra carregando, erro ou o conteúdo, para qualquer recurso. */
export function Carregado<T>(props: { estado: Estado<T>; oque: string; children: (dados: T) => ComponentChildren }) {
  const { estado } = props
  if (estado.carregando && !estado.dados) {
    return <div class="carregando" aria-busy="true" aria-label={`Carregando ${props.oque}`}><i /><i /><i /></div>
  }
  if (estado.erro) {
    const e = estado.erro
    const naoAchou = e instanceof ErroDados && e.status === 404
    return (
      <div class="aviso" role="alert">
        <strong>{naoAchou ? `Não encontrei ${props.oque}.` : `Não deu para carregar ${props.oque}.`}</strong>
        <span>{naoAchou ? 'O link pode ser antigo, ou o item não aparece no modo público.' : e.message}</span>
        {!naoAchou && <button class="botao" type="button" onClick={estado.tentarDeNovo}>Tentar de novo</button>}
      </div>
    )
  }
  return <>{estado.dados !== null && props.children(estado.dados)}</>
}

export function ChipSeveridade(props: { severidade: Severidade; area?: string }) {
  const classe = props.severidade === 'alto' ? 'alto' : props.severidade === 'baixo' ? 'baixo' : ''
  return (
    <span class={`sev ${classe}`}>
      {SEVERIDADE[props.severidade] ?? props.severidade}{props.area ? ` · ${AREA[props.area] ?? props.area}` : ''}
    </span>
  )
}

const CLASSE_STATUS: Record<Status, string> = {
  novo: '', 'em análise': 'atencao', descartado: '', confirmado: 'alto', encaminhado: 'ok',
}

export function ChipStatus(props: { status: Status }) {
  return <span class={`chip ${CLASSE_STATUS[props.status] ?? ''}`}>{props.status}</span>
}

export function ChipsFonte(props: { fontes: (FonteRef | string)[] }) {
  return (
    <span class="chips">
      {props.fontes.map((f) => {
        const nome = typeof f === 'string' ? f : f.nome
        return <span class="chip fonte" key={nome}>{FONTE[nome] ?? nome}</span>
      })}
    </span>
  )
}

/** De onde veio o dado e quando foi a última coleta boa */
export function Fontes(props: { fontes: FonteRef[] }) {
  return (
    <section class="secao" aria-label="Fontes">
      <span class="rotulo">Fontes</span>
      <ul class="lista">
        {props.fontes.map((f) => (
          <li key={f.nome}>
            <div class="item">
              <div class="linha-topo">
                <span class="titulo">{FONTE[f.nome] ?? f.nome}</span>
                {f.link && <a class="pequeno" href={f.link} target="_blank" rel="noopener">abrir ↗</a>}
              </div>
              <span class="apagado pequeno">Dado de {dataHora(f.coletado_em)}</span>
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

/** Lista de ocorrências de sinal, usada na regra e nas fichas */
export function ListaSinais(props: { sinais: Sinal[]; formato?: Formato; rotulo?: string; vazio?: string }) {
  if (!props.sinais.length) return <p class="vazio">{props.vazio ?? 'Nenhum sinal.'}</p>
  return (
    <ul class="lista">
      {props.sinais.map((s) => (
        <li key={s.id}>
          <a href={link.sinal(s.id)}>
            <span class="linha-topo">
              <ChipSeveridade severidade={s.severidade} area={s.area} />
              {s.status !== 'novo' && <ChipStatus status={s.status} />}
            </span>
            <span class="titulo">{s.titulo}</span>
            <span class="linha-topo apagado pequeno">
              <span>{props.rotulo ?? s.nome}</span>
              {props.formato && <span class="valor">{formatar(s.valor_observado, props.formato)}</span>}
            </span>
            {!s.ativo && <span class="apagado pequeno">Não aparece mais nos dados desde {data(s.ultima_vez)}</span>}
          </a>
        </li>
      ))}
    </ul>
  )
}

export function Rodape() {
  return (
    <p class="rodape">
      Sinais são pontos de atenção calculados a partir de dados públicos, não acusações.
      Cada um mostra a regra, o limiar e o que pode explicá-lo.
    </p>
  )
}
