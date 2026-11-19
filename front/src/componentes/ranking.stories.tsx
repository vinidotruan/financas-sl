import type { Meta, StoryObj } from '@storybook/preact-vite'
import { Ranking } from './ranking'

const meta: Meta<typeof Ranking> = { title: 'Componentes/Ranking', component: Ranking }
export default meta
type Historia = StoryObj<typeof Ranking>

export const DePessoas: Historia = {
  name: 'De pessoas, com foto',
  args: {
    vazio: 'Nenhum pedido com esse filtro.',
    linhas: [
      { chave: '775', nome: 'Marcelo Pitol', cargo: 'Vereador', detalhe: 'PSD', n: 1643, href: '#', foto: 'exemplo.jpg' },
      { chave: '752', nome: 'Lemos', cargo: 'Vereador', detalhe: 'PSB', n: 1462, href: '#', foto: 'exemplo.jpg' },
      { chave: '153', nome: 'Iara Cardoso', cargo: 'Vereadora', detalhe: 'PDT', n: 1085, href: '#', foto: 'exemplo.jpg' },
      { chave: '777', nome: 'Johnson Souza', cargo: 'Vereador', n: 13, href: '#', foto: null },
      { chave: '411', nome: 'Comissão de Obras Públicas', cargo: 'Comissão', n: 4, href: '#', foto: null },
    ],
  },
}

export const DeTemas: Historia = {
  name: 'De temas, sem foto',
  args: {
    vazio: 'Nenhum pedido nesse ano.',
    linhas: [
      { chave: 'a', nome: 'Água, esgoto e drenagem', n: 2568 },
      { chave: 'p', nome: 'Pavimentação e buracos', n: 2534 },
      { chave: 'l', nome: 'Limpeza e capina', n: 1999 },
    ],
  },
}

export const Vazio: Historia = { args: { vazio: 'Nenhum pedido com esse filtro.', linhas: [] } }
