<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface NetworkInfo {
  ipv4: string | null
  ipv6: string | null
  tailscale: string | null
}

const API_BASE = import.meta.env.VITE_API_BASE || ''
const info = ref<NetworkInfo | null>(null)
const collapsed = ref(false)
const copyMsg = ref('')

onMounted(async () => {
  try {
    const res = await fetch(`${API_BASE}/api/network-info`)
    if (res.ok) {
      info.value = await res.json()
    }
  } catch {
    // Backend not available, silently ignore
  }
})

function copyUrl(url: string) {
  navigator.clipboard.writeText(url).then(() => {
    copyMsg.value = '✓ 已复制'
    setTimeout(() => { copyMsg.value = '' }, 2000)
  })
}

function localAddrTip(): string {
  const host = window.location.host
  return host !== 'localhost:34567' && !host.startsWith('127.')
    ? 'remote'  // User already accessing remotely
    : 'local'   // User on local machine
}
</script>

<template>
  <div v-if="info && localAddrTip() === 'local'" class="network-info">
    <div class="ni-header" @click="collapsed = !collapsed">
      <span class="ni-title">{{ collapsed ? '▶' : '▼' }} 远程访问指引</span>
      <span class="ni-badge" v-if="info.ipv6">IPv6</span>
      <span class="ni-badge ts" v-if="info.tailscale">Tailscale</span>
    </div>

    <div v-if="!collapsed" class="ni-body">
      <div class="ni-item" v-if="info.ipv4">
        <span class="ni-label">局域网：</span>
        <span class="ni-url">http://{{ info.ipv4 }}:34567</span>
        <button class="ni-copy" @click="copyUrl(`http://${info.ipv4}:34567`)">复制</button>
      </div>

      <div class="ni-item" v-if="info.ipv6" :class="{ v6: true }">
        <span class="ni-label">IPv6 可用：</span>
        <span class="ni-url">http://[{{ info.ipv6 }}]:34567</span>
        <button class="ni-copy" @click="copyUrl(`http://[${info.ipv6}]:34567`)">复制</button>
      </div>
      <div class="ni-item ni-muted" v-else>
        <span class="ni-label">IPv6：</span>
        <span>当前网络无公网 IPv6</span>
      </div>

      <div class="ni-item" v-if="info.tailscale">
        <span class="ni-label">Tailscale：</span>
        <span class="ni-url">http://{{ info.tailscale }}:34567</span>
        <button class="ni-copy" @click="copyUrl(`http://${info.tailscale}:34567`)">复制</button>
      </div>
      <div class="ni-item ni-muted" v-else>
        <span class="ni-label">Tailscale：</span>
        <span>未检测到 Tailscale</span>
      </div>

      <div class="ni-note">
        外出时使用以上任一地址访问。支持 IPv6 的设备优先用 IPv6，否则用 Tailscale。
      </div>
    </div>

    <span v-if="copyMsg" class="ni-toast">{{ copyMsg }}</span>
  </div>
</template>

<style scoped>
.network-info {
  background: #F0F9FF;
  border: 1px solid #BAE6FD;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 0.85rem;
  position: relative;
  flex-shrink: 0;
}
.ni-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  cursor: pointer;
  user-select: none;
}
.ni-title {
  font-weight: 600;
  color: #0369A1;
  flex: 1;
}
.ni-badge {
  font-size: 0.75rem;
  background: #0369A1;
  color: #fff;
  padding: 1px 8px;
  border-radius: 10px;
}
.ni-badge.ts {
  background: #4338CA;
}
.ni-body {
  padding: 0 12px 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ni-item {
  display: flex;
  align-items: center;
  gap: 6px;
}
.ni-label {
  color: #475569;
  white-space: nowrap;
  min-width: 75px;
}
.ni-url {
  font-family: 'JetBrains Mono', 'Consolas', monospace;
  color: #1E293B;
  font-size: 0.8rem;
  word-break: break-all;
}
.ni-copy {
  font-size: 0.7rem;
  padding: 1px 8px;
  background: #E2E8F0;
  border: 1px solid #CBD5E1;
  border-radius: 4px;
  cursor: pointer;
  flex-shrink: 0;
}
.ni-copy:hover {
  background: #CBD5E1;
}
.ni-muted {
  color: #94A3B8;
}
.ni-note {
  color: #64748B;
  font-size: 0.75rem;
  margin-top: 4px;
  line-height: 1.4;
}
.ni-toast {
  position: absolute;
  top: -4px;
  right: 4px;
  font-size: 0.75rem;
  color: #16A34A;
  font-weight: 600;
}
</style>
