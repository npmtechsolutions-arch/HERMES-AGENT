// Theme switching (light default) — persisted in localStorage.
function apply(theme) {
  const root = document.documentElement
  root.classList.toggle('dark', theme === 'dark')
  root.classList.toggle('light', theme !== 'dark')
}

export function getTheme() {
  return localStorage.getItem('hermus_theme') || 'light'
}

export function initTheme() {
  apply(getTheme())
}

export function toggleTheme() {
  const next = getTheme() === 'dark' ? 'light' : 'dark'
  localStorage.setItem('hermus_theme', next)
  apply(next)
  return next
}
