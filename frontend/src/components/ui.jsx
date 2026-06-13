// Small shared presentational helpers.
import { useState } from 'react'
import { getTheme, toggleTheme } from '../theme'
import Icon from './Icon'

export function ThemeToggle() {
  const [theme, setTheme] = useState(getTheme())
  return (
    <button className="icon-btn" title="Toggle light / dark"
      onClick={() => setTheme(toggleTheme())}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} size={18} />
    </button>
  )
}

export function Pill({ status }) {
  const s = (status || '').toLowerCase()
  return <span className={`pill st-${s}`}><span className="dot" />{status}</span>
}

export function PageHead({ title, sub, children }) {
  return (
    <div className="page-head">
      <div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>
      <div className="row-actions">{children}</div>
    </div>
  )
}

export function Stat({ label, value, delta, icon, tint }) {
  return (
    <div className="stat">
      {icon && <div className={'stat-ico' + (tint ? ' ' + tint : '')}><Icon name={icon} size={20} /></div>}
      <div>
        <div className="label">{label}</div>
        <div className="value">{value}</div>
        {delta && <div className="delta">{delta}</div>}
      </div>
    </div>
  )
}

export function Loading() {
  return <div className="loading">Loading…</div>
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

export function Modal({ title, onClose, children }) {
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="between mb">
          <h3 style={{ margin: 0 }}>{title}</h3>
          <button className="icon-btn" onClick={onClose} style={{ width: 32, height: 32 }}>
            <Icon name="x" size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  )
}

export function initials(name = '') {
  return name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
}
