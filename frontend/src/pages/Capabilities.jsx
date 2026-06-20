import { PageHead } from '../components/ui'
import WhatICanDo from '../components/WhatICanDo'

// Doc 27 Part 2.1 / Part 9 #1 — the always-available "what can you do" reference:
// every capability grouped, each a tappable example command. The answer to
// "how do I know what to say" — usable commands, not a static feature count.
export default function Capabilities() {
  return (
    <>
      <PageHead title="What I can do" subtitle="Tap any example to run it. Just talk naturally — these are only examples." />
      <WhatICanDo />
    </>
  )
}
