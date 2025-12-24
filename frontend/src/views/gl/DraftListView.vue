<template>
  <div class="page">
    <div class="toolbar">
      <div class="field">
        <label>账簿</label>
        <select v-model="app.selectedBookId" @change="onBookChange">
          <option v-for="b in app.books" :key="b.id" :value="b.id">{{ b.name }}</option>
        </select>
      </div>
      <div class="field">
        <label>期间</label>
        <select v-model="app.selectedPeriodId" @change="reload">
          <option v-for="p in app.periods" :key="p.id" :value="p.id">
            {{ p.year }}-{{ String(p.month).padStart(2, '0') }}（{{ p.status }}）
          </option>
        </select>
      </div>
      <button class="btn" @click="reload">刷新</button>
    </div>

    <h2>待过账/待审核草稿</h2>

    <ExampleCard title="操作示例（企业日常）：从草稿到入账" subtitle="建议用系统预置示例：seed-1（投入资本）、EC-SEED-1（差旅报销）、PO-SEED-1（采购办公用品）、SO-SEED-1（销售咨询服务）。">
      <ol class="ol">
        <li>在下表找到一条草稿，点击“打开”。</li>
        <li>进入草稿页后：先点“审批”，再点“过账”（系统会自动先做预校验）。</li>
        <li>过账成功后，到“科目与寄存器”或“报表”验证结果。</li>
      </ol>
    </ExampleCard>

    <table class="table">
      <thead>
        <tr>
          <th>来源</th>
          <th>摘要</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="d in drafts" :key="d.id">
          <td>{{ sourceText(d) }}</td>
          <td>{{ d.description }}</td>
          <td>{{ d.status }}</td>
          <td><RouterLink :to="`/gl/drafts/${d.id}`">打开</RouterLink></td>
        </tr>
        <tr v-if="!drafts.length">
          <td colspan="4" class="muted">暂无草稿（seed 会创建 1 条示例草稿：source_id=seed-1）</td>
        </tr>
      </tbody>
    </table>

    <div v-if="error" class="notice">提示：{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'
import { formatSourceDisplay } from '../../utils/sourceDisplay'

const app = useAppStore()
const drafts = ref<any[]>([])
const error = ref('')

function sourceText(d: any) {
  return formatSourceDisplay({
    source_type: d?.source_type,
    source_id: d?.source_id,
    version: typeof d?.version === 'number' ? d.version : Number(d?.version),
    description: d?.description,
  })
}

async function reload() {
  error.value = ''
  try {
    if (!app.selectedPeriodId) return
    drafts.value = await api.listDrafts(app.selectedPeriodId)
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function onBookChange() {
  await app.reloadPeriods()
  await reload()
}

onMounted(async () => {
  if (!app.books.length) await app.init()
  await reload()
})
</script>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  align-items: end;
  margin-bottom: 12px;
}
.field {
  display: grid;
  gap: 6px;
}
select {
  border: 1px solid #ddd;
  padding: 6px 10px;
  border-radius: 10px;
}
.btn {
  border: 1px solid #ddd;
  background: white;
  padding: 7px 10px;
  border-radius: 10px;
  cursor: pointer;
}
.table {
  width: 100%;
  border-collapse: collapse;
}
.table th,
.table td {
  border-bottom: 1px solid #eee;
  padding: 10px;
  text-align: left;
  font-size: 14px;
}
.muted {
  color: #666;
}
.ol {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #0f172a;
  font-size: 13px;
}
.notice {
  margin-top: 12px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #111827;
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
}
</style>


