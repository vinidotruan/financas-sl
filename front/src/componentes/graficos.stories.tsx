import type { Meta, StoryObj } from '@storybook/preact-vite'
import type { Emenda } from '../tipos'
import { CargosEmendas, PizzaAreas } from './graficos'

const meta: Meta = { title: 'Gráficos' }
export default meta

// Totais reais das emendas Pix de São Leopoldo (19/11/2026), uma emenda de exemplo por área.
const AREAS: [string, number, string][] = [
  ['Saúde', 2835000, 'Deputado federal'], ['Desporto e Lazer', 1976000, 'Deputado federal'],
  ['Mais de uma área', 1559000, 'Deputado federal'], ['Assistência Social', 1042750, 'Senador'],
  ['Urbanismo', 892000, 'Deputado federal'], ['Segurança Pública', 620372.5, 'Deputado federal'],
  ['Comércio e Serviços', 398000, 'Deputada federal'], ['Gestão Ambiental', 199000, 'Deputado federal'],
  ['Habitação', 198000, 'Deputado federal'], ['Educação', 198000, 'Deputado federal'],
  ['Sem área informada', 155000, 'Senador'], ['Cultura', 150000, 'Deputado federal'],
  ['Direitos da Cidadania', 150000, 'Deputado federal'],
]
const EMENDAS: Emenda[] = AREAS.map(([area, indicado, cargo], i) => ({
  codigo_emenda: String(i), codigo: `2025/${4000 + i}`, parlamentar: `Parlamentar ${i + 1}`, cargo,
  codigo_autor: String(i % 6), ano: 2025, planos: 1, indicado, transferido: indicado / 2, executado_relatorio: null,
  areas: [{ area, indicado }],
}))

/** Pizza das emendas por área: 5 fatias com cor e "Outras", com as áreas de dentro listadas. */
export const Pizza: StoryObj = { render: () => <PizzaAreas emendas={EMENDAS} todas={EMENDAS} /> }

/** Uma área só: o círculo inteiro. */
export const PizzaDeUmaArea: StoryObj = {
  name: 'Pizza de uma área',
  render: () => <PizzaAreas emendas={EMENDAS.slice(0, 1)} todas={EMENDAS} />,
}

/** Indicado por cargo: deputados federais e senadores. */
export const PorCargo: StoryObj = { name: 'Por cargo', render: () => <CargosEmendas emendas={EMENDAS} /> }
