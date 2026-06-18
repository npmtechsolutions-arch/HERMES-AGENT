import { NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import Icon from '../components/Icon'
import { initials, ThemeToggle } from '../components/ui'

const NAV = [
  ['/admin', 'dashboard', 'Overview'],
  ['/admin/tenants', 'building', 'Tenants'],
  ['/admin/plans', 'card', 'Plans & Flags'],
  ['/admin/editions', 'layers', 'Editions'],
  ['/admin/gating', 'shield', 'Plan Gating'],
  ['/admin/pricing', 'card', 'Pricing'],
  ['/admin/hermes', 'sparkles', 'Hermes Defaults'],
  ['/admin/catalog', 'bag', 'Catalog Control'],
  ['/admin/config', 'layers', 'Common Config'],
  ['/admin/releases', 'rocket', 'Releases'],
  ['/admin/marketplace', 'bag', 'Marketplace'],
  ['/admin/audit', 'scroll', 'Audit Log'],
]

export default function AdminLayout({ children }) {
  const { admin, logout } = useAuth()
  const nav = useNavigate()
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="logo" />
          <div><h1 style={{ fontSize: 16 }}>HERMUS</h1>
            <div className="muted" style={{ fontSize: 10, letterSpacing: 1 }}>ADMIN CONSOLE</div></div>
        </div>
        <div className="nav-group-label">Platform</div>
        {NAV.map(([to, ico, label]) => (
          <NavLink key={to} to={to} end={to === '/admin'}
            className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
            <Icon name={ico} size={18} />{label}
          </NavLink>
        ))}
        <div style={{ flex: 1 }} />
        <div className="nav-item" onClick={() => { logout(); nav('/login') }}>
          <Icon name="logout" size={18} />Sign out
        </div>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="searchbar"><Icon name="shield" size={16} />
            <span>Product Admin — four-eyes enforced on destructive actions (PA-01)</span></div>
          <div className="spacer" />
          <ThemeToggle />
          <div className="account">
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 600 }}>{admin?.full_name || 'Product Admin'}</div>
              <div className="muted" style={{ fontSize: 11 }}>{(admin?.roles || []).join(', ')}</div>
            </div>
            <div className="avatar">{initials(admin?.full_name || 'PA')}</div>
          </div>
        </header>
        <div className="content">{children}</div>
      </div>
    </div>
  )
}
