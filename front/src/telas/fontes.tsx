import { useState } from 'preact/hooks'
import { useCarregar } from '../componentes/carregar'
import { Carregado, Rodape, Topo } from '../componentes/pecas'
import { dados, MODO_DADOS } from '../dados'
import { dataHora, FONTE, num } from '../formato'

type Tema = 'sistema' | 'light' | 'dark'

function lerTema(): Tema {
  try {
    const t = localStorage.getItem('slf-tema')
    return t === 'light' || t === 'dark' ? t : 'sistema'
  } catch {
    return 'sistema'
  }
}

export function aplicarTema(t: Tema = lerTema()) {
  if (t === 'sistema') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', t)
}

const O_QUE_TRAZ: Record<string, string> = {
  transferegov: 'Emendas Pix: planos de ação, empenhos, ordens bancárias, planos de trabalho e relatórios de gestão.',
  siconfi: 'Contas que a prefeitura declara ao Tesouro: RGF (pessoal, dívida) e RREO (receita e despesa).',
  pncp: 'Contratos, a compra de origem e os termos aditivos da prefeitura, das fundações, do SEMAE e da Câmara.',
  camara: 'Pedidos de providência e indicações dos vereadores, a situação de cada pedido na Câmara, os bairros e o cadastro dos vereadores de todas as legislaturas, com foto.',
  congresso: 'Cadastro de deputados federais (Câmara dos Deputados) e senadores (Senado), para o nome oficial e o cargo de quem indicou cada emenda.',
  tce: 'Empenhos, liquidações e pagamentos da prefeitura, da Câmara, do SEMAE e do Hospital Centenário, por credor (TCE-RS). Chega com meses de atraso.',
}

export function TelaFontes() {
  const fontes = useCarregar(() => dados.fontes(), [])
  const [tema, setTema] = useState<Tema>(lerTema)

  function escolher(t: Tema) {
    setTema(t)
    try { localStorage.setItem('slf-tema', t) } catch { /* sem armazenamento: vale até fechar */ }
    aplicarTema(t)
  }

  return (
    <>
      <Topo titulo="Fontes" sub="De onde vem cada dado e quando foi a última coleta boa" />
      <main class="conteudo">
        <Carregado estado={fontes} oque="as fontes">
          {(f) => (
            <>
              <ul class="lista">
                {f.fontes.map((x) => (
                  <li key={x.fonte}>
                    <div class="item">
                      <div class="linha-topo">
                        <span class="titulo">{FONTE[x.fonte] ?? x.fonte}</span>
                        {x.coleta ? <span class="chip ok">ok</span> : <span class="chip atencao">sem coleta</span>}
                      </div>
                      <span class="pequeno">{O_QUE_TRAZ[x.fonte]}</span>
                      <span class="apagado pequeno">
                        {x.coleta ? `Última coleta boa em ${dataHora(x.coletado_em)}, ${num(x.linhas)} linhas.` : 'Ainda sem coleta boa.'}
                      </span>
                      {x.link && <a class="pequeno" href={x.link} target="_blank" rel="noopener">Documentação da fonte ↗</a>}
                    </div>
                  </li>
                ))}
              </ul>
              {f.erros_de_regra.length > 0 && (
                <div class="aviso" role="alert">
                  <strong>Regras que falharam na última atualização</strong>
                  {f.erros_de_regra.map((e) => <span key={e.regra_id} class="pequeno">{e.regra_id}: {e.mensagem}</span>)}
                </div>
              )}
              <div class="cartao">
                <span class="rotulo">Como este painel funciona</span>
                <p class="pequeno">
                  Os dados vêm de APIs públicas, são guardados como vieram e passam por regras que apontam pontos de
                  atenção. Uma fonte que falha não apaga a outra: vale a última coleta boa de cada uma.
                </p>
                <p class="pequeno">
                  {f.modo === 'publico'
                    ? 'Modo público: só aparecem sinais revisados, e pessoa física (inclusive MEI) não aparece pelo nome.'
                    : 'Modo privado: aparecem todos os sinais e dá para revisar cada um.'}
                  {MODO_DADOS === 'estatico' ? ' Esta é uma cópia estática, gerada na última atualização.' : ''}
                </p>
              </div>
            </>
          )}
        </Carregado>
        <section class="secao">
          <span class="rotulo">Tema</span>
          <div class="filtros" role="group" aria-label="Tema">
            {(['sistema', 'light', 'dark'] as Tema[]).map((t) => (
              <button key={t} type="button" class="filtro" aria-pressed={tema === t} onClick={() => escolher(t)}>
                {t === 'sistema' ? 'Do aparelho' : t === 'light' ? 'Claro' : 'Escuro'}
              </button>
            ))}
          </div>
        </section>
        <Rodape />
      </main>
    </>
  )
}
