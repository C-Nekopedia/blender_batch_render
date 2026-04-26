<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useTerminal } from './composables/useTerminal'
import { useSettings } from './composables/useSettings'
import SystemInfo from './components/SystemInfo.vue'
import TerminalConsole from './components/TerminalConsole.vue'
import SettingsPanel from './components/SettingsPanel.vue'
import StatsBar from './components/StatsBar.vue'
import PreviewPanel from './components/PreviewPanel.vue'
import type { PreviewFile } from './components/PreviewPanel.vue'

const API_BASE = import.meta.env.VITE_API_BASE || ''

// =====================================================================
// Composables
// =====================================================================
const {
  terminalLines,
  errorLines,
  frameLineMap,
  writeTerminal,
  writeError,
  updateProgressLine,
  finalizeProgressLine,
  clearConsole,
  formatElapsed,
} = useTerminal()

const {
  blenderPath,
  blendFile,
  startFrame,
  endFrame,
  batchSize,
  memThreshold,
  restartDelay,
  crashLimit, crashWindow,
  loadSettings,
  saveSettingsToBackend,
  browseFile,
  getRenderBody,
  validate: validateSettings,
} = useSettings()

// =====================================================================
// View navigation
// =====================================================================
const currentView = ref<'tasks' | 'system' | 'preview'>('tasks')
const mobileMenuOpen = ref(false)
const isRemote = computed(() => {
  const host = window.location.host
  return host !== 'localhost:34567' && !host.startsWith('127.')
})

// =====================================================================
// WebSocket state
// =====================================================================
const isRunning = ref(false)
const wsConnected = ref(false)
const statTime = ref('--:--:--')
const statProgress = ref('--%')
const renderStartTime = ref<number | null>(null)
const completedFrames = ref(0)
let totalFramesCount = 0
const previewFiles = ref<PreviewFile[]>([])
const previewOutputDir = ref<string | null>(null)

// =====================================================================
// WebSocket connection
// =====================================================================
function wsUrl(): string {
  if (API_BASE) {
    return API_BASE.replace(/^http/, 'ws') + '/ws'
  }
  const loc = window.location
  const proto = loc.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${loc.host}/ws`
}

let ws: WebSocket | null = null
let wsReconnectTimer: ReturnType<typeof setTimeout> | null = null
let wsConnectTimer: ReturnType<typeof setTimeout> | null = null

function connectWebSocket() {
  wsConnected.value = false
  ws = new WebSocket(wsUrl())

  wsConnectTimer = setTimeout(() => {
    if (!wsConnected.value) {
      writeTerminal('WebSocket connection timeout — is the backend running?', 'error')
    }
  }, 5000)

  ws.onopen = () => {
    if (wsConnectTimer) clearTimeout(wsConnectTimer)
    if (wsReconnectTimer) clearTimeout(wsReconnectTimer)
    wsConnected.value = true
    writeTerminal('WebSocket connected', 'ok')
  }

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data)
      switch (msg.type) {
        case 'batch_start':
          writeTerminal(`Batch: frames ${msg.data.start} - ${msg.data.end}`, 'frame')
          break

        case 'frame_progress':
          updateProgressLine(msg.data.frame, msg.data.sample_curr, msg.data.sample_total, msg.data.elapsed)
          break

        case 'frame_saved':
          finalizeProgressLine(msg.data.frame)
          completedFrames.value++
          statProgress.value = totalFramesCount > 0
            ? `${Math.round((completedFrames.value / totalFramesCount) * 100)}%`
            : '--%'
          if (renderStartTime.value) {
            statTime.value = formatElapsed((Date.now() - renderStartTime.value) / 1000)
          }
          break

        case 'memory_restart':
          writeTerminal(`Memory restart at frame ${msg.data.next_frame}: ${msg.data.note}`, 'warn')
          break

        case 'error':
          writeError(msg.data.message)
          break

        case 'preview_update':
          previewFiles.value = msg.data.files ?? []
          previewOutputDir.value = msg.data.output_dir ?? null
          break

        case 'complete':
          writeTerminal('Render complete', 'ok')
          isRunning.value = false
          renderStartTime.value = null
          statProgress.value = '100%'
          frameLineMap.clear()
          break

        case 'system_stats':
          if (renderStartTime.value) {
            statTime.value = formatElapsed((Date.now() - renderStartTime.value) / 1000)
          }
          break
      }
    } catch {
      console.warn('Malformed WebSocket message:', event.data)
    }
  }

  ws.onclose = () => {
    if (wsConnectTimer) clearTimeout(wsConnectTimer)
    wsConnected.value = false
    writeTerminal('WebSocket disconnected', 'warn')
    isRunning.value = false
    renderStartTime.value = null
    frameLineMap.clear()
    wsReconnectTimer = setTimeout(connectWebSocket, 3000)
  }

  ws.onerror = () => {
    if (wsConnectTimer) clearTimeout(wsConnectTimer)
    wsConnected.value = false
    writeTerminal('WebSocket error', 'error')
  }
}

// =====================================================================
// Render control
// =====================================================================
async function startRender() {
  if (!wsConnected.value) {
    writeTerminal('Error: WebSocket not connected. Please wait.', 'error')
    return
  }

  const body = getRenderBody()

  writeTerminal('Starting render...', 'info')
  writeTerminal(`  Blender: ${body.blender}`, 'dim')
  writeTerminal(`  Scene:   ${body.blend || '(not set)'}`, 'dim')
  writeTerminal(`  Frames:  ${body.start} - ${body.end}`, 'dim')
  writeTerminal(`  Batch:   ${body.batch}`, 'dim')

  await saveSettingsToBackend()

  try {
    const res = await fetch(`${API_BASE}/render/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    if (!res.ok) {
      const err = await res.json()
      const detail = Array.isArray(err.detail) ? err.detail.map((d: any) => d.msg ?? JSON.stringify(d)).join('; ') : err.detail
      writeTerminal(`Error: ${detail}`, 'error')
      return
    }
    isRunning.value = true
    frameLineMap.clear()
    renderStartTime.value = Date.now()
    completedFrames.value = 0
    previewFiles.value = []
    previewOutputDir.value = null
    totalFramesCount = endFrame.value - startFrame.value + 1
    statTime.value = '00:00:00'
    statProgress.value = '0%'
    writeTerminal('Render engine started, waiting for progress...', 'info')
  } catch (e: any) {
    writeTerminal(`Failed to start render: ${e.message}`, 'error')
  }
}

async function stopRender() {
  try {
    const res = await fetch(`${API_BASE}/render/stop`, {
      method: 'POST',
    })
    if (!res.ok) {
      const err = await res.json()
      const detail = Array.isArray(err.detail) ? err.detail.map((d: any) => d.msg ?? JSON.stringify(d)).join('; ') : err.detail
      writeTerminal(`Error: ${detail}`, 'error')
    } else {
      writeTerminal('Render stopped by user', 'warn')
    }
  } catch (e: any) {
    writeTerminal(`Failed to stop render: ${e.message}`, 'error')
  }
  isRunning.value = false
  renderStartTime.value = null
}

// =====================================================================
// Save settings with validation
// =====================================================================
async function saveSettings() {
  const errors = validateSettings()
  if (errors.length > 0) {
    writeTerminal('保存设置失败：', 'error')
    errors.forEach(e => writeTerminal(`  - ${e}`, 'error'))
    return
  }

  try {
    const res = await fetch(`${API_BASE}/api/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        blender: blenderPath.value,
        blend: blendFile.value,
        start: startFrame.value,
        end: endFrame.value,
        batch: batchSize.value,
        memory_threshold: memThreshold.value,
        restart_delay: restartDelay.value,
      }),
    })
    if (!res.ok) {
      const err = await res.json()
      const msg = err.detail?.message || '后端校验失败'
      writeTerminal(`保存失败: ${msg}`, 'error')
      if (err.detail?.errors) {
        err.detail.errors.forEach((e: string) => writeTerminal(`  - ${e}`, 'error'))
      }
      return
    }
    writeTerminal('设置已保存', 'ok')
  } catch (e: any) {
    writeTerminal(`保存设置失败: ${e.message}`, 'error')
  }
}

// =====================================================================
// Request preview list when user switches to Preview tab
// =====================================================================
watch(currentView, (to) => {
  if (to === 'preview' && ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'preview_init' }))
  }
})

// =====================================================================
// Lifecycle
// =====================================================================
onMounted(() => {
  writeTerminal('Blender Batch Render Console ready', 'ok')
  loadSettings()
  connectWebSocket()
})

onUnmounted(() => {
  if (wsReconnectTimer) clearTimeout(wsReconnectTimer)
  if (wsConnectTimer) clearTimeout(wsConnectTimer)
  ws?.close()
})
</script>

<template>
  <div class="app">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="logo">
        <div class="logo-dot"></div>
        <div>Batch Render</div>
      </div>

      <!-- Navigation items -->
      <div class="nav-group" :class="{ open: mobileMenuOpen }">
        <div
          class="nav-item"
          :class="{ active: currentView === 'tasks' }"
          @click="currentView = 'tasks'; mobileMenuOpen = false"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/><line x1="9" y1="9" x2="15" y2="9"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="12" y2="17"/>
          </svg>
          <span>Tasks</span>
        </div>
        <div
          class="nav-item"
          :class="{ active: currentView === 'preview' }"
          @click="currentView = 'preview'; mobileMenuOpen = false"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
            <path d="m21 15-5-5L5 21"/>
          </svg>
          <span>Preview</span>
        </div>
        <div
          class="nav-item"
          :class="{ active: currentView === 'system' }"
          @click="currentView = 'system'; mobileMenuOpen = false"
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <span>System</span>
        </div>
      </div>

      <!-- Hamburger toggle (mobile only) -->
      <button class="nav-menu-btn" @click="mobileMenuOpen = !mobileMenuOpen" aria-label="Navigation menu">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/>
        </svg>
      </button>
    </aside>

    <!-- Main Content -->
    <main class="main">
      <!-- Tasks View -->
      <template v-if="currentView === 'tasks'">
        <header class="header">
          <h1>Tasks</h1>
        </header>

        <div class="content">
          <TerminalConsole
            :terminalLines="terminalLines"
            :errorLines="errorLines"
            :isRunning="isRunning"
            :wsConnected="wsConnected"
            @clear="clearConsole"
          />

          <SettingsPanel
            v-model:blenderPath="blenderPath"
            v-model:blendFile="blendFile"
            v-model:startFrame="startFrame"
            v-model:endFrame="endFrame"
            v-model:batchSize="batchSize"
            v-model:memThreshold="memThreshold"
            v-model:restartDelay="restartDelay"
            v-model:crashLimit="crashLimit"
            v-model:crashWindow="crashWindow"
            :wsConnected="wsConnected"
            :remoteAccess="isRemote"
            @browseFile="browseFile"
            @save="saveSettings"
            @startRender="startRender"
            @stopRender="stopRender"
          />
        </div>

        <StatsBar
          :statTime="statTime"
          :statProgress="statProgress"
          :isRunning="isRunning"
        />
      </template>

      <!-- Preview View -->
      <div v-else-if="currentView === 'preview'" class="content">
        <PreviewPanel
          :files="previewFiles"
          :outputDir="previewOutputDir"
          :isRunning="isRunning"
        />
      </div>

      <!-- System Info View -->
      <SystemInfo v-else />
    </main>
  </div>
</template>

<style>
/* =========================================================
   CSS Variables
   ========================================================= */
:root {
  --brand: #4F46E5;
  --brand-hover: #4338CA;
  --bg-main: #F8FAFC;
  --card-bg: #FFFFFF;
  --text-title: #1E293B;
  --text-body: #64748B;
  --text-muted: #94A3B8;
  --danger: #EF4444;
  --success: #10B981;
  --warning: #F59E0B;
  --border: #CBD5E1;
  --shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --sidebar-w: 260px;
  --radius: 20px;
  --radius-sm: 8px;
  --terminal-bg: #0F172A;
  --terminal-green: #22C55E;
  --terminal-dim: #475569;
  --transition: 0.2s ease;
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  height: 100%;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background: var(--bg-main);
  color: var(--text-body);
  -webkit-font-smoothing: antialiased;
}

/* =========================================================
   Layout
   ========================================================= */
.app {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

.sidebar {
  width: var(--sidebar-w);
  background: var(--card-bg);
  border-right: 1.5px solid var(--border);
  padding: 32px 24px;
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  height: 100%;
}

.logo {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text-title);
  margin-bottom: 48px;
}

.logo-dot {
  width: 12px;
  height: 12px;
  background: var(--brand);
  border-radius: 50%;
  flex-shrink: 0;
}

.nav-item {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 0.9rem;
  font-weight: 500;
  color: var(--text-body);
  transition: all var(--transition);
  margin-bottom: 4px;
  user-select: none;
}
.nav-item:hover {
  background: #F1F5F9;
  color: var(--text-title);
}
.nav-item.active {
  color: var(--brand);
  background: #EEF2FF;
  font-weight: 600;
}

.nav-group { display: flex; flex-direction: column; }

.nav-menu-btn {
  display: none;
  background: none;
  border: 1.5px solid var(--border);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  color: var(--text-body);
  transition: all var(--transition);
  line-height: 0;
  flex-shrink: 0;
}
.nav-menu-btn:hover { background: #F1F5F9; border-color: var(--text-muted); }

.main {
  flex: 1;
  display: flex;
  flex-direction: column;
  padding: 32px 40px;
  gap: 24px;
  overflow: hidden;
  min-width: 0;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.header h1 {
  margin: 0;
  font-size: 1.5rem;
  color: var(--text-title);
  font-weight: 600;
}

.content {
  display: grid;
  grid-template-columns: 1.6fr 1fr;
  gap: 24px;
  flex: 1;
  min-height: 0;
}

/* =========================================================
   Responsive
   ========================================================= */
@media (max-width: 1200px) {
  .content {
    grid-template-columns: 1fr;
  }
  .sidebar {
    width: 200px;
    padding: 24px 16px;
  }
}

@media (max-width: 768px) {
  .app {
    flex-direction: column;
  }
  .sidebar {
    width: 100%;
    flex-direction: row;
    padding: 12px 16px;
    border-right: none;
    border-bottom: 1.5px solid var(--border);
    height: auto;
    align-items: center;
    gap: 8px;
    position: relative;
  }
  .logo {
    margin-bottom: 0;
    margin-right: 0;
    font-size: 1rem;
    gap: 8px;
  }
  .logo-dot {
    width: 10px;
    height: 10px;
  }
  .nav-menu-btn { display: flex; }
  .nav-group {
    display: none;
    position: absolute;
    top: 100%;
    right: 8px;
    min-width: 160px;
    background: var(--card-bg);
    border: 1.5px solid var(--border);
    border-radius: var(--radius-sm);
    box-shadow: 0 8px 24px rgba(0,0,0,0.12);
    padding: 4px;
    z-index: 100;
    flex-direction: column;
  }
  .nav-group.open { display: flex; }
  .nav-group .nav-item {
    padding: 10px 12px;
    font-size: 0.85rem;
    margin-bottom: 0;
    border-radius: 6px;
  }
  .nav-group .nav-item svg { width: 16px; height: 16px; }
  .main {
    padding: 16px;
    gap: 16px;
    display: block;
    overflow-y: auto;
  }
  .content {
    flex: none;
    min-height: auto;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  .header {
    flex-direction: column;
    gap: 8px;
    align-items: stretch;
  }
  .header h1 {
    font-size: 1.2rem;
  }
}
</style>
