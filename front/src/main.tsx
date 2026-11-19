import '@fontsource/archivo/latin-600.css'
import '@fontsource/archivo/latin-700.css'
import '@fontsource/public-sans/latin-400.css'
import '@fontsource/public-sans/latin-500.css'
import '@fontsource/public-sans/latin-600.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import '@fontsource/ibm-plex-mono/latin-600.css'
import './tokens.css'
import './estilo.css'
import { render } from 'preact'
import { App } from './app'
import { dados } from './dados'
import { aplicarTema } from './telas/fontes'

aplicarTema()
dados.fontes().then((f) => { document.title = `Finanças de ${f.ente.nome}` }).catch(() => {})
render(<App />, document.getElementById('app')!)
