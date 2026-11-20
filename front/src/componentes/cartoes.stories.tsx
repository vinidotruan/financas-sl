import type { Meta, StoryObj } from '@storybook/preact-vite'
import { brlCurto, num, pct } from '../formato'
import { BarraProgresso, BarrasValor, CartaoPergunta } from './cartoes'

const meta: Meta = { title: 'Cartões do Início' }
export default meta

const EMPRESAS = [
  { chave: '1', nome: 'Green Card (refeição)', valor: 29_450_000, href: '#' },
  { chave: '2', nome: 'IDEAS (saúde)', valor: 28_440_000, href: '#' },
  { chave: '3', nome: 'Instaladora Elétrica Mercúrio', valor: 24_650_000, href: '#' },
  { chave: '4', nome: 'Construsinos', valor: 17_380_000, href: '#' },
  { chave: '5', nome: 'RGE Sul (energia)', valor: 16_880_000, href: '#' },
]

export const PerguntaComBarras: StoryObj = {
  name: 'Pergunta com barras',
  render: () => (
    <CartaoPergunta pergunta="Quem mais recebeu da prefeitura em 2025" href="#" rotuloLink="Ver todas">
      <span class="valor-grande">{brlCurto(944_600_000)}</span>
      <p class="apagado pequeno">pagos no ano a empresas, pessoas e outros órgãos. As cinco empresas que mais receberam:</p>
      <BarrasValor linhas={EMPRESAS} formato={brlCurto} />
    </CartaoPergunta>
  ),
}

export const PerguntaComProgresso: StoryObj = {
  name: 'Pergunta com progresso',
  render: () => (
    <CartaoPergunta pergunta="Quanto das emendas chegou à cidade" href="#" rotuloLink="Ver emendas">
      <span class="valor-grande">{pct(5_545_122.5 / 10_373_122.5)}</span>
      <BarraProgresso parte={5_545_122.5} todo={10_373_122.5} rotulo="53% transferido" />
      <p class="apagado pequeno">R$ 5,55 mi transferidos de R$ 10,37 mi indicados.</p>
    </CartaoPergunta>
  ),
}

export const PerguntaComNumeros: StoryObj = {
  name: 'Pergunta com números',
  render: () => (
    <CartaoPergunta pergunta="Partido que mais pediu obras e serviços">
      <span class="valor-grande">PDT</span>
      <BarrasValor formato={num} linhas={[
        { chave: 'PDT', nome: 'PDT', valor: 3163 }, { chave: 'PSD', nome: 'PSD', valor: 2002 },
        { chave: 'PSB', nome: 'PSB', valor: 1462 }]} />
    </CartaoPergunta>
  ),
}
