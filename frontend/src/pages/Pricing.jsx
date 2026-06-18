import { useEffect, useState } from 'react'
import { api } from '../api'
import Icon from '../components/Icon'
import { Loading, PageHead } from '../components/ui'

const TIERS = ['Free', 'Personal', 'Pro']

// Build-Your-Own-Suite calculator — the Master Formula (Doc 20) computed live.
export default function Pricing() {
  const [editions, setEditions] = useState(null)
  const [cfg, setCfg] = useState(null)
  const [sel, setSel] = useState([])
  const [tier, setTier] = useState('Pro')
  const [addOns, setAddOns] = useState([])
  const [byok, setByok] = useState(false)
  const [region, setRegion] = useState('IN')
  const [annual, setAnnual] = useState(false)
  const [quote, setQuote] = useState(null)

  useEffect(() => {
    api.get('/editions').then((d) => {
      setEditions(d.items)
      const def = d.items.find((e) => e.is_default) || d.items[0]
      if (def) setSel([def.slug])
    }).catch(() => {})
    api.get('/pricing/config').then(setCfg).catch(() => {})
  }, [])

  useEffect(() => {
    if (!sel.length) { setQuote(null); return }
    api.post('/pricing/quote', { editions: sel, tier, add_ons: addOns, byok, region, annual })
      .then(setQuote).catch(() => {})
  }, [sel, tier, addOns, byok, region, annual]) // eslint-disable-line

  if (!editions) return <Loading />
  const toggle = (arr, set, id) => set(arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id])

  return (
    <>
      <PageHead title="Plans & Pricing" sub="Pick your products and plan — combos are priced by one rule (discount the second product, never the platform)." />
      <div className="grid" style={{ gridTemplateColumns: '1.4fr 1fr', gap: 16, alignItems: 'start' }}>
        {/* Builder */}
        <div className="card">
          <h3 style={{ marginTop: 0 }}>1 · Choose products</h3>
          {editions.map((e) => (
            <label key={e.slug} className="between" style={{ padding: '8px 0', borderBottom: '1px solid var(--border)', cursor: 'pointer' }}>
              <span className="flex" style={{ gap: 10, alignItems: 'center' }}>
                <input type="checkbox" checked={sel.includes(e.slug)} onChange={() => toggle(sel, setSel, e.slug)} style={{ width: 16 }} />
                <span><div style={{ fontSize: 13, fontWeight: 600 }}>{e.name}</div>
                  <div className="muted" style={{ fontSize: 11 }}>{e.layer.replace('_', ' ')}</div></span>
              </span>
            </label>
          ))}

          <h3>2 · Plan</h3>
          <div className="flex wrap" style={{ gap: 6 }}>
            {TIERS.map((t) => <button key={t} className={'btn sm ' + (tier === t ? '' : 'ghost')} onClick={() => setTier(t)}>{t}</button>)}
          </div>

          {cfg?.addons?.length > 0 && <>
            <h3>3 · Shared add-ons <span className="muted" style={{ fontSize: 12, fontWeight: 400 }}>(charged once across all products)</span></h3>
            <div className="flex wrap" style={{ gap: 6 }}>
              {cfg.addons.map((a) => (
                <button key={a.id} className={'btn sm ' + (addOns.includes(a.id) ? '' : 'ghost')}
                  onClick={() => toggle(addOns, setAddOns, a.id)}>{a.name}</button>
              ))}
            </div>
          </>}

          <h3>4 · Options</h3>
          <div className="flex wrap" style={{ gap: 14, alignItems: 'center' }}>
            <label className="flex" style={{ gap: 8, fontSize: 13, cursor: 'pointer', width: 'auto' }}>
              <input type="checkbox" checked={byok} onChange={(e) => setByok(e.target.checked)} style={{ width: 16 }} />
              BYOK {cfg ? `(−${cfg.byok_discount_pct}%)` : ''}</label>
            <label className="flex" style={{ gap: 8, fontSize: 13, cursor: 'pointer', width: 'auto' }}>
              <input type="checkbox" checked={annual} onChange={(e) => setAnnual(e.target.checked)} style={{ width: 16 }} /> Annual</label>
            <select value={region} onChange={(e) => setRegion(e.target.value)} style={{ width: 'auto' }}>
              {(cfg?.regions || ['IN']).map((r) => <option key={r} value={r}>{r}</option>)}</select>
          </div>
        </div>

        {/* Quote */}
        <div className="card" style={{ position: 'sticky', top: 12 }}>
          <h3 style={{ marginTop: 0 }}><Icon name="card" size={17} /> Your price</h3>
          {!quote && <p className="muted">Select at least one product.</p>}
          {quote && <>
            {quote.editions.map((l) => (
              <div key={l.slug} className="between" style={{ fontSize: 13, padding: '5px 0' }}>
                <span>{l.name}{l.factor < 1 && <span className="tag" style={{ marginLeft: 6, fontSize: 10 }}>{Math.round(l.factor * 100)}%</span>}</span>
                <span>{quote.currency}{l.charged.toLocaleString()}</span>
              </div>
            ))}
            {quote.add_ons.map((a) => (
              <div key={a.id} className="between muted" style={{ fontSize: 12, padding: '3px 0' }}>
                <span>+ {a.name}</span><span>{quote.currency}{a.price.toLocaleString()}</span></div>
            ))}
            {quote.byok_discount > 0 && <div className="between" style={{ fontSize: 12, padding: '3px 0', color: 'var(--green)' }}>
              <span>BYOK discount</span><span>−{quote.currency}{quote.byok_discount.toLocaleString()}</span></div>}
            <div className="between" style={{ borderTop: '1px solid var(--border)', marginTop: 8, paddingTop: 10 }}>
              <strong>{annual ? 'Per year' : 'Per month'}</strong>
              <strong style={{ fontSize: 22 }}>{quote.currency}{(annual ? quote.annual : quote.monthly).toLocaleString()}</strong>
            </div>
            {!annual && <div className="between muted" style={{ fontSize: 12 }}><span>or annual</span><span>{quote.currency}{quote.annual.toLocaleString()}/yr</span></div>}
            {quote.suite_applied && <div className="pill st-completed" style={{ marginTop: 8 }}><span className="dot" /> Suite price</div>}
            {quote.notes?.length > 0 && <ul className="muted" style={{ fontSize: 11.5, marginTop: 10, paddingLeft: 16 }}>
              {quote.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
          </>}
        </div>
      </div>
    </>
  )
}
