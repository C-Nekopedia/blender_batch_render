<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'

export interface PreviewFile {
  filename: string
  frame: number
  size: number
  mtime: number
}

const props = defineProps<{
  files: PreviewFile[]
  outputDir: string | null
  isRunning: boolean
}>()

const PAGE_SIZE = 20
const COLUMNS = 5

const currentPage = ref(1)
const lightboxIndex = ref<number | null>(null)

const totalPages = computed(() => Math.max(1, Math.ceil(props.files.length / PAGE_SIZE)))

const pageFiles = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return props.files.slice(start, start + PAGE_SIZE)
})

const lightboxFile = computed(() => {
  if (lightboxIndex.value === null) return null
  return props.files[lightboxIndex.value] ?? null
})

function imageUrl(filename: string, thumb = false): string {
  const qs = `path=${encodeURIComponent(filename)}`
  return thumb ? `/api/preview-file?${qs}&thumb=true` : `/api/preview-file?${qs}`
}

function formatSize(bytes: number): string {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function openLightbox(index: number) {
  lightboxIndex.value = index
}

function closeLightbox() {
  lightboxIndex.value = null
}

function prevImage() {
  if (lightboxIndex.value === null) return
  if (lightboxIndex.value > 0) lightboxIndex.value--
  else lightboxIndex.value = props.files.length - 1
}

function nextImage() {
  if (lightboxIndex.value === null) return
  if (lightboxIndex.value < props.files.length - 1) lightboxIndex.value++
  else lightboxIndex.value = 0
}

function prevPage() {
  if (currentPage.value > 1) currentPage.value--
}

function nextPage() {
  if (currentPage.value < totalPages.value) currentPage.value++
}

// Reset page when files change (new render started)
const prevLen = ref(0)
if (props.files.length === 0 && prevLen.value > 0) {
  currentPage.value = 1
}
prevLen.value = props.files.length

// Keyboard navigation for lightbox
function onKeydown(e: KeyboardEvent) {
  if (lightboxIndex.value === null) return
  if (e.key === 'Escape') closeLightbox()
  if (e.key === 'ArrowLeft') prevImage()
  if (e.key === 'ArrowRight') nextImage()
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<template>
  <div class="preview-panel">
    <!-- Header -->
    <div class="preview-header">
      <span>Preview</span>
      <span v-if="outputDir" class="output-path" :title="outputDir">{{ outputDir }}</span>
      <span class="file-count">{{ files.length }} frame{{ files.length !== 1 ? 's' : '' }}</span>
    </div>

    <!-- Empty state -->
    <div v-if="files.length === 0" class="empty-state">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/>
        <path d="m21 15-5-5L5 21"/>
      </svg>
      <span>{{ isRunning ? 'Waiting for first frame...' : 'No images — start a render first' }}</span>
    </div>

    <!-- Grid -->
    <div v-else class="preview-grid">
      <div
        v-for="(file, i) in pageFiles"
        :key="file.filename"
        class="image-card"
        @click="openLightbox((currentPage - 1) * PAGE_SIZE + i)"
      >
        <div class="image-wrapper">
          <img
            :src="imageUrl(file.filename, true)"
            :alt="`Frame ${file.frame}`"
            loading="lazy"
          />
        </div>
        <div class="image-info">
          <span class="frame-label">Frame {{ file.frame }}</span>
          <span class="frame-size">{{ formatSize(file.size) }}</span>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="files.length > PAGE_SIZE" class="pagination">
      <button class="page-btn" :disabled="currentPage === 1" @click="prevPage">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="m15 18-6-6 6-6"/>
        </svg>
        Prev
      </button>
      <span class="page-info">{{ currentPage }} / {{ totalPages }}</span>
      <button class="page-btn" :disabled="currentPage === totalPages" @click="nextPage">
        Next
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="m9 18 6-6-6-6"/>
        </svg>
      </button>
    </div>

    <!-- Lightbox overlay -->
    <Teleport to="body">
      <div
        v-if="lightboxFile"
        class="lightbox-overlay"
        @click.self="closeLightbox"
      >
        <button class="lightbox-close" @click="closeLightbox" title="Close">
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
          </svg>
        </button>

        <button class="lightbox-nav lightbox-prev" @click.stop="prevImage" title="Previous">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m15 18-6-6 6-6"/>
          </svg>
        </button>

        <div class="lightbox-image-wrapper">
          <img
            :src="imageUrl(lightboxFile.filename)"
            :alt="`Frame ${lightboxFile.frame}`"
          />
        </div>

        <button class="lightbox-nav lightbox-next" @click.stop="nextImage" title="Next">
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="m9 18 6-6-6-6"/>
          </svg>
        </button>

        <div class="lightbox-footer">
          <span>{{ lightboxFile.filename }}</span>
          <span>Frame {{ lightboxFile.frame }} — {{ formatSize(lightboxFile.size) }}</span>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<style scoped>
.preview-panel {
  background: var(--card-bg);
  border-radius: var(--radius);
  border: 1.5px solid var(--border);
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  min-height: 0;
  grid-column: 1 / -1;
}

.preview-header {
  padding: 16px 20px;
  border-bottom: 1.5px solid var(--border);
  font-weight: 700;
  color: var(--text-title);
  font-size: 0.9rem;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.output-path {
  font-weight: 400;
  font-size: 0.75rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.file-count {
  font-weight: 400;
  font-size: 0.75rem;
  color: var(--text-muted);
  flex-shrink: 0;
}

/* Empty state */
.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  color: var(--text-muted);
  font-size: 0.85rem;
  padding: 40px;
}

/* Grid */
.preview-grid {
  flex: 1;
  padding: 20px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  overflow-y: auto;
  align-content: start;
}

.image-card {
  border-radius: var(--radius-sm);
  border: 1.5px solid var(--border);
  overflow: hidden;
  cursor: pointer;
  transition: border-color var(--transition), box-shadow var(--transition);
  background: #F1F5F9;
  display: flex;
  flex-direction: column;
}

.image-card:hover {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px rgba(79, 70, 229, 0.2);
}

.image-wrapper {
  aspect-ratio: 16 / 9;
  overflow: hidden;
  background: #0F172A;
  display: flex;
  align-items: center;
  justify-content: center;
}

.image-wrapper img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.image-card:hover .image-wrapper img {
  transform: scale(1.05);
}

.image-info {
  padding: 3px 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.68rem;
  color: var(--text-body);
  font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
}

.frame-label {
  font-weight: 600;
  color: var(--text-title);
}

.frame-size {
  color: var(--text-muted);
}

/* Pagination */
.pagination {
  padding: 12px 20px;
  border-top: 1.5px solid var(--border);
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  flex-shrink: 0;
}

.page-btn {
  padding: 6px 14px;
  border: 1.5px solid var(--border);
  border-radius: 6px;
  background: var(--card-bg);
  color: var(--text-body);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all var(--transition);
}

.page-btn:hover:not(:disabled) {
  background: #F1F5F9;
  border-color: var(--brand);
  color: var(--brand);
}

.page-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.page-info {
  font-size: 0.8rem;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
  user-select: none;
}

/* Lightbox */
.lightbox-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.92);
  display: flex;
  align-items: center;
  justify-content: center;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.lightbox-close {
  position: absolute;
  top: 20px;
  right: 20px;
  background: rgba(255,255,255,0.08);
  border: 1.5px solid rgba(255,255,255,0.15);
  border-radius: 8px;
  padding: 8px;
  cursor: pointer;
  color: #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition);
  z-index: 1001;
}

.lightbox-close:hover {
  background: rgba(255,255,255,0.18);
}

.lightbox-nav {
  position: absolute;
  top: 50%;
  transform: translateY(-50%);
  background: rgba(255,255,255,0.06);
  border: 1.5px solid rgba(255,255,255,0.1);
  border-radius: 12px;
  padding: 16px 8px;
  cursor: pointer;
  color: #E2E8F0;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background var(--transition);
  z-index: 1001;
}

.lightbox-nav:hover {
  background: rgba(255,255,255,0.15);
}

.lightbox-prev { left: 24px; }
.lightbox-next { right: 24px; }

.lightbox-image-wrapper {
  max-width: 85vw;
  max-height: 80vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

.lightbox-image-wrapper img {
  max-width: 85vw;
  max-height: 80vh;
  object-fit: contain;
  border-radius: 4px;
  box-shadow: 0 16px 48px rgba(0, 0, 0, 0.5);
}

.lightbox-footer {
  position: absolute;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  color: #94A3B8;
  font-size: 0.8rem;
  font-family: 'JetBrains Mono', 'Cascadia Code', 'Consolas', monospace;
  display: flex;
  gap: 24px;
  background: rgba(0,0,0,0.6);
  padding: 8px 16px;
  border-radius: 8px;
}

/* Scrollbar */
.preview-grid::-webkit-scrollbar { width: 6px; }
.preview-grid::-webkit-scrollbar-track { background: transparent; }
.preview-grid::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

/* Responsive */
@media (max-width: 1200px) {
  .preview-grid {
    grid-template-columns: repeat(4, 1fr);
  }
}

@media (max-width: 768px) {
  .preview-grid {
    grid-template-columns: repeat(2, 1fr);
    padding: 12px;
    gap: 8px;
  }
  .lightbox-nav { display: none; }
  .preview-header { padding: 12px 16px; font-size: 0.82rem; }
}
</style>
