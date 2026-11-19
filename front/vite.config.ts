import preact from '@preact/preset-vite'
import { defineConfig } from 'vite'

// base relativa: o mesmo build funciona servido pelo `slf servir` em "/" e numa subpasta do GitHub Pages
export default defineConfig({
  plugins: [preact()],
  base: './',
  build: { outDir: '../site', emptyOutDir: true },
  // em desenvolvimento (npm run dev) a API local responde em /api
  server: { proxy: { '/api': 'http://localhost:8765' } },
})
