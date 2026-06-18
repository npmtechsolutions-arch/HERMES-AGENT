import { useEffect, useState } from 'react'
import { api } from '../api'
import { Loading, PageHead } from '../components/ui'

// The pricing rate card — the Master Formula's knobs (declining rates, Suite
// multiplier, BYOK %, regions, annual, add-ons). No code owns a price.
export default function AdminPricing() {
  const [rates, setRates] = useState(null)
  const [text, setText] = useState('')
  const [defaults, setDefaults] = useState(null)
  const [msg, setMsg] = useState(null)

  const flash = (kind, t) => { setMsg({ kind, t }); setTimeout(() => setMsg(null), 8000) }
  const load = () => api.get('/admin/pricing').then((d) => {
    setRates(d.rates); setDefaults(d.defaults); setText(JSON.stringify(d.rates, null, 2))
  }).catch(() => flash('err', 'Could not load pricing.'))
  useEffect(() => { load() }, [])

  const save = async () => {
    let parsed
    try { parsed = JSON.parse(text) } catch { flash('err', 'Invalid JSON — fix and retry.'); return }
    try { const r = await api.patch('/admin/pricing', { rates: parsed }); flash('ok', r.message); load() }
    catch (e) { flash('err', e?.detail?.message || e?.message || 'Could not save.') }
  }
  const reset = () => defaults && setText(JSON.stringify(defaults, null, 2))

  if (!rates) return <Loading />
  return (
    <>
      <PageHead title="Pricing"
        sub="The Master Formula rate card — combos are computed from these (Doc 20). Changes apply to every tenant's live quote.">
        <button className="btn ghost" onClick={reset}>Reset to defaults</button>
      </PageHead>
      {msg && <div className="card mb" style={{ borderColor: msg.kind === 'ok' ? 'var(--green)' : 'var(--red)' }}>
        {msg.kind === 'ok' ? '✓ ' : '⚠ '}{msg.t}</div>}
      <div className="card">
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
          declining = [1st, 2nd, 3rd, 4th+] factors · suite_multiplier = Suite ÷ single · byok_discount_pct ·
          annual_months_free · regions{`{mult,cur}`} · addons[].
        </div>
        <textarea rows={22} value={text} onChange={(e) => setText(e.target.value)}
          style={{ width: '100%', fontFamily: 'monospace', fontSize: 12, lineHeight: 1.5 }} />
        <button className="btn mt" onClick={save}>Save rate card</button>
      </div>
    </>
  )
}
