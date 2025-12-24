<template>
  <div class="node">
    <div class="row" :class="{ selected: selected === node.id }" @click="$emit('select', node.id)">
      <span class="toggle" v-if="hasChildren" @click.stop="open = !open">{{ open ? "▾" : "▸" }}</span>
      <span class="toggle" v-else> </span>
      <span class="code">{{ node.code }}</span>
      <span class="name">{{ node.name }}</span>
      <span class="desc">{{ node.description }}</span>
      <span class="total">{{ node.total }}</span>
    </div>
    <div v-if="hasChildren" v-show="open" class="children">
      <AccountTreeNode v-for="c in node.children" :key="c.id" :node="c" :selected="selected" @select="$emit('select', $event)" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

defineOptions({ name: 'AccountTreeNode' })

type Node = {
  id: string
  parent_id: string | null
  code: string
  name: string
  description: string
  type: string
  allow_post: boolean
  is_active: boolean
  is_hidden?: boolean
  is_placeholder?: boolean
  total: string | number
  children: Node[]
}

const props = defineProps<{ node: Node; selected: string }>()
defineEmits<{ (e: 'select', id: string): void }>()

const open = ref(true)
const hasChildren = computed(() => (props.node.children?.length || 0) > 0)
</script>

<style scoped>
.row {
  display: grid;
  grid-template-columns: 18px 70px 1fr 1.2fr 90px;
  gap: 8px;
  padding: 6px 6px;
  border-radius: 8px;
  cursor: pointer;
  align-items: center;
}
.row.selected {
  background: #f2f4f7;
}
.toggle {
  color: #999;
}
.code {
  color: #111;
}
.name {
  color: #333;
}
.desc {
  color: #667085;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.total {
  text-align: right;
  font-variant-numeric: tabular-nums;
  color: #111;
}
.children {
  padding-left: 16px;
}
</style>


