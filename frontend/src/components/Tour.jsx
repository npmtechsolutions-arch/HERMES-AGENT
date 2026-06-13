import { useCallback, useEffect, useLayoutEffect, useState } from 'react'

// A lightweight, dependency-free product tour: dim the app, spotlight a target
// element, show a tooltip with Next/Back/Skip. Anchored via [data-tour="..."].
const STEPS = [
  { title: 'Welcome to HERMUS 👋', body: "Your private AI office — an entire company of AI agents that runs 100% on this machine. Here's a 60-second tour.", center: true },
  { sel: '[data-tour="nav"]', title: 'Your AI workforce', body: 'Each section here is a part of your company — agents, tasks, workflows, memory, approvals. It re-skins to your industry.', placement: 'right' },
  { sel: '[data-tour="guided"]', title: 'Start here', body: "New? Open Guided Setup — we'll pick your industry, hire your AI team, switch on automations and build a workflow, step by step.", placement: 'right' },
  { sel: '[data-tour="search"]', title: 'Search or just talk', body: 'Ask anything in plain language — “how many leads today?”, “what’s pending?” — and your agents answer from your data.', placement: 'bottom' },
  { sel: '[data-tour="mode"]', title: 'Two views, one product', body: 'Simple shows plain language. Advanced reveals logs, rule IDs and JSON — for when you want the detail.', placement: 'bottom' },
  { sel: '[data-tour="orb"]', title: 'Run it all by voice', body: 'Tap the orb — or press Ctrl/Cmd + Shift + Space anywhere — and command your whole office hands-free.', placement: 'left' },
  { title: "You're ready 🚀", body: 'Tap the ? in the top bar anytime to retake this tour. Let’s build your AI company.', center: true },
]

const SEEN_KEY = 'hermus_tour_done'

export default function Tour() {
  const [run, setRun] = useState(false)
  const [i, setI] = useState(0)
  const [rect, setRect] = useState(null)

  const start = useCallback(() => { setI(0); setRun(true) }, [])
  const finish = useCallback(() => { setRun(false); try { localStorage.setItem(SEEN_KEY, '1') } catch {} }, [])

  // Expose a global trigger (top-bar "?" button, Home button, etc.)
  useEffect(() => { window.__startTour = start; return () => { if (window.__startTour === start) delete window.__startTour } }, [start])

  // Auto-run once on first visit.
  useEffect(() => {
    let seen = true
    try { seen = localStorage.getItem(SEEN_KEY) === '1' } catch {}
    if (!seen) { const t = setTimeout(start, 1100); return () => clearTimeout(t) }
  }, [start])

  const step = STEPS[i]

  // Measure the current target (and re-measure on resize/scroll).
  useLayoutEffect(() => {
    if (!run) return
    if (step.center || !step.sel) { setRect(null); return }
    const measure = () => {
      const el = document.querySelector(step.sel)
      if (!el) { setRect(null); return }
      el.scrollIntoView({ block: 'nearest', inline: 'nearest' })
      const r = el.getBoundingClientRect()
      setRect({ top: r.top, left: r.left, width: r.width, height: r.height })
    }
    measure()
    const id = setTimeout(measure, 60)
    window.addEventListener('resize', measure)
    window.addEventListener('scroll', measure, true)
    return () => { clearTimeout(id); window.removeEventListener('resize', measure); window.removeEventListener('scroll', measure, true) }
  }, [run, i, step])

  // Keyboard: Esc skips, →/Enter next, ← back.
  useEffect(() => {
    if (!run) return
    const onKey = (e) => {
      if (e.key === 'Escape') finish()
      else if (e.key === 'ArrowRight' || e.key === 'Enter') next()
      else if (e.key === 'ArrowLeft') setI((x) => Math.max(0, x - 1))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }) // eslint-disable-line

  const next = () => { if (i >= STEPS.length - 1) finish(); else setI(i + 1) }

  if (!run) return null

  const pad = 8
  const hole = rect && { top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2, height: rect.height + pad * 2 }
  const tip = tooltipPos(hole, step.placement)

  return (
    <div style={{ position: 'fixed', inset: 0, zIndex: 4000 }}>
      {/* dim + spotlight via a big box-shadow on the hole; click-through blocked by the layer */}
      <div onClick={finish} style={{ position: 'absolute', inset: 0, cursor: 'default' }} />
      {hole && <div style={{
        position: 'absolute', top: hole.top, left: hole.left, width: hole.width, height: hole.height,
        borderRadius: 12, boxShadow: '0 0 0 9999px rgba(8,10,20,.66)', border: '2px solid var(--primary)',
        transition: 'all .25s ease', pointerEvents: 'none',
      }} />}
      {!hole && <div style={{ position: 'absolute', inset: 0, background: 'rgba(8,10,20,.72)' }} />}

      <div className="card" style={{
        position: 'absolute', width: 340, maxWidth: '90vw', zIndex: 4001,
        boxShadow: '0 18px 50px rgba(0,0,0,.4)', border: '1px solid var(--primary)', ...tip,
      }}>
        <div className="between mb">
          <span className="tag" style={{ color: 'var(--primary)' }}>Step {i + 1} / {STEPS.length}</span>
          <button className="btn ghost sm" onClick={finish}>Skip tour</button>
        </div>
        <h3 style={{ margin: '0 0 6px' }}>{step.title}</h3>
        <p className="muted" style={{ fontSize: 13, margin: 0 }}>{step.body}</p>
        <div className="between mt">
          <div className="flex" style={{ gap: 4 }}>
            {STEPS.map((_, k) => <span key={k} style={{ width: 6, height: 6, borderRadius: 6,
              background: k === i ? 'var(--primary)' : 'var(--border)' }} />)}
          </div>
          <div className="row-actions">
            {i > 0 && <button className="btn ghost sm" onClick={() => setI(i - 1)}>Back</button>}
            <button className="btn sm" onClick={next}>{i >= STEPS.length - 1 ? 'Get started' : 'Next'}</button>
          </div>
        </div>
      </div>
    </div>
  )
}

function tooltipPos(hole, placement) {
  const W = 340, H = 170, m = 14, vw = window.innerWidth, vh = window.innerHeight
  if (!hole) return { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' }
  const clampL = (l) => Math.max(m, Math.min(l, vw - W - m))
  const clampT = (t) => Math.max(m, Math.min(t, vh - H - m))
  if (placement === 'right' && hole.left + hole.width + W + m < vw)
    return { top: clampT(hole.top), left: hole.left + hole.width + m }
  if (placement === 'left' && hole.left - W - m > 0)
    return { top: clampT(hole.top + hole.height - H), left: hole.left - W - m }
  if (placement === 'bottom' && hole.top + hole.height + H + m < vh)
    return { top: hole.top + hole.height + m, left: clampL(hole.left) }
  // default: above, else below
  if (hole.top - H - m > 0) return { top: hole.top - H - m, left: clampL(hole.left) }
  return { top: clampT(hole.top + hole.height + m), left: clampL(hole.left) }
}
