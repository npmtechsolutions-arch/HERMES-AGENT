import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { api, IS_DESKTOP, openEvents } from '../api'
import { useAuth } from '../auth'
import { getMode, setMode, useMode } from '../mode'
import Icon from './Icon'
import { initials, ThemeToggle } from './ui'
import VoiceOrb from './VoiceOrb'
import FirstRunWizard from './FirstRunWizard'
import Tour from './Tour'

// Each item: [path, icon, label, badge?, module?]. Items with a `module` show
// only when that module is in the tenant's effective entitlements (edition ∩ tier
// − admin disables). Items with no module are core (always shown unless the
// edition's skin explicitly hides them). This is the admin-controlled left panel.
const NAV = [
  { group: 'Workspace', items: [
    ['/', 'home', 'Home'],
    ['/dictate', 'mic', 'Voice Type', null, 'M36'],
    ['/guided-setup', 'rocket', 'Guided Setup'],
    ['/verticals', 'sparkles', 'Vertical Agents', null, 'M20'],
    ['/solutions', 'bag', 'Solutions', null, 'M20'],
    ['/universal', 'sparkles', 'Universal Core'],
    ['/company', 'building', 'Your Company'],
    ['/org', 'users', 'Org Chart', null, 'M3'],
    ['/chatbots', 'chat', 'Chatbots', null, 'M14'],
    ['/agent-team', 'users', 'Agent Team', null, 'M3'],
    ['/tasks', 'tasks', 'Tasks', null, 'M12'],
    ['/recipes', 'zap', 'Recipes', null, 'M11'],
    ['/pipelines', 'layers', 'Pipelines', null, 'M11'],
    ['/skills', 'sparkles', 'Skills', null, 'M21'],
    ['/workflows', 'workflow', 'Workflows', null, 'M11'],
    ['/rehearsal', 'play', 'Rehearsal', null, 'M24'],
    ['/approvals', 'shield', 'Approvals', 'approvals', 'M4'],
  ]},
  { group: 'Intelligence', items: [
    ['/inbox', 'inbox', 'Comms Hub', null, 'M13'],
    ['/brain', 'brain', 'Second Brain', null, 'M5'],
    ['/graph', 'graph', 'Knowledge Graph', null, 'M6'],
    ['/analytics', 'chart', 'Analytics', null, 'M19'],
  ]},
  { group: 'Trust & Resilience', items: [
    ['/reliability', 'check', 'Reliability', null, 'M27'],
    ['/backup', 'shield', 'Backup & Restore', null, 'M26'],
    ['/remote', 'chat', 'Remote Access', null, 'M33'],
    ['/gateway', 'cpu', 'Model Gateway', null, 'M32'],
    ['/compliance', 'shield', 'Compliance', null, 'M35'],
    ['/webhooks', 'link', 'Webhooks', null, 'M23'],
    ['/trust', 'sparkles', 'Trust'],
  ]},
  { group: 'Account', items: [
    ['/editions', 'layers', 'Products'],
    ['/pricing', 'card', 'Plans & Pricing'],
    ['/marketplace', 'bag', 'Marketplace', null, 'M20'],
    ['/billing', 'card', 'Subscription'],
    ['/devices', 'monitor', 'Devices'],
    ['/runtime', 'cpu', 'Runtime & Models'],
    ['/system-health', 'check', 'System Health'],
    ['/settings', 'settings', 'Settings'],
  ]},
]

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const mode = useMode()
  const [pending, setPending] = useState(0)
  const [ticker, setTicker] = useState('')
  const [skin, setSkin] = useState(null)
  const [ent, setEnt] = useState(null)   // entitlements: effective modules + tier + skin → drives the whole left panel

  // The "Pipeline / Appointments" group is universal — its labels are SKINNED to the
  // tenant's installed industry template (a lead → patient inquiry → client intake).
  // It only appears once an industry/vertical is actually installed; with nothing
  // deployed there's no pipeline to show.
  const skinnedGroup = skin?.industry ? {
    group: skin.group_label || skin.industry,
    items: [
      ['/leads', 'users', skin.pipeline || 'Inquiry Pipeline'],
      ['/visits', 'tasks', skin.appointments || 'Appointments'],
    ],
  } : null
  // An edition can ship its OWN simplified shell (skin.nav) — e.g. HERMUS
  // Personal's 7 friendly screens. Else use the full business sidebar.
  const customNav = ent?.skin?.nav
  const NAV_FULL = (customNav && customNav.length) ? customNav
    : (skinnedGroup ? [skinnedGroup, ...NAV] : NAV)
  // ENTITLEMENTS drive the left panel: an item shows only if (it has no gating
  // module OR that module is granted) AND it isn't explicitly hidden by the
  // edition skin. Until entitlements load, show everything (no flicker-hide).
  const granted = ent ? new Set(ent.modules || []) : null
  const hidden = new Set(ent?.skin?.hidden_nav || [])
  const visible = (it) => {
    if (granted && it[4] && !granted.has(it[4])) return false   // module not entitled
    if (hidden.has(it[0])) return false                          // admin/edition hid it
    return true
  }
  const NAV_TRIMMED = (granted || hidden.size)
    ? NAV_FULL.map((g) => ({ ...g, items: g.items.filter(visible) })).filter((g) => g.items.length)
    : NAV_FULL
  const brand = ent?.skin?.brand || 'HERMUS'

  useEffect(() => {
    const load = () => api.get('/approvals?state=pending')
      .then((d) => setPending(d.length)).catch(() => {})
    load()
    const loadSkin = () => {
      api.get('/universal/skin').then(setSkin).catch(() => {})
      api.get('/me/entitlements').then(setEnt).catch(() => {})   // effective modules + tier + skin → left panel
    }
    loadSkin()
    // re-skin the nav immediately when an industry/vertical/edition changes
    window.addEventListener('hermus:skin-changed', loadSkin)
    const ws = openEvents((msg) => {
      if (msg.topic === 'approval.requested') {
        load(); setTicker('🛡️ New approval requested')
        if (window.hermus?.notify) window.hermus.notify('Approval needed',
          msg.payload?.summary || 'An agent is requesting your approval.')
      }
      if (msg.topic === 'approval.decided') {
        load()
        setTicker(msg.payload?.batch
          ? `${msg.payload.count} approval(s) ${msg.payload.state}`
          : `Approval ${msg.payload?.state || 'decided'}`)
      }
      if (msg.topic === 'agent.status' && msg.payload.name) {
        setTicker(`${msg.payload.name} is now ${msg.payload.status}`)
        window.dispatchEvent(new CustomEvent('hermus:agent-status', { detail: msg.payload }))
      }
      if (msg.topic === 'task.status_changed')
        setTicker(`Task "${msg.payload.title}" → ${msg.payload.new}`)
      if (msg.topic === 'vertical.changed') {
        setTicker(`${msg.payload.name} ${msg.payload.action === 'deploy' ? 'deployed' : 'removed'}`)
        loadSkin()
      }
      if (msg.topic === 'solution.changed')
        setTicker(`${msg.payload.name} ${msg.payload.action === 'deploy' ? 'deployed' : 'removed'}`)
      if (['engine.changed', 'roster.changed', 'rule.changed'].includes(msg.topic))
        setTicker(`${msg.payload.name} ${msg.payload.action === 'undeploy' ? 'removed'
          : msg.payload.action === 'tune' ? 'updated' : 'deployed'}`)
      if (msg.topic === 'company.changed') setTicker(`${msg.payload.name} updated`)
      if (msg.topic === 'product.changed')
        setTicker(`Product ${msg.payload.action === 'delete' ? 'removed' : 'added'}: ${msg.payload.name}`)
      if (msg.topic === 'org.updated' && msg.payload.agents)
        setTicker(`Org updated — ${msg.payload.agents} agents added`)
      if (msg.topic === 'chatbot.changed')
        setTicker(msg.payload.action === 'channel' ? msg.payload.name
          : `Chatbot ${msg.payload.action === 'delete' ? 'deleted' : msg.payload.action === 'update' ? 'updated' : 'created'}: ${msg.payload.name}`)
      if (msg.topic === 'team.changed')
        setTicker(`${msg.payload.name} ${{ deploy: 'deployed', undeploy: 'removed', claim: 'claimed', resolve: 'resolved' }[msg.payload.action] || 'updated'}`)
      if (msg.topic === 'recipe.changed')
        setTicker(`Recipe ${msg.payload.action === 'disable' ? 'turned off' : 'turned on'}: ${msg.payload.name}`)
      if (msg.topic === 'pipeline.changed')
        setTicker(`Pipeline ${{ create: 'created', update: 'updated', delete: 'deleted' }[msg.payload.action] || 'changed'}: ${msg.payload.name}`)
      if (msg.topic === 'skill.changed')
        setTicker(`Skill ${{ create: 'created', save: 'saved', update: 'updated', archive: 'removed', import: 'imported' }[msg.payload.action] || 'changed'}: ${msg.payload.name}`)
      if (msg.topic === 'workflow.changed')
        setTicker(`Workflow ${{ create: 'created', active: 'activated', paused: 'paused', delete: 'deleted', update: 'updated' }[msg.payload.action] || 'changed'}: ${msg.payload.name}`)
      if (msg.topic === 'rehearsal.changed')
        setTicker(`Rehearsal ${{ start: 'started', finish: 'went live', reset: 'cleared', qualify: 'qualified', play: 'replied' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'comms.changed')
        setTicker(`Inbox ${{ send: 'reply sent', recategorize: 're-triaged', demo: 'loaded' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'memory.changed')
        setTicker(`Memory ${{ ingest: 'saved', forget: 'forgotten', restore: 'restored', demo: 'loaded' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'graph.changed')
        setTicker(`Graph ${{ entity: 'entity added', relation: 'linked', delete: 'removed', unlink: 'unlinked', demo: 'loaded' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'analytics.changed')
        setTicker('Analytics report exported')
      if (msg.topic === 'evals.changed')
        setTicker(`Release gate ${msg.payload.gate}: ${msg.payload.name}`)
      if (msg.topic === 'backup.changed')
        setTicker(`Backup ${{ run: 'completed', restore: 'restored', phrase: 'phrase set', destination: 'destination added', destination_remove: 'destination removed' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'remote.changed')
        setTicker(`Remote ${{ pair_start: 'pairing', paired: 'paired', revoked: 'revoked', update: 'scopes updated' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'gateway.changed')
        setTicker(`Gateway ${{ tier: 'tier', tier_all: 'tiers', budget: 'cap set', call: 'managed call' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'webhook.changed')
        setTicker(`Webhook ${{ create: 'created', update: 'updated', test: 'fired', fire: 'broadcast', delete: 'removed' }[msg.payload.action] || 'changed'}: ${msg.payload.name}`)
      if (msg.topic === 'compliance.changed')
        setTicker(`Compliance ${{ anchor: 'anchored', evaluate: 'PDP', lease: 'sandbox recycled', ceiling: 'ceiling set', ceiling_remove: 'ceiling removed' }[msg.payload.action] || 'updated'}: ${msg.payload.name}`)
      if (msg.topic === 'marketplace.changed') {
        setTicker(`${msg.payload.action === 'uninstall' ? 'Uninstalled' : 'Installed'}: ${msg.payload.name}`)
        if (window.dispatchEvent) window.dispatchEvent(new Event('hermus:skin-changed'))
      }
      if (msg.topic === 'settings.changed')
        setTicker(`Hermes settings ${msg.payload.action === 'reset' ? 'reset' : 'saved'}: ${msg.payload.name}`)
      if (msg.topic === 'setup.changed') {
        const m = { requirement: 'industry set', company: 'company ready', staff: 'team hired', automations: 'automations on', workflow: 'workflow built', skip: 'step skipped' }
        setTicker(`Guided setup — ${m[msg.payload.action] || 'progress'}`)
        if (['requirement', 'company', 'staff'].includes(msg.payload.action)) loadSkin()
      }
    })
    return () => { window.removeEventListener('hermus:skin-changed', loadSkin); try { ws && ws.close() } catch {} }
  }, [])

  return (
    <div className="shell">
      <aside className="sidebar" data-tour="nav">
        <div className="brand">
          <div className="logo" />
          <h1>{brand}</h1>
        </div>
        {NAV_TRIMMED.map((g) => (
          <div key={g.group}>
            <div className="nav-group-label">{g.group}</div>
            {g.items.map(([to, ico, label, badge]) => (
              <NavLink key={to} to={to} end={to === '/'} data-tour={to === '/guided-setup' ? 'guided' : undefined}
                className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}>
                <Icon name={ico} size={18} />{label}
                {badge === 'approvals' && pending > 0 && <span className="badge">{pending}</span>}
              </NavLink>
            ))}
          </div>
        ))}
        <div style={{ flex: 1 }} />
        <div className="nav-item" onClick={() => { logout(); nav('/login') }}>
          <Icon name="logout" size={18} />Sign out
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="searchbar" data-tour="search">
            <Icon name="search" size={16} />
            <span>Search or talk — try “show urgent messages”</span>
            <kbd>⌘K</kbd>
          </div>
          <div className="spacer" />
          <div className="tabs" data-tour="mode" style={{ margin: 0, width: 172, padding: 3 }} title="Simple shows plain language; Advanced reveals logs, rule IDs, JSON">
            {['simple', 'advanced'].map((m) => (
              <button key={m} className={mode === m ? 'active' : ''} style={{ padding: '5px', fontSize: 12 }}
                onClick={() => setMode(m)}>{m === 'simple' ? 'Simple' : 'Advanced'}</button>
            ))}
          </div>
          {IS_DESKTOP && <div className="pill st-completed" title="Running locally on your machine; data syncs to your web dashboard">
            <span className="dot" /> Local · Synced</div>}
          {ticker && <div className="pill" style={{ maxWidth: 280 }}><Icon name="sparkles" size={13} />{ticker}</div>}
          <button className="icon-btn" title="Take the product tour" onClick={() => window.__startTour && window.__startTour()}>
            <Icon name="sparkles" size={18} /></button>
          <button className="icon-btn"><Icon name="bell" size={18} /></button>
          <ThemeToggle />
          <div className="account">
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontWeight: 600 }}>{user?.full_name}</div>
              <div className="muted" style={{ fontSize: 11 }}>{user?.tenant?.company_name}</div>
            </div>
            <div className="avatar">{initials(user?.full_name)}</div>
          </div>
        </header>
        <div className="content">{children}</div>
      </div>
      <VoiceOrb />
      <FirstRunWizard />
      <Tour />
    </div>
  )
}
