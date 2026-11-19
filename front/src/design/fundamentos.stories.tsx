import type { Meta, StoryObj } from '@storybook/preact-vite'
import { Amostra, Grupo } from './Amostra'

const meta: Meta = { title: 'Fundamentos', parameters: { layout: 'padded' } }
export default meta

/** As cores do painel (tokens.css), por função. Visual sóbrio: cinza na base, cor só com motivo.
 *  Troque o tema na barra de cima para ver as duas versões. */
export const Cores: StoryObj = {
  render: () => (
    <>
      <Grupo titulo="Neutros: tudo o que não precisa chamar atenção">
        <Amostra token="--fundo" nota="fundo da página" />
        <Amostra token="--superficie" nota="cartões e listas" />
        <Amostra token="--linha" nota="bordas" />
        <Amostra token="--texto" />
        <Amostra token="--apagado" nota="texto de apoio" />
        <Amostra token="--neutro-suave" nota="chip neutro, trilho da barra, caixa vazia" />
      </Grupo>
      <Grupo titulo="Destaque: o número principal da tela, links e filtro ativo">
        <Amostra token="--destaque" nota="número principal, links, barras" />
        <Amostra token="--destaque-suave" />
      </Grupo>
      <Grupo titulo="Estados dos sinais: reservados, sempre com rótulo">
        <Amostra token="--alto" />
        <Amostra token="--alto-suave" />
        <Amostra token="--atencao" />
        <Amostra token="--atencao-suave" />
        <Amostra token="--baixo" />
        <Amostra token="--baixo-suave" />
      </Grupo>
      <Grupo titulo="Gráficos: categorias, validadas para daltonismo">
        <Amostra token="--s1" />
        <Amostra token="--s2" />
        <Amostra token="--s3" />
        <Amostra token="--s4" />
        <Amostra token="--s5" />
        <Amostra token="--s-outras" />
      </Grupo>
    </>
  ),
}

/** Os estilos de texto que as telas usam hoje. */
export const Tipografia: StoryObj = {
  render: () => (
    <div style={{ display: 'grid', gap: '18px' }}>
      <div><span class="rotulo">Título da tela (h1, Archivo 22)</span><h1>Pedidos à prefeitura</h1></div>
      <div><span class="rotulo">Número em destaque (valor-grande, mono 24)</span><div class="valor-grande">10.555</div></div>
      <div><span class="rotulo">Valor (mono 15)</span><div class="valor">R$ 2,69 mi</div></div>
      <div><span class="rotulo">Texto (Public Sans 15)</span><p>Solicita ao Poder Executivo Municipal a colocação de duas tampas de bueiro.</p></div>
      <div><span class="rotulo">Texto pequeno (13)</span><p class="pequeno apagado">Pedido assinado por mais de um vereador conta para cada um.</p></div>
      <div><span class="rotulo">Rótulo (mono 11, caixa alta)</span><div class="rotulo">Quem mais pediu</div></div>
    </div>
  ),
}

/** Cartões e a trinca de números do topo das telas. */
export const Cartoes: StoryObj = {
  name: 'Cartões',
  render: () => (
    <div style={{ display: 'grid', gap: '12px' }}>
      <div class="cartao">
        <span class="rotulo">Todos os temas · todos os anos</span>
        <span class="valor-grande">10.555</span>
        <span class="apagado pequeno">pedidos de providência e indicações</span>
      </div>
      <div class="trio">
        <div class="cartao"><span class="rotulo">Planos</span><span class="valor">34</span></div>
        <div class="cartao"><span class="rotulo">Indicado</span><span class="valor">R$ 10,37 mi</span></div>
        <div class="cartao"><span class="rotulo">Transferido</span><span class="valor">R$ 5,55 mi</span></div>
      </div>
    </div>
  ),
}
