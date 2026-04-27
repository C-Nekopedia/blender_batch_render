<script setup lang="ts">
import { ref, watch, nextTick, computed } from 'vue'
import type { TerminalLine } from '../composables/useTerminal'

const props = defineProps<{
  terminalLines: TerminalLine[]
  errorLines: TerminalLine[]
  isRunning: boolean
  wsConnected: boolean
}>()

const emit = defineEmits<{
  clear: []
}>()

const activeTab = ref<'console' | 'errors'>('console')
const errorCount = computed(() => props.errorLines.length)
const terminalEl = ref<HTMLElement | null>(null)

// Auto-scroll when lines change
watch(() => props.terminalLines, () => {
  nextTick(() => {
    if (terminalEl.value) {
      terminalEl.value.scrollTop = terminalEl.value.scrollHeight
    }
  })
}, { deep: true })
</script>

<template>
  <div class="panel">
    <!-- Tab bar -->
    <div class="tab-bar">
      <button class="tab" :class="{ active: activeTab === 'console' }" @click="activeTab = 'console'">
        Console
      </button>
      <button class="tab" :class="{ active: activeTab === 'errors' }" @click="activeTab = 'errors'">
        Errors
        <span v-if="errorCount > 0" class="tab-badge">{{ errorCount }}</span>
      </button>
      <div class="tab-bar-spacer"></div>
      <button class="btn-icon" @click="emit('clear')" title="Clear">Clear</button>
    </div>

    <!-- Console tab -->
    <div v-if="activeTab === 'console'" class="terminal" ref="terminalEl">
      <div v-for="line in terminalLines" :key="line.id" class="terminal-line">
        <span class="terminal-time">[{{ line.time }}]</span>
        <span :class="['terminal-msg', line.type]">{{ line.text }}</span>
      </div>
      <div class="terminal-cursor-line">
        <span class="terminal-time" style="color:var(--terminal-dim);font-size:0.75rem;">
          {{ isRunning ? 'Rendering...' : !wsConnected ? '正在连接...' : 'Ready for render' }}
        </span>
        <span class="terminal-cursor"></span>
      </div>
    </div>

    <!-- Errors tab -->
    <div v-if="activeTab === 'errors'" class="terminal">
      <div v-if="errorLines.length === 0" class="terminal-line" style="color:var(--terminal-dim)">
        No errors
      </div>
      <div v-for="line in errorLines" :key="line.id" class="terminal-line">
        <span class="terminal-time">[{{ line.time }}]</span>
        <span class="terminal-msg error">{{ line.text }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panel {
  background: var(--card-bg);
  border-radius: var(--radius);
  border: 1.5px solid var(--border);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.tab-bar {
  display: flex;
  align-items: center;
  border-bottom: 1.5px solid var(--border);
  padding: 0 8px;
  flex-shrink: 0;
  background: #F8FAFC;
}
.tab {
  padding: 10px 16px;
  border: none;
  background: none;
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -1.5px;
  transition: all var(--transition);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.tab:hover { color: var(--text-title); }
.tab.active {
  color: var(--brand);
  border-bottom-color: var(--brand);
}
.tab-badge {
  background: var(--danger);
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 10px;
  line-height: 1.4;
}
.tab-bar-spacer { flex: 1; }

.btn-icon {
  background: none;
  border: 1.5px solid var(--border);
  border-radius: 6px;
  padding: 4px 8px;
  cursor: pointer;
  color: var(--text-muted);
  font-size: 0.75rem;
  transition: all var(--transition);
}

.btn-icon:hover {
  background: #F1F5F9;
  border-color: var(--text-muted);
}

.terminal {
  flex: 1;
  background: var(--terminal-bg);
  padding: 16px;
  font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
  font-size: 0.8rem;
  line-height: 1.7;
  overflow-y: auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.terminal-line {
  display: flex;
  gap: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  animation: fadeIn 0.15s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(-2px); }
  to { opacity: 1; transform: translateY(0); }
}

.terminal-time {
  color: var(--terminal-dim);
  flex-shrink: 0;
  user-select: none;
}

.terminal-msg { color: #E2E8F0; }
.terminal-msg.info { color: #60A5FA; }
.terminal-msg.ok { color: var(--terminal-green); }
.terminal-msg.warn { color: var(--warning); }
.terminal-msg.error { color: var(--danger); }
.terminal-msg.frame { color: #A78BFA; }
.terminal-msg.sample { color: #FBBF24; }
.terminal-msg.dim { color: var(--terminal-dim); }

.terminal-cursor-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: auto;
  min-height: 1.7em;
}

.terminal-cursor {
  display: inline-block;
  width: 8px;
  height: 16px;
  background: var(--terminal-green);
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% { opacity: 0; }
}

.terminal::-webkit-scrollbar { width: 6px; }
.terminal::-webkit-scrollbar-track { background: transparent; }
.terminal::-webkit-scrollbar-thumb { background: #334155; border-radius: 3px; }

@media (max-width: 768px) {
  .terminal {
    min-height: 400px;
    max-height: 400px;
  }
  .panel-header {
    padding: 12px 16px;
  }
}
</style>
