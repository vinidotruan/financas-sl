import type { Aba } from '../rotas'
import { link } from '../rotas'

const ICONES: Record<Aba, preact.JSX.Element> = {
  // casa: a primeira tela
  inicio: <path d="M3.5 11 12 4l8.5 7M6 9v11h4.5v-6h3v6H18V9" />,
  // triângulo de atenção
  sinais: <path d="M12 3.5 2.8 19.5h18.4L12 3.5ZM12 10v4.5M12 17.2v.3" />,
  // caminho com dois pontos: o rastro do dinheiro
  emendas: <><circle cx="5.5" cy="6" r="2.5" /><circle cx="18.5" cy="18" r="2.5" /><path d="M8 6h6.5a3.5 3.5 0 0 1 0 7h-5a3.5 3.5 0 0 0 0 7H16" /></>,
  // prancheta com pedidos
  pedidos: <><rect x="5" y="4" width="14" height="17" rx="2" /><path d="M9 4V3h6v1M8.5 10h7M8.5 14h7M8.5 18h4" /></>,
  // duas fichas
  fichas: <><rect x="3" y="5" width="13" height="15" rx="2" /><path d="M8 3h11a2 2 0 0 1 2 2v13M6.5 10h6M6.5 14h6" /></>,
  // barras
  contas: <path d="M4 20h16M7 16.5V11M12 16.5V6M17 16.5v-8" />,
}

// Início primeiro (D44); Fontes saiu da barra e é um link no rodapé do Início
const ABAS: { aba: Aba; nome: string; href: string }[] = [
  { aba: 'inicio', nome: 'Início', href: link.inicio() },
  { aba: 'emendas', nome: 'Emendas', href: link.emendas() },
  { aba: 'pedidos', nome: 'Pedidos', href: link.pedidos() },
  { aba: 'fichas', nome: 'Fichas', href: link.fichas() },
  { aba: 'contas', nome: 'Contas', href: link.contas() },
  { aba: 'sinais', nome: 'Sinais', href: link.sinais() },
]

export function Abas(props: { atual: Aba }) {
  return (
    <nav class="abas" aria-label="Seções">
      <ul>
        {ABAS.map((a) => (
          <li key={a.aba}>
            <a href={a.href} aria-current={a.aba === props.atual ? 'page' : undefined}>
              <svg viewBox="0 0 24 24" aria-hidden="true">{ICONES[a.aba]}</svg>
              {a.nome}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
