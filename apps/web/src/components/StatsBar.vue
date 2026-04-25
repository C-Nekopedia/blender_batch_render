<script setup lang="ts">
defineProps<{
  statTime: string
  statProgress: string
  isRunning: boolean
}>()
</script>

<template>
  <div class="stats-bar">
    <div class="stat-item">
      <span class="stat-label">用时</span>
      <span class="stat-value" :class="{ running: isRunning }">{{ statTime }}</span>
    </div>
    <div class="stat-item">
      <span class="stat-label">进度</span>
      <span class="stat-value" :class="{ running: isRunning, done: statProgress === '100%' }">{{ statProgress }}</span>
    </div>
  </div>
</template>

<style scoped>
.stats-bar {
  padding: 14px 24px;
  background: var(--card-bg);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  display: flex;
  justify-content: space-around;
  align-items: center;
  flex-shrink: 0;
  margin-bottom: 4px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 6px 16px;
  min-width: 80px;
}

.stat-label {
  font-size: 0.75rem;
  color: var(--text-muted);
}

.stat-value {
  font-weight: 600;
  color: var(--text-title);
  font-size: 0.85rem;
  font-family: 'JetBrains Mono', monospace;
}

.stat-value.running { color: var(--brand); }
.stat-value.done { color: var(--success); }

@media (max-width: 768px) {
  .stats-bar {
    padding: 10px 16px;
  }
  .stat-item {
    min-width: 60px;
    padding: 4px 10px;
  }
  .stat-value {
    font-size: 0.8rem;
  }
}
</style>
