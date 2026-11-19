import '@fontsource/archivo/latin-600.css'
import '@fontsource/archivo/latin-700.css'
import '@fontsource/public-sans/latin-400.css'
import '@fontsource/public-sans/latin-500.css'
import '@fontsource/public-sans/latin-600.css'
import '@fontsource/ibm-plex-mono/latin-400.css'
import '@fontsource/ibm-plex-mono/latin-500.css'
import '@fontsource/ibm-plex-mono/latin-600.css'
import '../src/estilo.css'
import type { Preview } from '@storybook/preact-vite'

// O tema escolhido na barra do Storybook vai para <html data-theme>, como o seletor de tema do site faz.
const preview: Preview = {
  globalTypes: {
    tema: {
      description: 'Tema claro ou escuro',
      toolbar: {
        title: 'Tema',
        icon: 'contrast',
        items: [{ value: 'light', title: 'Claro' }, { value: 'dark', title: 'Escuro' }],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: { tema: 'light' },
  decorators: [
    (Story, ctx) => {
      document.documentElement.setAttribute('data-theme', ctx.globals.tema === 'dark' ? 'dark' : 'light')
      return <div style={{ maxWidth: '720px' }}><Story /></div>
    },
  ],
  parameters: { layout: 'padded', controls: { expanded: true } },
}
export default preview
