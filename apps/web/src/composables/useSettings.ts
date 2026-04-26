import { ref } from 'vue'

const API_BASE = import.meta.env.VITE_API_BASE || ''

export function useSettings() {
  const blenderPath = ref('')
  const blendFile = ref('')
  const startFrame = ref(1)
  const endFrame = ref(250)
  const batchSize = ref(50)
  const memThreshold = ref(85)
  const restartDelay = ref(5)
  const crashLimit = ref(3)      // max rapid crashes before giving up
  const crashWindow = ref(60)    // seconds — crashes outside this window reset counter

  async function loadSettings() {
    try {
      const res = await fetch(`${API_BASE}/api/settings`)
      if (!res.ok) return
      const data = await res.json()
      if (data.blender) blenderPath.value = data.blender
      if (data.blend) blendFile.value = data.blend
      if (data.start) startFrame.value = data.start
      if (data.end) endFrame.value = data.end
      if (data.batch) batchSize.value = data.batch
      if (data.memory_threshold) memThreshold.value = data.memory_threshold
      if (data.restart_delay) restartDelay.value = data.restart_delay
      if (data.rapid_crash_limit != null) crashLimit.value = data.rapid_crash_limit
      if (data.rapid_crash_window != null) crashWindow.value = data.rapid_crash_window
    } catch {
      console.warn('Failed to load settings from backend')
    }
  }

  async function saveSettingsToBackend() {
    const body = {
      blender: blenderPath.value,
      blend: blendFile.value,
      start: startFrame.value,
      end: endFrame.value,
      batch: batchSize.value,
      memory_threshold: memThreshold.value,
      restart_delay: restartDelay.value,
      rapid_crash_limit: crashLimit.value,
      rapid_crash_window: crashWindow.value,
    }
    try {
      await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
    } catch {
      // non-critical
    }
  }

  async function browseFile(filter: string, target: 'blender' | 'blend') {
    try {
      const res = await fetch(
        `${API_BASE}/api/browse-file?filter=${encodeURIComponent(filter)}`
      )
      if (!res.ok) return
      const data = await res.json()
      if (data.path) {
        if (target === 'blender') blenderPath.value = data.path
        else blendFile.value = data.path
      }
    } catch {
      console.warn('File dialog failed')
    }
  }

  function getRenderBody() {
    return {
      blender: blenderPath.value,
      blend: blendFile.value,
      start: startFrame.value,
      end: endFrame.value,
      batch: batchSize.value,
      memory_threshold: memThreshold.value,
      restart_delay: restartDelay.value,
      rapid_crash_limit: crashLimit.value,
      rapid_crash_window: crashWindow.value,
    }
  }

  function validate(): string[] {
    const errors: string[] = []
    if (!blenderPath.value) errors.push('Blender 路径不能为空')
    if (!blendFile.value) errors.push('工程文件不能为空')
    if (!Number.isInteger(startFrame.value) || startFrame.value < 0) errors.push('起始帧必须为 >= 0 的整数')
    if (!Number.isInteger(endFrame.value) || endFrame.value < 0) errors.push('结束帧必须为 >= 0 的整数')
    if (startFrame.value > endFrame.value) errors.push('起始帧不能大于结束帧')
    if (batchSize.value < 1) errors.push('批次大小不能小于 1')
    return errors
  }

  return {
    blenderPath, blendFile, startFrame, endFrame, batchSize, memThreshold, restartDelay,
    crashLimit, crashWindow,
    loadSettings, saveSettingsToBackend, browseFile, getRenderBody, validate,
  }
}
