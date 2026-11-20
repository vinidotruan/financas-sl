import type { ComponentChildren } from 'preact'

/* Peças da aba Início (D44): cada cartão responde uma pergunta, com um número grande, um gráfico
   simples quando ajuda e um link para a tela de detalhe. */

export function CartaoPergunta(props: {
  pergunta: string; children: ComponentChildren; href?: string; rotuloLink?: string
}) {
  return (
    <section class="cartao pergunta">
      <h2 class="rotulo">{props.pergunta}</h2>
      {props.children}
      {props.href && <a class="ver" href={props.href}>{props.rotuloLink ?? 'Ver mais'}</a>}
    </section>
  )
}

/** Uma linha das barras: o nome, o valor formatado e, se tiver, o link. */
export interface LinhaValor { chave: string; nome: string; valor: number; href?: string }

/** Barras horizontais proporcionais ao maior valor, com o valor à direita. */
export function BarrasValor({ linhas, formato }: { linhas: LinhaValor[]; formato: (n: number) => string }) {
  if (!linhas.length) return null
  const maior = Math.max(...linhas.map((l) => l.valor))
  return (
    <ul class="barras-valor">
      {linhas.map((l) => {
        const conteudo = (
          <>
            <span class="linha-topo"><span class="nome">{l.nome}</span><span class="num">{formato(l.valor)}</span></span>
            <span class="barra" aria-hidden="true"><i style={{ width: `${maior > 0 ? Math.max(0, l.valor / maior) * 100 : 0}%` }} /></span>
          </>
        )
        return <li key={l.chave}>{l.href ? <a href={l.href}>{conteudo}</a> : <span class="item-barra">{conteudo}</span>}</li>
      })}
    </ul>
  )
}

/** Quanto de um todo já aconteceu (transferido sobre indicado, por exemplo). */
export function BarraProgresso({ parte, todo, rotulo }: { parte: number; todo: number; rotulo: string }) {
  const fracao = todo > 0 ? Math.min(1, Math.max(0, parte / todo)) : 0
  return <div class="barra progresso" role="img" aria-label={rotulo}><i style={{ width: `${fracao * 100}%` }} /></div>
}
