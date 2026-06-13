import Icon from '../components/Icon'
import { PageHead } from '../components/ui'

const EGRESS = ['api.hermus.app (identity, billing, entitlements)',
  'gateway.razorpay.com / api.stripe.com (payments)', 'cdn.hermus.app (installers, signed config)',
  'localhost:11434 (Ollama — local only)']

export default function Trust() {
  return (
    <>
      <PageHead title="Trust & Governance"
        sub="Why a governed AI company beats a free general agent — and how our privacy is verifiable." />

      <div className="card mb" style={{ background: 'var(--grad)', color: '#fff', border: 'none' }}>
        <h3 style={{ color: '#fff', margin: 0 }}>Autonomy you can govern</h3>
        <p style={{ color: 'rgba(255,255,255,.9)', fontSize: 14 }}>
          Businesses don't fear AI capability — they fear <em>ungoverned</em> capability. HERMUS gives you
          approval chains, audit trails, spend limits, voice-print authorization and compliance calendars
          around every autonomous action. A free general agent structurally can't.</p>
      </div>

      <div className="grid cols-3 mb">
        {[['shield', 'A company, not a chatbot', 'Org chart, departments, KPIs, a CEO Agent and industry templates — outcomes per vertical: “your GST files itself.”'],
          ['check', 'Self-improving, but supervised', 'Agents auto-capture skills from completed work — every one is versioned, reviewable and approval-gated before it touches external systems.'],
          ['link', 'Verifiably private', 'Business data never leaves your machine (DB-01). The desktop egress allow-list is published and auditable — privacy you can verify, not just a slogan.']]
          .map(([ic, t, d]) => (
          <div className="card" key={t}>
            <div className="stat-ico mb"><Icon name={ic} size={20} /></div>
            <h3 style={{ marginTop: 0 }}>{t}</h3>
            <div className="muted" style={{ fontSize: 13 }}>{d}</div>
          </div>
        ))}
      </div>

      <div className="grid cols-2">
        <div className="card">
          <h3><Icon name="link" size={17} /> Published egress allow-list</h3>
          <p className="muted" style={{ fontSize: 13 }}>The desktop core only ever talks to these hosts.
            Everything else is blocked at the network layer (Offline Enterprise Mode blocks all WAN).</p>
          {EGRESS.map((e) => (
            <div key={e} className="flex" style={{ padding: '7px 0', borderBottom: '1px solid var(--border)', fontSize: 13 }}>
              <Icon name="check" size={14} style={{ color: 'var(--green)' }} />{e}</div>
          ))}
          <div className="tag mt" style={{ color: 'var(--green)' }}>✓ No business data, memory, or transcripts ever leave</div>
        </div>

        <div className="card">
          <h3><Icon name="sparkles" size={17} /> Free Solo — forever</h3>
          <p className="muted" style={{ fontSize: 13 }}>No subscription required to start. The open-source local
            connector/MCP layer, Plugin SDK and skill format are public — build on us, verify our claims.</p>
          <ul style={{ fontSize: 14, lineHeight: 1.9, paddingLeft: 16 }}>
            <li>2 agents · 2 workflows · 1 device</li>
            <li>Full voice · full local privacy</li>
            <li>Email channel · community marketplace</li>
          </ul>
          <p className="muted" style={{ fontSize: 12 }}>We don't sell the agent — we sell the <strong>governed
            workforce</strong>: approvals, audit, templates, support and admin-managed compliance updates.</p>
        </div>
      </div>
    </>
  )
}
