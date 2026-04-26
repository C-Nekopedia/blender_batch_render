<script setup lang="ts">
const blenderPath = defineModel<string>('blenderPath', { required: true })
const blendFile = defineModel<string>('blendFile', { required: true })
const startFrame = defineModel<number>('startFrame', { required: true })
const endFrame = defineModel<number>('endFrame', { required: true })
const batchSize = defineModel<number>('batchSize', { required: true })
const memThreshold = defineModel<number>('memThreshold', { required: true })
const restartDelay = defineModel<number>('restartDelay', { required: true })
const crashLimit = defineModel<number>('crashLimit', { required: true })
const crashWindow = defineModel<number>('crashWindow', { required: true })

defineProps<{
  isRunning: boolean
  wsConnected: boolean
  remoteAccess: boolean
}>()

const emit = defineEmits<{
  browseFile: [filter: string, target: 'blender' | 'blend']
  save: []
  startRender: []
  stopRender: []
}>()
</script>

<template>
  <div class="settings-panel">
    <div class="panel-header">
      <span>设置</span>
    </div>

    <div class="settings-body">
      <!-- Blender Executable -->
      <div class="form-group">
        <label class="form-label">Blender 路径</label>
        <div class="file-picker">
          <input class="form-input" type="text" v-model="blenderPath" placeholder="C:\path\to\blender.exe" />
          <button class="btn-browse" v-if="!remoteAccess" @click="emit('browseFile', '.exe', 'blender')">···</button>
        </div>
      </div>

      <!-- Blend File -->
      <div class="form-group">
        <label class="form-label">工程文件</label>
        <div class="file-picker">
          <input class="form-input" type="text" v-model="blendFile" placeholder="C:\path\to\scene.blend" />
          <button class="btn-browse" v-if="!remoteAccess" @click="emit('browseFile', '.blend', 'blend')">···</button>
        </div>
      </div>

      <div class="form-section-title">帧范围</div>

      <div class="form-input-row">
        <div class="form-group">
          <label class="form-label">起始帧</label>
          <input class="form-input" type="number" v-model.number="startFrame" min="1" />
        </div>
        <div class="form-group">
          <label class="form-label">结束帧</label>
          <input class="form-input" type="number" v-model.number="endFrame" min="1" />
        </div>
      </div>

      <div class="form-section-title">性能</div>

      <div class="form-group">
        <label class="form-label">批次大小</label>
        <input class="form-input" type="number" v-model.number="batchSize" min="1" max="500" />
        <span class="form-hint">每批渲染的帧数，越大越省内存但启动开销更大</span>
      </div>

      <div class="form-group">
        <label class="form-label">内存阈值 (%)</label>
        <input class="form-input" type="number" v-model.number="memThreshold" min="10" max="99" />
        <span class="form-hint">系统内存超过此阈值时自动重启批次</span>
      </div>

      <div class="form-group">
        <label class="form-label">重启延迟 (秒)</label>
        <input class="form-input" type="number" v-model.number="restartDelay" min="1" max="60" />
      </div>

      <div class="form-section-title">崩溃恢复</div>

      <div class="form-group">
        <label class="form-label">连崩检测上限</label>
        <input class="form-input" type="number" v-model.number="crashLimit" min="1" max="20" />
        <span class="form-hint">Blender 在时间窗口内连续崩溃超过此次数后停止渲染</span>
      </div>

      <div class="form-group">
        <label class="form-label">连崩时间窗口 (秒)</label>
        <input class="form-input" type="number" v-model.number="crashWindow" min="10" max="3600" />
        <span class="form-hint">两次崩溃间隔超过此秒数即视为非连续崩溃，计数器归零</span>
      </div>
    </div>

    <div class="settings-actions">
      <button class="btn btn-save" @click="emit('save')">
        保存设置
      </button>
      <button class="btn btn-primary" :disabled="isRunning || !wsConnected" @click="emit('startRender')">
        开始渲染
      </button>
      <button class="btn btn-danger" :disabled="!isRunning" @click="emit('stopRender')">
        停止渲染
      </button>
    </div>
  </div>
</template>

<style scoped>
.panel-header {
  padding: 16px 20px;
  border-bottom: 1.5px solid var(--border);
  font-weight: 700;
  color: var(--text-title);
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.settings-panel {
  background: var(--card-bg);
  border-radius: var(--radius);
  border: 1.5px solid var(--border);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
}

.settings-body {
  flex: 1;
  padding: 20px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 0.8rem;
  font-weight: 600;
  color: var(--text-title);
}

.form-hint {
  font-size: 0.7rem;
  color: var(--text-muted);
}

.form-input,
.form-select {
  width: 100%;
  padding: 8px 12px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  font-size: 0.85rem;
  font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
  color: var(--text-title);
  background: var(--card-bg);
  transition: border-color var(--transition), box-shadow var(--transition);
  outline: none;
}

.form-input:focus,
.form-select:focus {
  border-color: var(--brand);
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.15);
}

.form-input::placeholder {
  color: var(--text-muted);
  font-family: 'Inter', sans-serif;
}

.form-input-row {
  display: flex;
  gap: 12px;
}

.form-input-row .form-group {
  flex: 1;
}

.form-section-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  padding-top: 8px;
  border-top: 1px solid #F1F5F9;
  margin-top: 4px;
}

.file-picker {
  display: flex;
  gap: 8px;
}

.file-picker .form-input {
  flex: 1;
}

.btn-browse {
  padding: 8px 16px;
  border: 1.5px solid var(--border);
  border-radius: var(--radius-sm);
  background: #F8FAFC;
  color: var(--text-body);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  transition: all var(--transition);
  white-space: nowrap;
}

.btn-browse:hover {
  background: #F1F5F9;
  border-color: var(--text-muted);
}

.settings-actions {
  padding: 16px 20px;
  border-top: 1.5px solid var(--border);
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.btn {
  padding: 8px 20px;
  border-radius: 6px;
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  border: none;
  transition: all var(--transition);
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: 'Inter', sans-serif;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--brand);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--brand-hover);
}

.btn-save {
  background: white;
  color: var(--text-title);
  border: 1.5px solid var(--border);
}

.btn-save:hover:not(:disabled) {
  background: #F8FAFC;
  border-color: var(--brand);
  color: var(--brand);
}

.btn-danger {
  background: white;
  color: var(--danger);
  border: 1.5px solid var(--border);
}

.btn-danger:hover:not(:disabled) {
  background: #FEF2F2;
  border-color: var(--danger);
}

.settings-body::-webkit-scrollbar {
  width: 6px;
}

.settings-body::-webkit-scrollbar-track {
  background: transparent;
}

.settings-body::-webkit-scrollbar-thumb {
  background: var(--border);
  border-radius: 3px;
}

@media (max-width: 768px) {
  .settings-body {
    padding: 14px;
  }
  .settings-actions {
    flex-direction: column;
    padding: 12px 14px;
    gap: 8px;
  }
  .settings-actions .btn {
    justify-content: center;
  }
  .panel-header {
    padding: 12px 14px;
  }
}
</style>
