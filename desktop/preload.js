// Secure bridge between the renderer (React UI) and the Electron main process.
const { contextBridge, ipcRenderer } = require('electron')

const API_PORT = 7700

contextBridge.exposeInMainWorld('hermus', {
  isElectron: true,
  apiBase: `http://127.0.0.1:${API_PORT}/api/v1`,
  wsBase: `ws://127.0.0.1:${API_PORT}/ws/v1/events`,

  systemInfo: () => ipcRenderer.invoke('sys-info'),
  systemHealth: () => ipcRenderer.invoke('system-health'),
  ollamaStatus: () => ipcRenderer.invoke('ollama-status'),
  runtimePaths: () => ipcRenderer.invoke('runtime-paths'),
  backendStatus: () => ipcRenderer.invoke('backend-status'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  markOnboarded: () => ipcRenderer.invoke('mark-onboarded'),
  notify: (title, body) => ipcRenderer.invoke('notify', { title, body }),

  pullModel: (model, onProgress, onDone) => {
    const prog = (_e, p) => { if (p.model === model) onProgress(p.line) }
    const done = (_e, p) => {
      if (p.model === model) {
        ipcRenderer.removeListener('ollama-pull-progress', prog)
        ipcRenderer.removeListener('ollama-pull-done', done)
        onDone(p)
      }
    }
    ipcRenderer.on('ollama-pull-progress', prog)
    ipcRenderer.on('ollama-pull-done', done)
    ipcRenderer.send('ollama-pull', model)
  },

  // Runtime/model management (install + uninstall), all with streamed progress.
  installOllama: (onProgress, onDone) => runtimeOp('install-ollama', null, onProgress, onDone),
  uninstallOllama: (onProgress, onDone) => runtimeOp('uninstall-ollama', null, onProgress, onDone),
  removeModel: (model, onProgress, onDone) => runtimeOp('ollama-remove', model, onProgress, onDone),

  // Uninstall the whole HERMUS app (data + optional runtime), then hand off to
  // the OS uninstaller / trash. opts = { removeRuntime: boolean }.
  uninstallApp: (opts, onProgress, onDone) => runtimeOp('app-uninstall', opts || {}, onProgress, onDone),
})

// Shared helper: send a runtime op and relay install-progress / install-done.
function runtimeOp(channel, arg, onProgress, onDone) {
  const prog = (_e, p) => onProgress && onProgress(p.line)
  const done = (_e, p) => {
    ipcRenderer.removeListener('install-progress', prog)
    ipcRenderer.removeListener('install-done', done)
    onDone && onDone(p)
  }
  ipcRenderer.on('install-progress', prog)
  ipcRenderer.on('install-done', done)
  if (arg != null) ipcRenderer.send(channel, arg)
  else ipcRenderer.send(channel)
}
