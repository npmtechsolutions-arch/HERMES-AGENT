import { useEffect, useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { api, IS_DESKTOP, openEvents } from '../api'
import { useAuth } from '../auth'
import { getMode, setMode, useMode } from '../mode'
import Icon from './Icon'
import { initials, ThemeToggle } from './ui'
import VoiceOrb from './VoiceOrb'
import Tour from './Tour'

const NAV = [
  { group: 'Workspace', items: [
    ['/', 'home', 'Home'],
    ['/dictate', 'mic', 'Voice Type'],
    ['/guided-setup', 'rocket', 'Guided Setup'],
    ['/verticals', 'sparkles', 'Vertical Agents'],
    ['/solutions', 'bag', 'Solutions'],
    ['/universal', 'sparkles', 'Universal Core'],
    ['/company', 'building', 'Your Company'],
    ['/org', 'users', 'Org Chart'],
    ['/chatbots', 'chat', 'Chatbots'],
    ['/agent-team', 'users', 'Agent Team'],
    ['/tasks', 'tasks', 'Tasks'],
    ['/recipes', 'zap', 'Recipes'],
    ['/pipelines', 'layers', 'Pipelines'],
    ['/skills', 'sparkles', 'Skills'],
    ['/workflows', 'workflow', 'Workflows'],
    ['/rehearsal', 'play', 'Rehearsal'],
    ['/approvals', 'shield', 'Approvals', 'approvals'],
  ]},
  { group: 'Intelligence', items: [
    ['/inbox', 'inbox', 'Comms Hub'],
    ['/brain', 'brain', 'Second Brain'],
    ['/graph', 'graph', 'Knowledge Graph'],
    ['/analytics', 'chart', 'Analytics'],
  ]},
  { group: 'Trust & Resilience', items: [
    ['/reliability', 'check', 'Reliability'],
    ['/backup', 'shield', 'Backup & Restore'],
    ['/remote', 'chat', 'Remote Access'],
    ['/gateway', 'cpu', 'Model Gateway'],
    ['/compliance', 'shield', 'Compliance'],
    ['/webhooks', 'link', 'Webhooks'],
    ['/trust', 'sparkles', 'Trust'],
  ]},
  { group: 'Account', items: [
    ['/editions', 'layers', 'Products'],
    ['/pricing', 'card', 'Plans & Pricing'],
    ['/marketplace', 'bag', 'Marketplace'],
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
  const [edition, setEdition] = useState(null)   // active Edition → brand + nav trim (Phase 3)

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
  const NAV_FULL = skinnedGroup ? [skinnedGroup, ...NAV] : NAV
  // The active Edition trims the sidebar to its enabled scope (Phase 3 skin):
  // explicit hidden_nav + module-gated items (a feature hides if its module is off).
  const MODULE_NAV = { '/dictate': 'M36' }  // path → required module id
  const hidden = new Set(edition?.active ? (edition?.skin?.hidden_nav || []) : [])
  if (edition?.active) {
    const mods = edition.enabled_modules || []
    for (const [path, mod] of Object.entries(MODULE_NAV)) if (!mods.includes(mod)) hidden.add(path)
  }
  const NAV_TRIMMED = hidden.size
    ? NAV_FULL.map((g) => ({ ...g, items: g.items.filter((it) => !hidden.has(it[0])) })).filter((g) => g.items.length)
    : NAV_FULL
  const brand = (edition?.active && edition?.skin?.brand) || 'HERMUS'

  useEffect(() => {
    const load = () => api.get('/approvals?state=pending')
      .then((d) => setPending(d.length)).catch(() => {})
    load()
    const loadSkin = () => {
      api.get('/universal/skin').then(setSkin).catch(() => {})
      api.get('/editions/active').then(setEdition).catch(() => {})   // active Edition → brand + nav trim
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
      if (msg.topic === 'agent.status' && msg.payload.name)
        setTicker(`${msg.payload.name} is now ${msg.payload.status}`)
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
      <Tour />
    </div>
  )
}
