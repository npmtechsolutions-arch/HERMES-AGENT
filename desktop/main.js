/*
 * HERMUS Desktop — Electron main process.
 *
 * Responsibilities (the "local execution plane" shell):
 *   1. Bring up the local stack: isolated PostgreSQL + the FastAPI Core Service.
 *   2. Serve / load the React UI and attach the preload bridge.
 *   3. Native desktop integration: app menu, tray, global push-to-talk hotkey,
 *      and native notifications for approvals.
 *
 * Dev mode (HERMUS_DEV=1): loads the Vite dev server at :5173 and reuses the
 * repo venv. Packaged mode: serves frontend/dist and runs the bundled backend.
 */
const { app, BrowserWindow, Menu, Tray, globalShortcut, ipcMain, Notification, shell, nativeImage } = require('electron')
const { spawn } = require('child_process')
const http = require('http')
const fs = require('fs')
const path = require('path')

const DEV = process.env.HERMUS_DEV === '1'
const API_PORT = 7700
const PG_PORT = 5544
const UI_PORT = 5179
const VITE_URL = 'http://localhost:5173'

// Resolve project paths (repo layout in dev, resources in packaged build).
const ROOT = DEV ? path.resolve(__dirname, '..') : process.resourcesPath
const BACKEND_DIR = DEV ? path.join(ROOT, 'backend') : path.join(ROOT, 'backend')
const DIST_DIR = DEV ? path.join(ROOT, 'frontend', 'dist') : path.join(ROOT, 'frontend')
const PGDATA = path.join(BACKEND_DIR, '.pgdata')
const VENV_PY = path.join(BACKEND_DIR, '.venv', 'bin', 'python')

let win, tray, backendProc, pgStarted = false, staticServer

// Never let a stray error tear the app down with a crash dialog — log instead.
process.on('uncaughtException', (e) => console.error('[uncaught]', e && e.message ? e.message : e))
process.on('unhandledRejection', (e) => console.error('[unhandledRejection]', e && e.message ? e.message : e))

// ── helpers ─────────────────────────────────────────────────────────────────
function pgBin() {
  for (const p of ['/usr/local/opt/postgresql@15/bin', '/opt/homebrew/opt/postgresql@15/bin',
                   '/usr/local/bin', '/opt/homebrew/bin']) {
    if (fs.existsSync(path.join(p, 'pg_ctl'))) return p
  }
  return null
}

// Packaged GUI apps on macOS/Linux inherit a minimal PATH that omits Homebrew
// and /usr/local/bin — so `ollama`, `brew`, etc. fail to spawn. Augment PATH so
// install/uninstall actually work from the packaged app.
const EXTRA_PATHS = ['/usr/local/bin', '/opt/homebrew/bin', '/usr/bin', '/bin', '/usr/sbin', '/sbin']
const SPAWN_ENV = { ...process.env, PATH: [process.env.PATH || '', ...EXTRA_PATHS].filter(Boolean).join(':') }

// Absolute path to the ollama binary (or 'ollama' as a last resort).
function ollamaBin() {
  for (const p of ['/usr/local/bin/ollama', '/opt/homebrew/bin/ollama', '/usr/bin/ollama',
                   'C:/Program Files/Ollama/ollama.exe',
                   path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'ollama.exe')]) {
    if (fs.existsSync(p)) return p
  }
  return 'ollama'
}

function httpGet(url, timeout = 1500) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout }, (res) => {
      let d = ''; res.on('data', (c) => (d += c)); res.on('end', () => resolve({ ok: res.statusCode < 400, body: d }))
    })
    req.on('error', () => resolve({ ok: false }))
    req.on('timeout', () => { req.destroy(); resolve({ ok: false }) })
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const humanSize = (bytes) => {
  if (!bytes) return ''
  const gb = bytes / 1e9
  return gb >= 1 ? gb.toFixed(1) + ' GB' : Math.round(bytes / 1e6) + ' MB'
}

// Call the local Ollama HTTP API (the running server on :11434). This works
// whether or not the `ollama` CLI binary is installed — the desktop app talks
// to the runtime over HTTP. For streaming endpoints (pull), onChunk receives
// each NDJSON object. Resolves { ok, status, error }.
function ollamaApi(method, pathname, body, onChunk) {
  return new Promise((resolve) => {
    const data = body ? Buffer.from(JSON.stringify(body)) : null
    const req = http.request({ host: '127.0.0.1', port: 11434, path: pathname, method,
      headers: data ? { 'Content-Type': 'application/json', 'Content-Length': data.length } : {} }, (res) => {
      let buf = ''
      res.on('data', (c) => {
        buf += c.toString()
        if (onChunk) {
          let i
          while ((i = buf.indexOf('\n')) >= 0) {
            const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1)
            if (line) { try { onChunk(JSON.parse(line)) } catch {} }
          }
        }
      })
      res.on('end', () => {
        if (onChunk && buf.trim()) { try { onChunk(JSON.parse(buf.trim())) } catch {} }
        resolve({ ok: res.statusCode < 400, status: res.statusCode, body: buf })
      })
    })
    req.on('error', (e) => resolve({ ok: false, error: e.message }))
    req.setTimeout(600000, () => { req.destroy(); resolve({ ok: false, error: 'timeout' }) })
    if (data) req.write(data)
    req.end()
  })
}
const ollamaUp = async () => (await httpGet('http://127.0.0.1:11434/api/tags', 1500)).ok

async function waitFor(url, tries = 40, gap = 500) {
  for (let i = 0; i < tries; i++) {
    if ((await httpGet(url)).ok) return true
    await sleep(gap)
  }
  return false
}

// ── local stack ───────────────────────────────────────────────────────────
async function ensurePostgres(send) {
  const bin = pgBin()
  if (!bin) { send && send('Postgres not found — backend will try its configured DB.'); return false }
  const ready = spawn(path.join(bin, 'pg_isready'), ['-h', '127.0.0.1', '-p', String(PG_PORT)])
  const ok = await new Promise((r) => ready.on('exit', (code) => r(code === 0)))
  if (ok) { send && send('PostgreSQL already running.'); return true }
  if (!fs.existsSync(path.join(PGDATA, 'PG_VERSION'))) {
    send && send('Initializing local database…')
    await new Promise((r) => spawn(path.join(bin, 'initdb'),
      ['-D', PGDATA, '-U', 'hermus', '--auth=trust', '--encoding=UTF8']).on('exit', r))
  }
  send && send('Starting PostgreSQL…')
  await new Promise((r) => spawn(path.join(bin, 'pg_ctl'),
    ['-D', PGDATA, '-o', `-p ${PG_PORT} -k ${PGDATA} -c listen_addresses=127.0.0.1`,
     '-l', path.join(PGDATA, 'server.log'), 'start']).on('exit', r))
  await sleep(1500)
  spawn(path.join(bin, 'createdb'), ['-h', '127.0.0.1', '-p', String(PG_PORT), '-U', 'hermus', 'hermus'])
  pgStarted = true
  return true
}

async function ensureBackend(send) {
  if ((await httpGet(`http://127.0.0.1:${API_PORT}/api/v1/health`)).ok) {
    send && send('Core service already running.'); return true
  }
  send && send('Starting the HERMUS core service…')
  const py = fs.existsSync(VENV_PY) ? VENV_PY : 'python3'
  backendProc = spawn(py, ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', String(API_PORT)],
    { cwd: BACKEND_DIR, env: { ...process.env, HERMUS_DB_PORT: String(PG_PORT) } })
  backendProc.stdout.on('data', (d) => process.stdout.write(`[core] ${d}`))
  backendProc.stderr.on('data', (d) => process.stdout.write(`[core] ${d}`))
  const ok = await waitFor(`http://127.0.0.1:${API_PORT}/api/v1/health`)
  if (ok) {
    // best-effort seed so first run has demo data
    const seed = spawn(py, ['-m', 'app.seed'], { cwd: BACKEND_DIR, env: { ...process.env, HERMUS_DB_PORT: String(PG_PORT) } })
    await new Promise((r) => seed.on('exit', r))
  }
  return ok
}

function startStaticServer() {
  if (DEV) return Promise.resolve(VITE_URL)
  return new Promise((resolve) => {
    const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
      '.svg': 'image/svg+xml', '.png': 'image/png', '.json': 'application/json' }
    staticServer = http.createServer((req, res) => {
      let p = decodeURIComponent(req.url.split('?')[0])
      let file = path.join(DIST_DIR, p)
      if (!fs.existsSync(file) || fs.statSync(file).isDirectory()) file = path.join(DIST_DIR, 'index.html')
      fs.readFile(file, (err, data) => {
        if (err) { res.writeHead(404); res.end('not found'); return }
        res.writeHead(200, { 'Content-Type': types[path.extname(file)] || 'application/octet-stream' })
        res.end(data)
      })
    })
    // Bind to an OS-assigned free port (0) so we can never collide with a stale
    // instance — the previous fixed port 5179 was the cause of EADDRINUSE crashes.
    staticServer.on('error', (e) => { console.error('[static]', e.message); resolve(null) })
    staticServer.listen(0, '127.0.0.1', () => resolve(`http://127.0.0.1:${staticServer.address().port}`))
  })
}

// ── window + chrome ─────────────────────────────────────────────────────────
async function createWindow() {
  win = new BrowserWindow({
    width: 1380, height: 900, minWidth: 1080, minHeight: 680,
    backgroundColor: '#f5f6fb', title: 'HERMUS',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: { preload: path.join(__dirname, 'preload.js'), contextIsolation: true },
  })

  await win.loadFile(path.join(__dirname, 'splash.html'))

  const send = (m) => win && win.webContents.executeJavaScript(
    `window.__setBoot && window.__setBoot(${JSON.stringify(m)})`).catch(() => {})

  // Online mode (packaged build): the backend + database run in the cloud, so we
  // only serve the bundled UI and manage the local AI runtime (Ollama). The full
  // local stack (Postgres + FastAPI) is started only in dev.
  if (DEV) {
    await ensurePostgres(send)
    await ensureBackend(send)
  }
  const uiBase = await startStaticServer()
  send('Opening HERMUS…')
  await sleep(300)

  // Flow: launch → login → (first run) install everything → dashboard.
  // The post-login redirect to /welcome handles first-run install; we just open
  // the app root (which shows login when signed out). /setup remains available
  // from the tray for diagnostics/re-install.
  const startPath = process.env.HERMUS_START_PATH || '/'
  await win.loadURL(`${uiBase}${startPath}`)

  // Optional headless verification: HERMUS_SHOT=/path captures the window.
  if (process.env.HERMUS_SHOT) {
    await sleep(Number(process.env.HERMUS_SHOT_WAIT) || 4000)
    try {
      const img = await win.webContents.capturePage()
      fs.writeFileSync(process.env.HERMUS_SHOT, img.toPNG())
      console.log('[shot] saved', process.env.HERMUS_SHOT)
    } catch (e) { console.log('[shot] failed', e.message) }
    if (process.env.HERMUS_SHOT_QUIT) { await sleep(300); app.quit() }
  }
}

function buildMenu() {
  const template = [
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    { label: 'File', submenu: [{ role: 'quit' }] },
    { label: 'HERMUS', submenu: [
      { label: 'Talk to HERMUS  (Ctrl/Cmd+Shift+Space)', click: triggerVoice },
      { label: 'Setup & Dependencies', click: () => win && win.webContents.executeJavaScript("location.hash='#/setup'") },
      { type: 'separator' },
      { label: 'Open Web Dashboard', click: () => shell.openExternal('http://localhost:5173') },
    ]},
    { role: 'editMenu' }, { role: 'viewMenu' }, { role: 'windowMenu' },
  ]
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

function setupTray() {
  try {
    const img = nativeImage.createFromPath(path.join(__dirname, 'assets', 'tray.png'))
    tray = new Tray(img.isEmpty() ? nativeImage.createEmpty() : img)
    tray.setToolTip('HERMUS — AI Office')
    tray.setContextMenu(Menu.buildFromTemplate([
      { label: 'Show HERMUS', click: () => win && win.show() },
      { label: 'Talk to HERMUS', click: triggerVoice },
      { type: 'separator' }, { role: 'quit' },
    ]))
  } catch {}
}

function triggerVoice() {
  if (!win) return
  win.show()
  win.webContents.executeJavaScript("window.__hermusVoice && window.__hermusVoice()").catch(() => {})
}

// ── IPC bridge (used by preload) ─────────────────────────────────────────────
ipcMain.handle('sys-info', () => {
  const os = require('os')
  return {
    platform: process.platform, arch: process.arch,
    cpus: os.cpus().length, cpuModel: (os.cpus()[0] || {}).model,
    ramGB: Math.round(os.totalmem() / 1e9), freeGB: Math.round(os.freemem() / 1e9),
    apiPort: API_PORT,
  }
})
// Full local system + service health for the dashboard's System Health module.
ipcMain.handle('system-health', async () => {
  const os = require('os')
  let disk = null
  try {
    const st = fs.statfsSync(process.platform === 'win32' ? 'C:\\' : '/')
    const total = st.blocks * st.bsize, free = st.bavail * st.bsize
    disk = { totalGB: +(total / 1e9).toFixed(1), freeGB: +(free / 1e9).toFixed(1),
             usedPct: Math.round((1 - free / total) * 100) }
  } catch {}
  const load = (os.loadavg && os.loadavg()[0]) || 0
  const ram = { totalGB: +(os.totalmem() / 1e9).toFixed(1), freeGB: +(os.freemem() / 1e9).toFixed(1) }
  ram.usedPct = Math.round((1 - ram.freeGB / ram.totalGB) * 100)
  const [core, ollama, pg] = await Promise.all([
    httpGet(`http://127.0.0.1:${API_PORT}/api/v1/health`, 1500).then((r) => r.ok),
    httpGet('http://127.0.0.1:11434/api/tags', 1500).then((r) => r.ok),
    Promise.resolve(pgStarted),
  ])
  let models = 0
  try { const r = await httpGet('http://127.0.0.1:11434/api/tags', 1500); if (r.ok) models = (JSON.parse(r.body).models || []).length } catch {}
  return {
    platform: process.platform, arch: process.arch,
    cpus: os.cpus().length, cpuModel: (os.cpus()[0] || {}).model, loadavg: +load.toFixed(2),
    uptimeMin: Math.round(os.uptime() / 60), appUptimeMin: Math.round(process.uptime() / 60),
    ram, disk,
    services: { core, runtime: ollama, postgres: pg, models },
  }
})
ipcMain.handle('ollama-status', async () => {
  const r = await httpGet('http://127.0.0.1:11434/api/tags', 2000)
  if (!r.ok) return { online: false }
  try { return { online: true, models: (JSON.parse(r.body).models || []).map((m) => ({ name: m.name, size: humanSize(m.size) })) } }
  catch { return { online: true, models: [] } }
})
// Where the runtime + models live on disk (shown in the installer).
ipcMain.handle('runtime-paths', () => {
  const os = require('os')
  let bin = ''
  for (const p of ['/usr/local/bin/ollama', '/opt/homebrew/bin/ollama', '/usr/bin/ollama',
                   path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'ollama.exe')]) {
    if (fs.existsSync(p)) { bin = p; break }
  }
  const models = process.env.OLLAMA_MODELS ||
    (process.platform === 'win32' ? path.join(os.homedir(), '.ollama', 'models')
                                  : path.join(os.homedir(), '.ollama', 'models'))
  return { ollama_bin: bin || '(installs to your system path)', models_dir: models, platform: process.platform }
})
ipcMain.handle('backend-status', async () => (await httpGet(`http://127.0.0.1:${API_PORT}/api/v1/health`)).ok)
ipcMain.handle('open-external', (_e, url) => shell.openExternal(url))
ipcMain.handle('mark-onboarded', () => {
  fs.writeFileSync(path.join(app.getPath('userData'), 'onboarded'), '1'); return true
})
ipcMain.handle('notify', (_e, { title, body }) => {
  if (Notification.isSupported()) new Notification({ title, body }).show()
})
// Pull (download) a model, streaming progress back to the renderer. Prefers the
// Ollama HTTP API so it works even if the `ollama` CLI isn't on PATH.
ipcMain.on('ollama-pull', async (evt, model) => {
  const prog = (line) => evt.sender.send('ollama-pull-progress', { model, line })
  const finish = (ok, error) => evt.sender.send('ollama-pull-done', { model, ok, error })
  if (await ollamaUp()) {
    let last = -1, sawError = null
    const r = await ollamaApi('POST', '/api/pull', { name: model, stream: true }, (o) => {
      if (o.error) { sawError = o.error; prog('error: ' + o.error) }
      else if (o.total) {
        const pct = Math.floor((o.completed || 0) / o.total * 100)
        if (pct !== last) { last = pct; prog(`${o.status || 'downloading'} ${pct}%`) }
      } else if (o.status) prog(o.status)
    })
    return finish(r.ok && !sawError, sawError || r.error)
  }
  // Fallback: the CLI (e.g. server not yet started).
  const p = spawn(ollamaBin(), ['pull', model], { env: SPAWN_ENV })
  const onData = (d) => prog(d.toString())
  p.stdout.on('data', onData); p.stderr.on('data', onData)
  p.on('exit', (code) => finish(code === 0))
  p.on('error', () => finish(false, 'ollama not found'))
})

// ── Auto-install the Ollama runtime (the one external dependency) ────────────
function ollamaInstalled() {
  const r = require('child_process').spawnSync(ollamaBin(), ['--version'], { env: SPAWN_ENV })
  if (!r.error) return true
  for (const p of ['/usr/local/bin/ollama', '/opt/homebrew/bin/ollama',
                   'C:/Program Files/Ollama/ollama.exe', '/usr/bin/ollama']) {
    if (fs.existsSync(p)) return true
  }
  return false
}

// Run a shell command, streaming combined output to the renderer.
function streamCmd(evt, cmd, args, opts = {}) {
  return new Promise((resolve) => {
    const emit = (line) => evt.sender.send('install-progress', { line: String(line).trim().slice(-160) })
    let proc
    try { proc = spawn(cmd, args, { shell: opts.shell || false, env: SPAWN_ENV, ...opts }) }
    catch (e) { emit('failed: ' + e.message); return resolve(false) }
    proc.stdout && proc.stdout.on('data', (d) => emit(d))
    proc.stderr && proc.stderr.on('data', (d) => emit(d))
    proc.on('error', (e) => { emit('failed: ' + e.message); resolve(false) })
    proc.on('exit', (code) => resolve(code === 0))
  })
}

ipcMain.on('install-ollama', async (evt) => {
  const done = (ok, msg) => evt.sender.send('install-done', { ok, message: msg })
  const emit = (line) => evt.sender.send('install-progress', { line })
  try {
    if (ollamaInstalled()) { emit('Ollama is already installed.'); return done(true, 'Ollama is already installed.') }
    emit(`Installing the local AI runtime for ${process.platform}…`)
    let ok = false
    if (process.platform === 'linux') {
      // Official one-line installer (downloads, installs, starts the service).
      ok = await streamCmd(evt, 'sh', ['-c', 'curl -fsSL https://ollama.com/install.sh | sh'])
    } else if (process.platform === 'darwin') {
      // Prefer Homebrew; otherwise download the macOS app and move it into place.
      const hasBrew = !require('child_process').spawnSync('brew', ['--version'], { env: SPAWN_ENV }).error
      if (hasBrew) {
        emit('Installing via Homebrew…')
        ok = await streamCmd(evt, 'brew', ['install', 'ollama'])
        if (ok) await streamCmd(evt, 'brew', ['services', 'start', 'ollama'])
      } else {
        const tmp = path.join(app.getPath('temp'), 'Ollama-darwin.zip')
        emit('Downloading Ollama for macOS…')
        ok = await streamCmd(evt, 'curl', ['-fSL', 'https://ollama.com/download/Ollama-darwin.zip', '-o', tmp])
        if (ok) {
          emit('Unpacking…')
          const dest = '/Applications'
          ok = await streamCmd(evt, 'ditto', ['-x', '-k', tmp, dest])
          if (ok) { emit('Launching Ollama…'); spawn('open', ['-a', 'Ollama']) }
        }
      }
    } else if (process.platform === 'win32') {
      const tmp = path.join(app.getPath('temp'), 'OllamaSetup.exe')
      emit('Downloading Ollama for Windows…')
      ok = await streamCmd(evt, 'curl', ['-fSL', 'https://ollama.com/download/OllamaSetup.exe', '-o', tmp])
      if (ok) { emit('Running the installer…'); ok = await streamCmd(evt, tmp, ['/SILENT']) }
    }
    if (!ok) return done(false, 'Automatic install failed — please install Ollama from ollama.com/download, then click Recheck.')
    // Give the runtime a moment to come online.
    for (let i = 0; i < 15; i++) {
      if ((await httpGet('http://127.0.0.1:11434/api/tags', 1500)).ok) { return done(true, 'Ollama installed and running.') }
      await sleep(1000)
    }
    done(true, 'Ollama installed. Start it if it isn’t running, then click Recheck.')
  } catch (e) {
    done(false, 'Install error: ' + e.message)
  }
})

// Install (pull) / remove a single model — the "Hermes agent" brains.
ipcMain.on('ollama-remove', async (evt, model) => {
  const emit = (line) => evt.sender.send('install-progress', { line })
  const done = (ok, message) => evt.sender.send('install-done', { ok, model, message })
  emit(`Removing ${model}…`)
  // Prefer the HTTP API (DELETE /api/delete) — only needs the running server,
  // so it works even when the `ollama` CLI isn't installed on PATH.
  if (await ollamaUp()) {
    const r = await ollamaApi('DELETE', '/api/delete', { name: model })
    return done(r.ok, r.ok ? `Removed ${model}.`
      : `Could not remove ${model}${r.status === 404 ? ' — it isn’t installed.' : r.error ? ' (' + r.error + ')' : '.'}`)
  }
  // Fallback: the CLI.
  const p = spawn(ollamaBin(), ['rm', model], { env: SPAWN_ENV })
  const onData = (d) => emit(String(d).trim().slice(-160))
  p.stdout && p.stdout.on('data', onData); p.stderr && p.stderr.on('data', onData)
  p.on('exit', (code) => done(code === 0, code === 0 ? `Removed ${model}.` : `Could not remove ${model}.`))
  p.on('error', () => done(false, 'The Ollama runtime isn’t reachable — make sure it’s running.'))
})

// Uninstall the Ollama runtime (best-effort, per-OS). Models in ~/.ollama are
// left unless removed separately. Destructive — the UI confirms first.
ipcMain.on('uninstall-ollama', async (evt) => {
  const done = (ok, msg) => evt.sender.send('install-done', { ok, message: msg })
  const emit = (line) => evt.sender.send('install-progress', { line })
  try {
    emit('Stopping Ollama…')
    try { spawn(ollamaBin(), ['stop'], { env: SPAWN_ENV }) } catch {}
    if (process.platform === 'darwin') {
      try { spawn('/usr/bin/pkill', ['-f', 'Ollama']) } catch {}
      try { spawn('/usr/bin/osascript', ['-e', 'tell application "Ollama" to quit']) } catch {}
    }
    await sleep(900)
    if (process.platform === 'darwin') {
      const hasBrew = !require('child_process').spawnSync('brew', ['list', 'ollama'], { env: SPAWN_ENV }).error
      if (hasBrew) { emit('Removing via Homebrew…'); await streamCmd(evt, 'brew', ['uninstall', 'ollama'], { env: SPAWN_ENV }) }
      else { emit('Removing the Ollama app…'); await streamCmd(evt, '/bin/rm', ['-rf', '/Applications/Ollama.app']) }
      // Remove the CLI symlink the app may have installed.
      for (const p of ['/usr/local/bin/ollama', '/opt/homebrew/bin/ollama']) { try { fs.rmSync(p, { force: true }) } catch {} }
    } else if (process.platform === 'linux') {
      emit('Removing the service & binary (may prompt for sudo)…')
      await streamCmd(evt, 'sh', ['-c',
        'systemctl stop ollama 2>/dev/null; systemctl disable ollama 2>/dev/null; rm -f /usr/local/bin/ollama /usr/bin/ollama'])
    } else if (process.platform === 'win32') {
      const un = path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'uninstall.exe')
      if (fs.existsSync(un)) { emit('Running the uninstaller…'); await streamCmd(evt, un, ['/S']) }
    }
    // Verify by checking the runtime is actually down.
    await sleep(1200)
    const stillUp = await ollamaUp()
    done(!stillUp, !stillUp
      ? 'Ollama uninstalled. (Your downloaded models in ~/.ollama were left in place.)'
      : 'Stopped Ollama, but some files may remain — finish by removing the Ollama app from your Applications / app manager.')
  } catch (e) { done(false, 'Uninstall error: ' + e.message) }
})

// Uninstall the whole HERMUS app: stop services, remove local data, optionally
// purge the AI runtime + models, then hand off to the OS uninstaller / Trash.
ipcMain.on('app-uninstall', async (evt, opts = {}) => {
  const done = (ok, msg) => evt.sender.send('install-done', { ok, message: msg })
  const emit = (line) => evt.sender.send('install-progress', { line })
  const os = require('os')
  try {
    if (opts.removeRuntime) {
      emit('Removing the AI runtime & all models…')
      try { spawn(ollamaBin(), ['stop'], { env: SPAWN_ENV }) } catch {}
      if (process.platform === 'darwin') {
        try { spawn('/usr/bin/pkill', ['-f', 'Ollama']) } catch {}
        const hasBrew = !require('child_process').spawnSync('brew', ['list', 'ollama'], { env: SPAWN_ENV }).error
        if (hasBrew) await streamCmd(evt, 'brew', ['uninstall', 'ollama'], { env: SPAWN_ENV })
        else await streamCmd(evt, '/bin/rm', ['-rf', '/Applications/Ollama.app'])
      } else if (process.platform === 'linux') {
        await streamCmd(evt, 'sh', ['-c',
          'systemctl stop ollama 2>/dev/null; systemctl disable ollama 2>/dev/null; rm -f /usr/local/bin/ollama /usr/bin/ollama'])
      } else if (process.platform === 'win32') {
        const un = path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Ollama', 'uninstall.exe')
        if (fs.existsSync(un)) await streamCmd(evt, un, ['/S'])
      }
      emit('Removing downloaded models…')
      try { fs.rmSync(path.join(os.homedir(), '.ollama'), { recursive: true, force: true }) } catch {}
    }

    emit('Stopping local services…')
    try { backendProc && backendProc.kill() } catch {}
    if (pgStarted) { const bin = pgBin(); if (bin) try { spawn(path.join(bin, 'pg_ctl'), ['-D', PGDATA, 'stop']) } catch {} }

    emit('Removing local data…')
    try { fs.rmSync(app.getPath('userData'), { recursive: true, force: true }) } catch {}

    if (process.platform === 'darwin') {
      const bundle = path.resolve(process.execPath, '..', '..', '..') // …/HERMUS.app
      done(true, 'HERMUS data removed. The app will now move itself to the Trash and quit.')
      setTimeout(async () => { try { await shell.trashItem(bundle) } catch {} ; app.quit() }, 1400)
    } else if (process.platform === 'win32') {
      const uninstaller = path.join(path.dirname(process.execPath), 'Uninstall ' + app.getName() + '.exe')
      if (fs.existsSync(uninstaller)) {
        emit('Launching the Windows uninstaller…')
        try { spawn(uninstaller, ['--force-run'], { detached: true, stdio: 'ignore' }).unref() } catch {}
        done(true, 'The Windows uninstaller has opened — follow its prompts to finish.')
        setTimeout(() => app.quit(), 1000)
      } else {
        done(true, 'Local data removed. Finish in Settings → Apps → HERMUS → Uninstall.')
      }
    } else {
      done(true, 'Local data removed. To finish: if installed from the .deb run “sudo apt remove hermus-desktop”, or just delete the AppImage file.')
    }
  } catch (e) { done(false, 'Uninstall error: ' + e.message) }
})

// ── lifecycle ────────────────────────────────────────────────────────────────
// Only one HERMUS instance — a second launch just focuses the existing window
// (and avoids two processes fighting over the same ports).
if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => { if (win) { if (win.isMinimized()) win.restore(); win.show(); win.focus() } })
  app.whenReady().then(async () => {
    buildMenu()
    setupTray()
    await createWindow()
    globalShortcut.register('CommandOrControl+Shift+Space', triggerVoice)
    app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
  })
}

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
  try { staticServer && staticServer.close() } catch {}
  try { backendProc && backendProc.kill() } catch {}
  if (pgStarted) {
    const bin = pgBin()
    if (bin) try { spawn(path.join(bin, 'pg_ctl'), ['-D', PGDATA, 'stop']) } catch {}
  }
})
