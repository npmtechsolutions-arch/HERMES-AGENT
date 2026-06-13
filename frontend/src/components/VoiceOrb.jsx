import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import Icon from './Icon'

// 7 voice states from Design Flow §2.1
const STATE_LABEL = {
  sleeping: 'Sleeping', listening: 'Listening', thinking: 'Thinking',
  speaking: 'Speaking', acting: 'Acting', confirming: 'Confirming', error: 'Error',
}

export default function VoiceOrb() {
  const nav = useNavigate()
  const [state, setState] = useState('sleeping')
  const [open, setOpen] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [response, setResponse] = useState('')
  const [textInput, setTextInput] = useState('')
  const recogRef = useRef(null)
  const supported = typeof window !== 'undefined' &&
    (window.SpeechRecognition || window.webkitSpeechRecognition)

  useEffect(() => {
    if (!supported) return
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    const r = new SR()
    r.lang = 'en-IN'
    r.interimResults = true
    r.continuous = false
    r.onresult = (e) => {
      let txt = ''
      for (let i = 0; i < e.results.length; i++) txt += e.results[i][0].transcript
      setTranscript(txt)
      if (e.results[e.results.length - 1].isFinal) handleUtterance(txt)
    }
    r.onerror = () => setState('error')
    r.onend = () => setState((s) => (s === 'listening' ? 'sleeping' : s))
    recogRef.current = r
    return () => { try { r.stop() } catch {} }
  }, [supported])

  function speak(text) {
    setResponse(text)
    if (typeof window !== 'undefined' && window.speechSynthesis) {
      setState('speaking')
      const u = new SpeechSynthesisUtterance(text)
      u.lang = 'en-IN'
      u.onend = () => setState('sleeping')
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(u)
    } else {
      setState('sleeping')
    }
  }

  // Questions about your business are answered inline — the agent IS the dashboard.
  const QUESTION = /^(how many|how much|how's|how is|what('| i)?s|what is|show( me)?|do i|are there|any |when('| i)?s|when is|whats|give me my (numbers|stats))/i
  const METRIC = /\b(lead|inquir|enquir|appointment|visit|booking|no.?show|message|sms|whatsapp|task|hour|roi|saved|approval|pipeline|conversion|won|lost|summary|briefing|stats?|numbers?)\b/i

  async function handleUtterance(text) {
    if (!text.trim()) return
    setState('thinking')
    setOpen(true)
    // A page may register a voice handler (e.g. Vertical Agents, Solutions). Let it
    // handle clear deploy/undeploy phrasing for what's on screen.
    const pageVoice = window.__verticalsVoice || window.__solutionsVoice || window.__universalVoice
      || window.__companyVoice || window.__orgVoice || window.__chatbotsVoice || window.__agentteamVoice
      || window.__tasksVoice || window.__recipesVoice || window.__pipelinesVoice || window.__skillsVoice || window.__workflowsVoice || window.__rehearsalVoice || window.__approvalsVoice || window.__inboxVoice || window.__brainVoice || window.__graphVoice || window.__analyticsVoice || window.__reliabilityVoice || window.__backupVoice || window.__remoteVoice || window.__gatewayVoice || window.__webhooksVoice || window.__complianceVoice || window.__marketplaceVoice || window.__settingsVoice || window.__setupVoice
    if (pageVoice && /\b(deploy|undeploy|install|uninstall|vertical|solution|engine|roster|re-?skin|rule|industry|company|product|org|suggest|focus|adopt|hire|fire|recruit|pause|resume|employee|department|archive|chatbot|channel|telegram|whatsapp|slack|discord|teams|team|persona|escalation|handoff|inbox|routing|adversarial|ask the team|task|execute|cancel|recipe|automation|turn on|turn off|pipeline|run|build|duplicate|skill|import|sandbox|workflow|activate|deactivate|dry.?run|rehears|qualify|go live|simulat|approve|reject|approval|decline|draft|reply|triage|urgent|spam|conversation|remember|memory|forget|recall|ingest|restore|entity|connect|link|graph|relationship|export|refresh|analytics|metric|release gate|reliability|eval|golden|back ?up|recovery phrase|destination|pair|revoke|signal|gateway|tier|managed|budget|local model|webhook|integration|zapier|verify|anchor|ceiling|policy|policies|isolation|compliance|audit chain|marketplace|pack|temperature|tone|autonomy|verbosity|wake word|telemetry|setting|grounding|creativity|set up|setup|staff|guide me|next step|what.?s next)\b/i.test(text)) {
      pageVoice(text)
      speak('On it.')
      return
    }
    // Data questions → chat-based dashboard. Otherwise → intent routing (navigate/act).
    if (QUESTION.test(text.trim()) || METRIC.test(text)) {
      try {
        const a = await api.post('/ask', { question: text })
        if (a.understood) { speak(a.answer); return }
      } catch {}
    }
    try {
      const r = await api.post('/voice/intents/parse', { text })
      routeIntent(r)
    } catch {
      speak("Sorry, I couldn't process that.")
      setState('error')
    }
  }

  function routeIntent(r) {
    const { intent, slots, confidence } = r
    if (confidence < 0.6) {
      setState('confirming')
      speak("I didn't quite catch that. " + (r.suggestion || 'Could you rephrase?'))
      return
    }
    switch (intent) {
      case 'navigate':
        if (slots.route) { nav(slots.route); speak(`Opening ${slots.target}.`) }
        else speak(`I couldn't find a screen for "${slots.target}".`)
        break
      case 'hire_agent': nav('/org?hire=1'); speak('Opening the hire wizard.'); break
      case 'create_workflow': nav('/workflows?compile=' + encodeURIComponent(r.utterance));
        speak('Let me build that workflow.'); break
      case 'create_task': nav('/tasks?plan=' + encodeURIComponent(r.utterance));
        speak('Let me plan that task with the CEO Agent.'); break
      case 'briefing': nav('/'); speak('Here is your briefing on the dashboard.'); break
      case 'search_memory': nav('/brain?q=' + encodeURIComponent(r.utterance));
        speak('Searching your Second Brain.'); break
      case 'approvals': nav('/approvals'); speak('Showing pending approvals.'); break
      default: speak(r.suggestion || "I'm not sure how to help with that yet.")
    }
  }

  function startListening() {
    setOpen(true)
    setResponse('')
    setTranscript('')
    if (supported && recogRef.current) {
      setState('listening')
      try { recogRef.current.start() } catch {}
    } else {
      setState('listening')
    }
  }

  // Let the Electron global hotkey (Cmd/Ctrl+Shift+Space) and tray trigger voice.
  useEffect(() => {
    window.__hermusVoice = startListening
    return () => { if (window.__hermusVoice === startListening) delete window.__hermusVoice }
  }, [supported])

  function submitText(e) {
    e.preventDefault()
    if (!textInput.trim()) return
    setTranscript(textInput)
    handleUtterance(textInput)
    setTextInput('')
  }

  return (
    <div className="orb-wrap">
      {open && (
        <div className="orb-panel">
          <div className="between">
            <div className="state">◉ {STATE_LABEL[state]} · "Hey Office"</div>
            <button className="icon-btn" onClick={() => setOpen(false)} style={{ width: 30, height: 30 }}>
              <Icon name="x" size={15} /></button>
          </div>
          <div className="tx">{transcript || <span className="muted">Ask about your business, or give a command…</span>}</div>
          {response && <div className="resp">🔊 {response}</div>}
          {!response && !transcript && (
            <div className="flex wrap mt" style={{ gap: 5 }}>
              {['How many leads today?', "This week's appointments", "What's my no-show rate?", 'Hours saved this week']
                .map((q) => (
                  <button key={q} type="button" className="tag" style={{ cursor: 'pointer' }}
                    onClick={() => { setTranscript(q); handleUtterance(q) }}>{q}</button>))}
            </div>
          )}
          <form onSubmit={submitText} className="flex mt">
            <input value={textInput} onChange={(e) => setTextInput(e.target.value)}
              placeholder='e.g. "show my tasks" or "hire an employee"' />
            <button className="btn sm" type="submit">Send</button>
          </form>
          {!supported && <div className="muted mt" style={{ fontSize: 11 }}>
            Mic not available in this browser — using keyboard fallback (no voice-only dead ends).
          </div>}
        </div>
      )}
      {open && transcript && <div className="orb-chip">{transcript}</div>}
      <button className={`orb ${state}`} data-tour="orb" onClick={startListening} title="Push to talk (Ctrl+Space)">
        <Icon name="mic" size={24} stroke={2.2} />
      </button>
    </div>
  )
}
