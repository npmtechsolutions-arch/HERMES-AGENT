// §9.1 Simple/Advanced mode + §9.6 large-type accessibility — one surface, two doors.
import { useEffect, useState } from 'react'

export function getMode() { return localStorage.getItem('hermus_mode') || 'simple' }
export function setMode(m) { localStorage.setItem('hermus_mode', m); window.dispatchEvent(new Event('hermus-mode')) }
export function getBig() { return localStorage.getItem('hermus_big') === '1' }
export function setBig(v) {
  localStorage.setItem('hermus_big', v ? '1' : '0')
  document.documentElement.style.fontSize = v ? '17.5px' : ''
  window.dispatchEvent(new Event('hermus-mode'))
}

export function initMode() { if (getBig()) document.documentElement.style.fontSize = '17.5px' }

export function useMode() {
  const [m, set] = useState(getMode())
  useEffect(() => {
    const h = () => set(getMode())
    window.addEventListener('hermus-mode', h)
    return () => window.removeEventListener('hermus-mode', h)
  }, [])
  return m
}

export const isAdvanced = () => getMode() === 'advanced'
