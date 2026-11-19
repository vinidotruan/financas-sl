import type { Meta, StoryObj } from '@storybook/preact-vite'
import { ChipCargo, Foto, Topo } from './pecas'

const meta: Meta = { title: 'Componentes/Peças' }
export default meta

/** Chips: cargo (contorno), tema e bairro (neutro), fonte e estados. */
export const Chips: StoryObj = {
  render: () => (
    <div style={{ display: 'grid', gap: '12px' }}>
      <div class="chips"><ChipCargo cargo="Vereador" /><ChipCargo cargo="Vereadora" /><ChipCargo cargo="Deputada federal" /><ChipCargo cargo="Senador" /><ChipCargo cargo="Comissão" /></div>
      <div class="chips"><span class="chip">Limpeza e capina</span><span class="chip">Vicentina</span></div>
      <div class="chips"><span class="chip fonte">Transferegov</span><span class="chip ok">ok</span><span class="chip atencao">atenção</span><span class="chip alto">alto</span></div>
    </div>
  ),
}

/** Foto oficial reduzida, ou as iniciais quando a fonte não tem foto (ou a imagem não carrega). */
export const Fotos: StoryObj = {
  render: () => (
    <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
      <Foto arquivo="exemplo.jpg" nome="Pessoa de Exemplo" />
      <Foto arquivo={null} nome="Johnson Souza" />
      <Foto arquivo="exemplo.jpg" nome="Pessoa de Exemplo" grande />
      <Foto arquivo={null} nome="Diógenes Padilha de Souza (Johnson)" grande />
      <Foto arquivo="nao-existe.jpg" nome="Foto Quebrada" />
    </div>
  ),
}

export const Cabecalho: StoryObj = {
  name: 'Cabeçalho',
  render: () => (
    <div style={{ display: 'grid', gap: '16px' }}>
      <Topo titulo="Pedidos à prefeitura" sub="O que os vereadores pediram: obras, placas, limpeza, iluminação" />
      <Topo titulo="Marcelo Pitol" volta="#/pedidos" avatar={<Foto arquivo="exemplo.jpg" nome="Marcelo Pitol" grande />}
        sub={<><ChipCargo cargo="Vereador" /> PSD</>} />
    </div>
  ),
}
