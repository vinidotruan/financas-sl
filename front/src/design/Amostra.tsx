import { useEffect, useRef, useState } from 'preact/hooks'

/** Quadrado com a cor de uma variável de design, o nome e o valor que ela tem no tema atual. */
export function Amostra({ token, nota }: { token: string; nota?: string }) {
  const ref = useRef<HTMLDivElement>(null)
  const [valor, setValor] = useState('')
  useEffect(() => {
    const ler = () => setValor(getComputedStyle(document.documentElement).getPropertyValue(token).trim())
    ler()
    const obs = new MutationObserver(ler)
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
    return () => obs.disconnect()
  }, [token])
  return (
    <div ref={ref} style={{ display: 'grid', gridTemplateColumns: '48px minmax(0, 1fr)', gap: '10px', alignItems: 'center' }}>
      <span style={{ width: '48px', height: '48px', borderRadius: '10px', background: `var(${token})`, boxShadow: 'inset 0 0 0 1px var(--linha)' }} />
      <span style={{ display: 'grid', gap: '2px', minWidth: 0 }}>
        <code class="mono pequeno">{token}</code>
        <span class="pequeno apagado">{valor}{nota ? ` · ${nota}` : ''}</span>
      </span>
    </div>
  )
}

export function Grupo({ titulo, children }: { titulo: string; children: preact.ComponentChildren }) {
  return (
    <section class="secao" style={{ marginBottom: '20px' }}>
      <span class="rotulo">{titulo}</span>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>{children}</div>
    </section>
  )
}
