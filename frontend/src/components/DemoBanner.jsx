import { useEffect, useState } from 'react'
import { isOffline } from '../api'

// Slim banner shown only when the app is running in offline demo mode
// (bundled backend unreachable). Tells the tester data is canned + not saved.
export default function DemoBanner() {
  const [on, setOn] = useState(isOffline())
  useEffect(() => {
    const f = () => setOn(true)
    window.addEventListener('hermus-offline', f)
    return () => window.removeEventListener('hermus-offline', f)
  }, [])
  if (!on) return null
  return (
    <div style={{
      position: 'fixed', bottom: 14, left: '50%', transform: 'translateX(-50%)',
      zIndex: 9998, background: '#1f2430', color: '#fff', border: '1px solid rgba(255,255,255,.14)',
      borderRadius: 999, padding: '7px 16px', fontSize: 12.5, fontWeight: 500,
      boxShadow: '0 8px 28px rgba(0,0,0,.35)', display: 'flex', alignItems: 'center', gap: 8,
      pointerEvents: 'none', maxWidth: '92vw',
    }}>
      <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#f5a623', flex: '0 0 auto' }} />
      Demo mode — backend offline. Showing sample data; changes aren’t saved.
    </div>
  )
}
