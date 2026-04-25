<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || ''
const MAX_HISTORY = 60

interface HardwareInfo {
  cpu: string | null; gpu: string | null
  motherboard: string | null; ram_gb: number | null
  os: string | null; vram_gb: number | null
}

interface SystemStats {
  cpu: number | null; gpu: number | null
  memory: number | null; vram_used: number | null; vram_total: number | null
}

interface NetworkInfo {
  ipv4: string | null; ipv6: string | null; tailscale: string | null
}

// ========== State ==========
const hw = ref<HardwareInfo | null>(null)
const stats = ref<SystemStats | null>(null)
const net = ref<NetworkInfo | null>(null)
const copyMsg = ref('')
const collapsed = ref({ remote: false, hw: false, charts: false, bars: false })
const cpuHistory = ref<number[]>([])
const gpuHistory = ref<number[]>([])
let statsTimer: ReturnType<typeof setInterval> | null = null

// ========== Fetch ==========
async function fetchJSON(url: string) {
  try {
    const res = await fetch(`${API_BASE}${url}`)
    return res.ok ? res.json() : null
  } catch { return null }
}

async function fetchStats() {
  const data = await fetchJSON('/api/system-stats') as SystemStats | null
  if (!data) return
  stats.value = data
  if (data.cpu != null) {
    cpuHistory.value.push(data.cpu)
    if (cpuHistory.value.length > MAX_HISTORY) cpuHistory.value.shift()
  }
  if (data.gpu != null) {
    gpuHistory.value.push(data.gpu)
    if (gpuHistory.value.length > MAX_HISTORY) gpuHistory.value.shift()
  }
}

// ========== SVG Line Chart ==========
function svgPoints(history: number[], w: number, h: number): string {
  if (history.length === 0) return ''
  const maxLen = Math.max(history.length - 1, 1)
  return history.map((val, i) => {
    const x = (i / maxLen) * w
    const y = h - (Math.min(val, 100) / 100) * h
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')
}

const cpuPoints = computed(() => svgPoints(cpuHistory.value, 200, 60))
const gpuPoints = computed(() => svgPoints(gpuHistory.value, 200, 60))
const cpuCurrent = computed(() => cpuHistory.value.length > 0 ? cpuHistory.value[cpuHistory.value.length - 1] : null)
const gpuCurrent = computed(() => gpuHistory.value.length > 0 ? gpuHistory.value[gpuHistory.value.length - 1] : null)

// ========== Helpers ==========
function copyUrl(url: string) {
  navigator.clipboard.writeText(url).then(() => {
    copyMsg.value = 'Copied!'
    setTimeout(() => { copyMsg.value = '' }, 2000)
  })
}

function isLocal(): boolean {
  const host = window.location.host
  return host === 'localhost:34567' || host.startsWith('127.')
}

function vramPercent(): number {
  if (!stats.value?.vram_total || !stats.value?.vram_used) return 0
  return Math.round((stats.value.vram_used / stats.value.vram_total) * 100)
}

// ========== Lifecycle ==========
onMounted(async () => {
  hw.value = await fetchJSON('/api/hardware-info')
  net.value = await fetchJSON('/api/network-info')
  await fetchStats()
  statsTimer = setInterval(fetchStats, 3000)
})

onUnmounted(() => {
  if (statsTimer) clearInterval(statsTimer)
})
</script>

<template>
  <div class="sys-info">
    <!-- 1. Remote Access Guide -->
    <div class="section" v-if="net && isLocal()">
      <div class="section-header" @click="collapsed.remote = !collapsed.remote">
        <span>{{ collapsed.remote ? '▶' : '▼' }} Remote Access Guide</span>
      </div>
      <div v-if="!collapsed.remote" class="net-body">
        <div class="net-row" v-if="net.ipv4">
          <span class="net-label">LAN</span>
          <code class="net-url">http://{{ net.ipv4 }}:34567</code>
          <button class="btn-copy" @click="copyUrl(`http://${net.ipv4}:34567`)">Copy</button>
        </div>
        <div class="net-row" v-if="net.ipv6">
          <span class="net-label">IPv6</span>
          <code class="net-url">http://[{{ net.ipv6 }}]:34567</code>
          <button class="btn-copy" @click="copyUrl(`http://[${net.ipv6}]:34567`)">Copy</button>
        </div>
        <div class="net-row net-off" v-else>
          <span class="net-label">IPv6</span><span>No global IPv6 on this network</span>
        </div>
        <div class="net-row" v-if="net.tailscale">
          <span class="net-label">Tailscale</span>
          <code class="net-url">http://{{ net.tailscale }}:34567</code>
          <button class="btn-copy" @click="copyUrl(`http://${net.tailscale}:34567`)">Copy</button>
        </div>
        <div class="net-row net-off" v-else>
          <span class="net-label">Tailscale</span><span>Not detected</span>
        </div>
        <div class="net-hint">Use any address above to access from outside your local network.</div>
      </div>
    </div>

    <!-- 2. Hardware Configuration -->
    <div class="section">
      <div class="section-header" @click="collapsed.hw = !collapsed.hw">
        <span>{{ collapsed.hw ? '▶' : '▼' }} Hardware Configuration</span>
      </div>
      <div v-if="!collapsed.hw" class="hw-grid">
        <div class="hw-card">
          <span class="hw-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/>
            </svg>
          </span>
          <span class="hw-label">CPU</span>
          <span class="hw-value">{{ hw?.cpu || '--' }}</span>
        </div>
        <div class="hw-card">
          <span class="hw-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/>
            </svg>
          </span>
          <span class="hw-label">GPU</span>
          <span class="hw-value">{{ hw?.gpu || '--' }}</span>
        </div>
        <div class="hw-card">
          <span class="hw-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="2" y="2" width="20" height="8" rx="2"/><rect x="2" y="14" width="20" height="8" rx="2"/>
            </svg>
          </span>
          <span class="hw-label">Motherboard</span>
          <span class="hw-value">{{ hw?.motherboard || '--' }}</span>
        </div>
        <div class="hw-card">
          <span class="hw-icon">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="4" y="4" width="16" height="16" rx="2"/><line x1="12" y1="4" x2="12" y2="20"/><line x1="4" y1="12" x2="20" y2="12"/>
            </svg>
          </span>
          <span class="hw-label">Memory</span>
          <span class="hw-value">{{ hw?.ram_gb ? `${hw.ram_gb} GB` : '--' }}{{ hw?.vram_gb ? ` / ${hw.vram_gb} GB VRAM` : '' }}</span>
        </div>
      </div>
    </div>

    <!-- 3. CPU / GPU Utilization Charts -->
    <div class="section">
      <div class="section-header" @click="collapsed.charts = !collapsed.charts">
        <span>{{ collapsed.charts ? '▶' : '▼' }} Utilization History</span>
      </div>
      <div v-if="!collapsed.charts" class="chart-grid">
        <div class="chart-box">
          <div class="chart-title-bar">
            <span>CPU</span>
            <span class="chart-current">{{ cpuCurrent != null ? cpuCurrent + '%' : '--' }}</span>
          </div>
          <svg class="chart-svg" viewBox="0 0 200 60" preserveAspectRatio="none">
            <line x1="0" y1="30" x2="200" y2="30" stroke="#E2E8F0" stroke-width="0.5"/>
            <line x1="0" y1="15" x2="200" y2="15" stroke="#F1F5F9" stroke-width="0.5"/>
            <line x1="0" y1="45" x2="200" y2="45" stroke="#F1F5F9" stroke-width="0.5"/>
            <polyline v-if="cpuPoints" :points="cpuPoints" fill="none" stroke="#4F46E5" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
          </svg>
        </div>
        <div class="chart-box">
          <div class="chart-title-bar">
            <span>GPU</span>
            <span class="chart-current">{{ gpuCurrent != null ? gpuCurrent + '%' : '--' }}</span>
          </div>
          <svg class="chart-svg" viewBox="0 0 200 60" preserveAspectRatio="none">
            <line x1="0" y1="30" x2="200" y2="30" stroke="#E2E8F0" stroke-width="0.5"/>
            <line x1="0" y1="15" x2="200" y2="15" stroke="#F1F5F9" stroke-width="0.5"/>
            <line x1="0" y1="45" x2="200" y2="45" stroke="#F1F5F9" stroke-width="0.5"/>
            <polyline v-if="gpuPoints" :points="gpuPoints" fill="none" stroke="#10B981" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
          </svg>
        </div>
      </div>
    </div>

    <!-- 4. Live Utilization Bars -->
    <div class="section">
      <div class="section-header" @click="collapsed.bars = !collapsed.bars">
        <span>{{ collapsed.bars ? '▶' : '▼' }} Current Usage</span>
      </div>
      <div v-if="!collapsed.bars" class="stats-body">
        <div class="stat-row">
          <span class="stat-row-label">CPU</span>
          <div class="stat-bar-bg"><div class="stat-bar-fill cpu" :style="{ width: (stats?.cpu ?? 0) + '%' }"></div></div>
          <span class="stat-row-val">{{ stats?.cpu != null ? stats.cpu + '%' : '--' }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-row-label">GPU</span>
          <div class="stat-bar-bg"><div class="stat-bar-fill gpu" :style="{ width: (stats?.gpu ?? 0) + '%' }"></div></div>
          <span class="stat-row-val">{{ stats?.gpu != null ? stats.gpu + '%' : '--' }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-row-label">Memory</span>
          <div class="stat-bar-bg"><div class="stat-bar-fill mem" :style="{ width: (stats?.memory ?? 0) + '%' }"></div></div>
          <span class="stat-row-val">{{ stats?.memory != null ? stats.memory + '%' : '--' }}</span>
        </div>
        <div class="stat-row">
          <span class="stat-row-label">VRAM</span>
          <div class="stat-bar-bg"><div class="stat-bar-fill vram" :style="{ width: vramPercent() + '%' }"></div></div>
          <span class="stat-row-val">{{ vramPercent() > 0 ? vramPercent() + '%' : '--' }}</span>
        </div>
      </div>
    </div>

    <span v-if="copyMsg" class="toast">{{ copyMsg }}</span>
  </div>
</template>

<style scoped>
.sys-info {
  display: flex; flex-direction: column; gap: 10px;
  overflow-y: auto; min-height: 0; flex: 1;
  padding: 4px 0; position: relative;
}

.section {
  background: var(--card-bg);
  border-radius: var(--radius);
  border: 1.5px solid var(--border);
  box-shadow: var(--shadow);
  overflow: hidden;
}

.section-header {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 16px; cursor: pointer; user-select: none;
  font-weight: 600; font-size: 0.85rem; color: var(--text-title);
  border-bottom: 1.5px solid var(--border);
  background: #FAFBFC;
}

/* ===== Hardware Grid ===== */
.hw-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 1px; background: var(--border);
}
.hw-card {
  background: var(--card-bg); padding: 14px;
  display: flex; flex-direction: column; gap: 4px;
}
.hw-icon { color: var(--brand); opacity: 0.7; }
.hw-label { font-size: 0.68rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--text-muted); }
.hw-value { font-size: 0.78rem; color: var(--text-title); line-height: 1.4; word-break: break-all; }

/* ===== Charts ===== */
.chart-grid {
  display: grid; grid-template-columns: 1fr 1fr;
  gap: 1px; background: var(--border);
}
.chart-box {
  background: var(--card-bg); padding: 12px;
}
.chart-title-bar {
  display: flex; justify-content: space-between; align-items: center;
  margin-bottom: 6px;
  font-size: 0.75rem; font-weight: 600; color: var(--text-body);
}
.chart-current {
  font-family: 'JetBrains Mono', monospace;
  font-size: 0.85rem; font-weight: 700; color: var(--text-title);
}
.chart-svg {
  width: 100%; height: 56px;
  display: block;
}

/* ===== Live Bars ===== */
.stats-body { padding: 12px 16px; display: flex; flex-direction: column; gap: 10px; }
.stat-row { display: flex; align-items: center; gap: 10px; }
.stat-row-label { font-size: 0.78rem; font-weight: 600; color: var(--text-title); width: 52px; flex-shrink: 0; }
.stat-bar-bg { flex: 1; height: 18px; background: #F1F5F9; border-radius: 4px; overflow: hidden; }
.stat-bar-fill { height: 100%; border-radius: 4px; transition: width 0.8s ease; }
.stat-bar-fill.cpu { background: var(--brand); }
.stat-bar-fill.gpu { background: #10B981; }
.stat-bar-fill.mem { background: #F59E0B; }
.stat-bar-fill.vram { background: #8B5CF6; }
.stat-row-val { font-size: 0.78rem; font-weight: 600; font-family: 'JetBrains Mono', monospace; color: var(--text-title); width: 48px; text-align: right; flex-shrink: 0; }

/* ===== Remote Access ===== */
.net-body { padding: 12px 16px; display: flex; flex-direction: column; gap: 6px; }
.net-row { display: flex; align-items: center; gap: 8px; font-size: 0.82rem; }
.net-label { font-weight: 600; color: var(--text-body); min-width: 60px; flex-shrink: 0; }
.net-url { font-family: 'JetBrains Mono', 'Consolas', monospace; font-size: 0.78rem; color: var(--text-title); word-break: break-all; flex: 1; }
.btn-copy { font-size: 0.7rem; padding: 2px 10px; background: #E2E8F0; border: 1px solid #CBD5E1; border-radius: 4px; cursor: pointer; flex-shrink: 0; }
.btn-copy:hover { background: #CBD5E1; }
.net-off { color: #94A3B8; }
.net-hint { font-size: 0.72rem; color: var(--text-muted); margin-top: 4px; line-height: 1.4; }

.toast {
  position: fixed; top: 12px; right: 12px;
  font-size: 0.78rem; color: #16A34A; font-weight: 600;
  background: #F0FDF4; padding: 4px 12px; border-radius: 6px;
  border: 1px solid #BBF7D0;
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
  .sys-info { padding: 0; }
  .hw-card { padding: 12px; }
  .hw-value { font-size: 0.72rem; }
  .chart-box { padding: 10px; }
  .chart-svg { height: 48px; }
  .net-row { flex-wrap: wrap; }
  .net-url { width: 100%; order: 1; }
  .btn-copy { order: 2; }
  .stats-body { padding: 10px 12px; }
}

@media (max-width: 480px) {
  .hw-grid { grid-template-columns: 1fr; }
  .chart-grid { grid-template-columns: 1fr; }
  .stat-row-label { width: 44px; font-size: 0.72rem; }
  .stat-bar-bg { height: 16px; }
}
</style>
