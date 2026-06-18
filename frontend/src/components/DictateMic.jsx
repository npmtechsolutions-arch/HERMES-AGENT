import { useRef, useState } from 'react'
import Icon from './Icon'

// Reusable on-device dictation mic. Streams the live session transcript to
// onText(text); call onStart() to snapshot a prefix. Uses the browser's local
// SpeechRecognition — the voice never leaves the machine.
export default function DictateMic({ onText, onStart, lang = 'en-IN', big }) {
  const [on, setOn] = useState(false)
  const ref = useRef(null)
  const supported = typeof window !== 'undefined' &&
    (window.SpeechRecognition || window.webkitSpeechRecognition)

  const start = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const r = new SR()
    r.lang = lang; r.interimResults = true; r.continuous = true
    let finalT = ''
    r.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i]
        if (res.isFinal) finalT += res[0].transcript + ' '
        else interim += res[0].transcript
      }
      onText && onText((finalT + interim).replace(/\s{2,}/g, ' '))
    }
    r.onerror = () => setOn(false)
    r.onend = () => setOn(false)
    ref.current = r
    onStart && onStart()
    try { r.start(); setOn(true) } catch { setOn(false) }
  }
  const stop = () => { try { ref.current && ref.current.stop() } catch {} ; setOn(false) }

  if (!supported) {
    return <button className="btn ghost" disabled title="Voice input needs Chrome or Edge">
      <Icon name="mic" size={big ? 22 : 14} /> Not supported</button>
  }
  if (big) {
    return (
      <button onClick={on ? stop : start} title={on ? 'Stop dictating' : 'Start dictating'}
        style={{
          width: 92, height: 92, borderRadius: '50%', border: 'none', cursor: 'pointer', color: '#fff',
          display: 'grid', placeItems: 'center',
          background: on ? 'var(--red, #ef4444)' : 'var(--grad)',
          boxShadow: on ? '0 0 0 8px rgba(239,68,68,.18)' : '0 8px 24px rgba(99,102,241,.35)',
          transition: 'box-shadow .2s',
        }}>
        <Icon name="mic" size={34} />
      </button>
    )
  }
  return <button onClick={on ? stop : start} className={'btn sm ' + (on ? '' : 'ghost')}
    title={on ? 'Stop' : 'Dictate'}><Icon name="mic" size={14} /></button>
}
