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

/** Seis tamanhos (tokens.css). A hierarquia vem do tamanho e do peso; a cor fica para o destaque. */
export const Tipografia: StoryObj = {
  render: () => (
    <div style={{ display: 'grid', gap: '18px' }}>
      <div><span class="rotulo">--t-numero, Archivo 32 negrito, cor de destaque: o número principal da tela</span><div class="valor-grande">R$ 10,37 mi</div></div>
      <div><span class="rotulo">--t-titulo, Archivo 22: título da tela</span><h1>Pedidos à prefeitura</h1></div>
      <div><span class="rotulo">--t-sub, Archivo 17: subtítulo e valor de cartão</span><h2>Quem mais pediu</h2><div class="valor" style={{ fontSize: 'var(--t-sub)' }}>R$ 2,69 mi</div></div>
      <div><span class="rotulo">--t-texto, Public Sans 15: texto corrido e listas</span><p>Solicita ao Poder Executivo Municipal a colocação de duas tampas de bueiro.</p></div>
      <div><span class="rotulo">--t-apoio, Public Sans 13: apoio e rótulos</span><p class="pequeno apagado">Pedido assinado por mais de um vereador conta para cada um.</p></div>
      <div><span class="rotulo">--t-mini, Public Sans 12: chips e abas</span><span class="chip">Limpeza e capina</span></div>
      <div><span class="rotulo">Mono só para códigos</span><span class="mono">2026/42710013</span></div>
    </div>
  ),
}

/** O cartão com o número principal da tela e a trinca de números das fichas. */
export const Cartoes: StoryObj = {
  name: 'Cartões',
  render: () => (
    <div style={{ display: 'grid', gap: '12px' }}>
      <div class="cartao">
        <span class="rotulo">Indicado para a cidade</span>
        <span class="valor-grande">R$ 10,37 mi</span>
        <span class="apagado pequeno">R$ 5,55 mi já transferidos, em 34 planos</span>
      </div>
      <div class="trio">
        <div class="cartao"><span class="rotulo">Planos</span><span class="valor">34</span></div>
        <div class="cartao"><span class="rotulo">Indicado</span><span class="valor">R$ 10,37 mi</span></div>
        <div class="cartao"><span class="rotulo">Transferido</span><span class="valor">R$ 5,55 mi</span></div>
      </div>
    </div>
  ),
}

/** Espaços em múltiplos de 4 e três cantos (tokens.css). Ajustes finos de 2 a 7 px dentro de chips e legendas
 *  ficam no próprio componente. */
export const EspacosECantos: StoryObj = {
  name: 'Espaços e cantos',
  render: () => (
    <div style={{ display: 'grid', gap: 'var(--e-5)' }}>
      <div class="secao">
        <span class="rotulo">Espaços</span>
        {['--e-1', '--e-2', '--e-3', '--e-4', '--e-5'].map((t) => (
          <div key={t} style={{ display: 'grid', gridTemplateColumns: '64px minmax(0, 1fr)', gap: 'var(--e-3)', alignItems: 'center' }}>
            <code class="mono pequeno">{t}</code>
            <span style={{ display: 'block', height: '12px', width: `var(${t})`, background: 'var(--destaque)', borderRadius: '2px' }} />
          </div>
        ))}
      </div>
      <div class="secao">
        <span class="rotulo">Cantos</span>
        <div style={{ display: 'flex', gap: 'var(--e-4)', flexWrap: 'wrap' }}>
          {['--raio-p', '--raio-m', '--raio-pilula'].map((t) => (
            <div key={t} style={{ display: 'grid', gap: 'var(--e-2)', justifyItems: 'center' }}>
              <span style={{ width: '96px', height: '48px', background: 'var(--superficie)', border: '1px solid var(--linha)', borderRadius: `var(${t})` }} />
              <code class="mono pequeno">{t}</code>
            </div>
          ))}
        </div>
      </div>
    </div>
  ),
}
