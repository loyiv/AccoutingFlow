<template>
  <section class="card">
    <div class="head">
      <div class="left">
        <div class="title">{{ title }}</div>
        <div v-if="subtitle" class="sub">{{ subtitle }}</div>
      </div>
      <div class="actions">
        <slot name="actions" />
      </div>
    </div>
    <div class="body">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>

<style scoped>
.card {
  border: 1px dashed var(--primary-200);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.92), rgba(248, 250, 252, 0.92));
  border-radius: 14px;
  padding: 12px;
  margin: 10px 0 14px;
  box-shadow: var(--shadow-sm);
}
.head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}
.title {
  font-weight: 900;
  color: var(--primary-900);
  font-size: 14px;
}
.sub {
  margin-top: 4px;
  color: var(--muted);
  font-size: 12px;
}
.body {
  margin-top: 8px;
  color: var(--text);
  font-size: 13px;
}
</style>


