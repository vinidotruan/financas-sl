import type { StorybookConfig } from '@storybook/preact-vite'

// Design system do painel: os componentes de verdade (src/componentes), nos temas claro e escuro.
// Publicado junto com o site em /storybook/. Sem telemetria: nada sai da máquina de quem roda.
const config: StorybookConfig = {
  framework: '@storybook/preact-vite',
  stories: ['../src/**/*.mdx', '../src/**/*.stories.tsx'],
  addons: ['@storybook/addon-docs'],
  // foto de exemplo neutra (sem rosto de ninguém) no mesmo caminho que a API usa: api/fotos/
  staticDirs: ['./public'],
  core: { disableTelemetry: true },
}
export default config
