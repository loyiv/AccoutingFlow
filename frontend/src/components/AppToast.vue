<template>
  <div v-if="toast.visible" class="toast-root" :style="{ '--toast-scale': String(toast.scale) }">
    <div class="toast-mask" aria-hidden="true" @click="toast.hide()" />
    <div class="toast" role="status" aria-live="polite">
      <span class="toast-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none">
          <path
            d="M20 6L9 17l-5-5"
            stroke="white"
            stroke-width="2.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </span>
      <span class="toast-text">{{ toast.text }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useToastStore } from '../stores/toast'

const toast = useToastStore()
</script>

<style scoped>
.toast-root {
  position: fixed;
  inset: 0;
  z-index: 6000;
  pointer-events: none;
}
.toast-mask {
  position: absolute;
  inset: 0;
  background: rgba(2, 6, 23, 0.08);
  pointer-events: auto;
}
.toast {
  position: absolute;
  left: 50%;
  top: 50%;
  transform: translate(-50%, -50%) scale(var(--toast-scale, 3));
  transform-origin: center;
  padding: 12px 16px;
  border-radius: 14px;
  background: #ecfdf5;
  border: 1px solid #86efac;
  color: #065f46;
  font-size: 14px;
  box-shadow: 0 18px 44px rgba(2, 6, 23, 0.22);
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 180px;
  justify-content: center;
  pointer-events: auto;
}
.toast-icon {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  background: #22c55e;
  display: grid;
  place-items: center;
  box-shadow: 0 8px 20px rgba(34, 197, 94, 0.35);
  flex: 0 0 auto;
}
.toast-text {
  font-weight: 700;
  letter-spacing: 0.2px;
}
</style>


