import { ref, nextTick, reactive } from 'vue'

export interface TerminalLine {
  id: number
  time: string
  text: string
  type: string
}

let nextLineId = 0

export function useTerminal() {
  const terminalLines = ref<TerminalLine[]>([])
  const errorLines = ref<TerminalLine[]>([])
  const frameLineMap = reactive(new Map<number, number>())

  function nowStr() {
    return new Date().toLocaleTimeString('zh-CN', { hour12: false })
  }

  function writeTerminal(message: string, type = '') {
    terminalLines.value.push({ id: nextLineId++, time: nowStr(), text: message, type })
    trimTerminal()
  }

  function writeError(message: string) {
    errorLines.value.push({ id: nextLineId++, time: nowStr(), text: message, type: 'error' })
    if (errorLines.value.length > 200) errorLines.value = errorLines.value.slice(-200)
  }

  function updateProgressLine(frame: number, sampleCurr: number, sampleTotal: number | null, elapsed: number) {
    const total = sampleTotal ?? '?'
    const text = `Frame ${frame}  采样: ${sampleCurr}/${total} 单帧用时: ${formatElapsed(elapsed)}`

    const idx = frameLineMap.get(frame)
    if (idx !== undefined) {
      const line = terminalLines.value[idx]
      if (line) {
        line.time = nowStr()
        line.text = text
        return
      }
    }
    terminalLines.value.push({ id: nextLineId++, time: nowStr(), text, type: 'sample' })
    frameLineMap.set(frame, terminalLines.value.length - 1)
    trimTerminal()
  }

  function finalizeProgressLine(frame: number) {
    const idx = frameLineMap.get(frame)
    if (idx !== undefined) {
      const line = terminalLines.value[idx]
      if (line) {
        line.time = nowStr()
        line.text += '  ✓'
        line.type = 'ok'
      }
      frameLineMap.delete(frame)
    }
  }

  function clearConsole() {
    terminalLines.value = []
    errorLines.value = []
    frameLineMap.clear()
  }

  function trimTerminal() {
    if (terminalLines.value.length > 500) {
      const cut = terminalLines.value.length - 500
      terminalLines.value = terminalLines.value.slice(cut)
      const shifted: [number, number][] = []
      for (const [frame, oldIdx] of frameLineMap) {
        const newIdx = oldIdx - cut
        if (newIdx >= 0) shifted.push([frame, newIdx])
      }
      frameLineMap.clear()
      for (const [frame, idx] of shifted) frameLineMap.set(frame, idx)
    }
  }

  function formatElapsed(seconds: number): string {
    const h = Math.floor(seconds / 3600)
    const m = Math.floor((seconds % 3600) / 60)
    const s = Math.floor(seconds % 60)
    return `${pad(h)}:${pad(m)}:${pad(s)}`
  }

  function pad(n: number): string {
    return n.toString().padStart(2, '0')
  }

  return {
    terminalLines,
    errorLines,
    frameLineMap,
    writeTerminal,
    writeError,
    updateProgressLine,
    finalizeProgressLine,
    clearConsole,
    formatElapsed,
  }
}
