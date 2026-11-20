import { BarraProgresso, BarrasValor, CartaoPergunta } from '../componentes/cartoes'
import { useCarregar } from '../componentes/carregar'
import { MedidorLRF } from '../componentes/medidor'
import { Carregado, Fontes, Rodape, Topo } from '../componentes/pecas'
import { dados } from '../dados'
import { brlCurto, data, num, pct, pctDireto } from '../formato'
import { link } from '../rotas'
import type { Inicio } from '../tipos'

/* A primeira tela (D44): o que uma pessoa da cidade quer saber sobre o dinheiro dela em 10 segundos.
   Um cartão por pergunta, cada um com a data do dado e um link para o detalhe. Descreve, não julga. */

function QuemMaisRecebeu({ r }: { r: Inicio['recebeu'] }) {
  if (!r) {
    return (
      <CartaoPergunta pergunta="Quem mais recebeu da prefeitura">
        <p class="vazio">O TCE-RS ainda não trouxe um ano completo de pagamentos.</p>
      </CartaoPergunta>
    )
  }
  return (
    <CartaoPergunta pergunta={`Quem mais recebeu da prefeitura em ${r.ano}`} href={link.fichas('fornecedores')}
      rotuloLink="Ver todas">
      <span class="valor-grande">{brlCurto(r.total)}</span>
      <p class="apagado pequeno">pagos no ano a empresas, pessoas e outros órgãos. As cinco empresas que mais receberam:</p>
      <BarrasValor formato={brlCurto}
        linhas={r.empresas.map((e) => ({ chave: e.id, nome: e.nome, valor: e.valor, href: link.fornecedor(e.id) }))} />
      <p class="apagado pequeno">
        Sem órgãos públicos e bancos, que recebem repasses. Fonte: TCE-RS
        {r.ate ? `; ${r.ano_corrente} vai até ${data(r.ate)}, porque a prefeitura manda os dados ao Tribunal com atraso.` : '.'}
      </p>
    </CartaoPergunta>
  )
}

function Emendas({ e }: { e: Inicio['emendas'] }) {
  const fracao = e.indicado > 0 ? e.transferido / e.indicado : 0
  return (
    <CartaoPergunta pergunta="Quanto das emendas chegou à cidade" href={link.emendas()} rotuloLink="Ver emendas">
      <span class="valor-grande">{pct(fracao)}</span>
      <BarraProgresso parte={e.transferido} todo={e.indicado} rotulo={`${pct(fracao)} do indicado já foi transferido`} />
      <p class="apagado pequeno">{brlCurto(e.transferido)} transferidos de {brlCurto(e.indicado)} indicados em emendas Pix.</p>
    </CartaoPergunta>
  )
}

function Parados({ p }: { p: Inicio['parados'] }) {
  return (
    <CartaoPergunta pergunta="Pedidos parados na Câmara" href={link.pedidos()} rotuloLink="Ver pedidos">
      <span class="valor-grande">{num(p.total)}</span>
      <p class="apagado pequeno">
        Pedidos de providência e indicações em comissão, pauta ou parecer na Câmara há mais de {p.dias} dias.
      </p>
      {p.por_situacao.length > 0 && (
        <ul class="pequeno situacoes">
          {p.por_situacao.slice(0, 3).map((s) => <li key={s.situacao}>{s.situacao}: <strong>{num(s.pedidos)}</strong></li>)}
        </ul>
      )}
      {p.sem_situacao > 0 && (
        <p class="apagado pequeno">
          Ainda conferindo a situação de {num(p.sem_situacao)} pedidos: ela chega aos poucos, 2.000 por dia.
        </p>
      )}
    </CartaoPergunta>
  )
}

function Partidos({ partidos }: { partidos: Inicio['partidos'] }) {
  return (
    <CartaoPergunta pergunta="Partido que mais pediu obras e serviços">
      {partidos.length ? (
        <>
          <span class="valor-grande">{partidos[0].partido}</span>
          <BarrasValor formato={num} linhas={partidos.map((p) => ({ chave: p.partido, nome: p.partido, valor: p.pedidos }))} />
          <p class="apagado pequeno">
            Pedidos de providência e indicações, pelo partido do vereador na época de cada pedido. Pedido de dois
            vereadores do mesmo partido conta uma vez.
          </p>
        </>
      ) : <p class="vazio">Sem pedidos com partido.</p>}
    </CartaoPergunta>
  )
}

function Bairros({ bairros }: { bairros: Inicio['bairros'] }) {
  return (
    <CartaoPergunta pergunta="Bairros que mais pedem" href={link.pedidos()} rotuloLink="Ver pedidos">
      {bairros.length ? <BarrasValor formato={num} linhas={bairros.map((b) => ({ chave: String(b.id), nome: b.nome, valor: b.pedidos }))} />
        : <p class="vazio">Sem pedidos com bairro.</p>}
    </CartaoPergunta>
  )
}

function Folha({ f }: { f: Inicio['folha'] }) {
  if (!f) return null
  return (
    <CartaoPergunta pergunta="A folha da prefeitura está perto do limite?" href={link.contas()} rotuloLink="Ver contas">
      <span class="valor-grande">{pctDireto(f.pct_rcl)}</span>
      <MedidorLRF ultimo={f} />
      <p class="apagado pequeno">
        da receita corrente líquida vai para pessoal ({f.periodo}º quadrimestre de {f.exercicio}). A Lei de
        Responsabilidade Fiscal acende o alerta em {pctDireto(f.limite_alerta, 1)} e o máximo é {pctDireto(f.limite_maximo, 0)}.
      </p>
    </CartaoPergunta>
  )
}

export function TelaInicio() {
  const inicio = useCarregar(() => dados.inicio(), [])
  const fontes = useCarregar(() => dados.fontes(), [])
  const cidade = fontes.dados?.ente.nome ?? 'A cidade'
  return (
    <>
      <Topo titulo={cidade}
        sub={inicio.dados ? `Para onde vai o dinheiro da cidade · dados de ${data(inicio.dados.data_referencia)}`
          : 'Para onde vai o dinheiro da cidade'} />
      <main class="conteudo">
        <Carregado estado={inicio} oque="o início">
          {(i) => (
            <>
              <QuemMaisRecebeu r={i.recebeu} />
              <Emendas e={i.emendas} />
              <Parados p={i.parados} />
              <Partidos partidos={i.partidos} />
              <Bairros bairros={i.bairros} />
              <Folha f={i.folha} />
              <CartaoPergunta pergunta="Maior salário do mês" tracejado>
                <span class="valor-grande apagado">em breve</span>
                <p class="apagado pequeno">
                  O portal da prefeitura só mostra a folha de pagamento com login. Ela vai entrar por um pedido de
                  Lei de Acesso à Informação ou por um arquivo baixado à mão.
                </p>
              </CartaoPergunta>
              <Fontes fontes={i.fontes} />
              <p class="pequeno rodape-inicio"><a href={link.fontes()}>De onde vem cada dado</a></p>
            </>
          )}
        </Carregado>
      </main>
      <Rodape />
    </>
  )
}
