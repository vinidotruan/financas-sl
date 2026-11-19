import { Abas } from './componentes/abas'
import { abaDa, useRota } from './rotas'
import { TelaContas } from './telas/contas'
import { TelaEmendas, TelaRastro } from './telas/emendas'
import { TelaFichas, TelaFornecedor, TelaParlamentar } from './telas/fichas'
import { TelaFontes } from './telas/fontes'
import { TelaPedidos, TelaVereador } from './telas/pedidos'
import { TelaSinal } from './telas/sinal'
import { TelaRegra, TelaSinais } from './telas/sinais'

export function App() {
  const rota = useRota()
  let tela
  switch (rota.tela) {
    case 'sinais': tela = <TelaSinais />; break
    case 'regra': tela = <TelaRegra key={rota.id} id={rota.id} />; break
    case 'sinal': tela = <TelaSinal key={rota.id} id={rota.id} />; break
    case 'emendas': tela = <TelaEmendas />; break
    case 'emenda': tela = <TelaRastro key={rota.codigo} codigo={rota.codigo} />; break
    case 'fichas': tela = <TelaFichas lista={rota.lista} />; break
    case 'parlamentar': tela = <TelaParlamentar key={rota.codigo} codigo={rota.codigo} />; break
    case 'fornecedor': tela = <TelaFornecedor key={rota.id} id={rota.id} />; break
    case 'pedidos': tela = <TelaPedidos tema={rota.tema} />; break
    case 'vereador': tela = <TelaVereador key={rota.id} id={rota.id} />; break
    case 'contas': tela = <TelaContas />; break
    case 'fontes': tela = <TelaFontes />; break
  }
  return (
    <>
      {tela}
      <Abas atual={abaDa(rota)} />
    </>
  )
}
