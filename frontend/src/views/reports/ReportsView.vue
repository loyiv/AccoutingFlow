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
        <select v-model="app.selectedPeriodId">
          <option v-for="p in app.periods" :key="p.id" :value="p.id">
            {{ p.year }}-{{ String(p.month).padStart(2, '0') }}（{{ p.status }}）
          </option>
        </select>
      </div>
      <div class="field">
        <label>口径</label>
        <select v-model="basis">
          <option value="LEGAL">法定</option>
          <option value="MGMT">管理</option>
        </select>
      </div>
      <button class="btn primary" :disabled="loadingGen" @click="generate">生成报表</button>
      <button class="btn" @click="reloadSnapshots">刷新快照</button>
    </div>

    <ExampleCard title="操作示例（企业日常）：生成并查看当期报表" subtitle="建议先完成：投入资本(seed-1)过账、销售(SO)过账、采购(PO)或报销(EC)过账。">
      <ol class="ol">
        <li>选择账簿与期间，点击“生成报表”。</li>
        <li>在下方快照列表点击“查看”，进入报表快照页。</li>
        <li>在快照页点击“下钻”，可定位到科目、凭证与分录明细。</li>
      </ol>
    </ExampleCard>

    <div v-if="latestSummary" class="card summary">
      <div class="summary-head">
        <b>本次生成结果</b>
        <span class="muted">snapshot={{ latestSummary.id }} · {{ latestSummary.period }} · {{ latestSummary.basis }}</span>
        <div class="spacer"></div>
        <RouterLink class="btn" :to="`/reports/${latestSummary.id}`">查看报表</RouterLink>
      </div>
      <div class="summary-grid">
        <div class="kpi">
          <div class="k">资产合计</div>
          <div class="v">{{ latestSummary.assets }}</div>
        </div>
        <div class="kpi">
          <div class="k">负债与权益合计</div>
          <div class="v">{{ latestSummary.liabEquity }}</div>
        </div>
        <div class="kpi">
          <div class="k">净利润</div>
          <div class="v">{{ latestSummary.netProfit }}</div>
        </div>
        <div class="kpi" :class="{ ok: latestSummary.bsOk, bad: !latestSummary.bsOk }">
          <div class="k">资产负债表是否平衡</div>
          <div class="v">{{ latestSummary.bsOk ? '平衡' : '不平衡' }}</div>
        </div>
      </div>
    </div>

    <h2>报表快照</h2>
    <table class="table">
      <thead>
        <tr>
          <th>生成时间</th>
          <th>期间</th>
          <th>口径</th>
          <th>状态</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in snapshots" :key="s.id">
          <td>{{ s.generated_at }}</td>
          <td>{{ periodLabel(s.period_id) }}</td>
          <td>{{ s.basis_code }}</td>
          <td>{{ s.is_stale ? 'stale' : 'ok' }}</td>
          <td>
            <RouterLink :to="`/reports/${s.id}`">查看</RouterLink>
          </td>
        </tr>
        <tr v-if="!snapshots.length">
          <td colspan="5" class="muted">暂无快照，点击“生成报表”创建</td>
        </tr>
      </tbody>
    </table>

    <div v-if="error" class="notice">提示：{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'
import { useToastStore } from '../../stores/toast'

const app = useAppStore()
const router = useRouter()
const toast = useToastStore()

const basis = ref<'LEGAL' | 'MGMT'>('LEGAL')
const snapshots = ref<any[]>([])
const error = ref('')
const loadingGen = ref(false)
const latestSnapshot = ref<any | null>(null)

function periodLabel(periodId: string) {
  const p = app.periods.find((x) => x.id === periodId)
  if (!p) return periodId
  return `${p.year}-${String(p.month).padStart(2, '0')}`
}

function fmtMoney(v: any) {
  const n = Number(v)
  const x = Number.isFinite(n) ? n : Number(String(v || 0))
  return `¥${(x || 0).toFixed(2)}`
}

const latestSummary = computed(() => {
  const s = latestSnapshot.value
  if (!s?.id) return null
  const checks = s?.result?.checks || s?.checks || {}
  const assets = checks?.BS_ASSETS_TOTAL ?? null
  const le = checks?.BS_LIAB_EQUITY_TOTAL ?? null
  const bsOk = !!checks?.BS_BALANCE_OK

  // 从 statements 中找净利润（后端会补一个 IS_NET_PROFIT）
  const isRows: any[] = s?.result?.statements?.IS || []
  const npRow = isRows.find((x) => x?.code === 'IS_NET_PROFIT')
  const netProfit = npRow?.amount ?? null

  const period = periodLabel(String(s.period_id || app.selectedPeriodId || ''))
  const basisText = String(s.basis_code || basis.value)

  return {
    id: String(s.id),
    period,
    basis: basisText,
    assets: fmtMoney(assets),
    liabEquity: fmtMoney(le),
    netProfit: fmtMoney(netProfit),
    bsOk,
  }
})

async function reloadSnapshots() {
  error.value = ''
  try {
    if (!app.selectedBookId) return
    snapshots.value = await api.listSnapshots(app.selectedBookId)
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function generate() {
  error.value = ''
  loadingGen.value = true
  try {
    if (!app.selectedBookId || !app.selectedPeriodId) throw new Error('请先选择账簿与期间')
    const res = await api.generateReport(app.selectedBookId, app.selectedPeriodId, basis.value)
    // 立即加载本次生成的快照，给用户看到关键指标（就算没点“查看”也能看到结果）
    try {
      latestSnapshot.value = await api.getSnapshot(res.snapshot_id)
    } catch {
      // 不阻塞主流程
    }
    await reloadSnapshots()
    toast.success('报表生成成功', { scale: 3 })
    // 生成后直接进入“图表视图”，让用户立刻看到可视化结果
    await router.push({ path: `/reports/${res.snapshot_id}`, query: { tab: 'charts' } })
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    loadingGen.value = false
  }
}

async function onBookChange() {
  await app.reloadPeriods()
  await reloadSnapshots()
}

onMounted(async () => {
  if (!app.books.length) await app.init()
  await reloadSnapshots()
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
.btn.primary {
  background: #111827;
  color: white;
  border-color: #111827;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
.card.summary {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 14px;
  padding: 12px;
  box-shadow: var(--shadow-sm);
  margin: 10px 0 14px;
}
.summary-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.spacer {
  flex: 1;
}
.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.kpi {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 10px;
  background: #f8fafc;
}
.kpi .k {
  font-size: 12px;
  color: #64748b;
  margin-bottom: 6px;
}
.kpi .v {
  font-weight: 800;
  font-size: 16px;
  color: #0f172a;
}
.kpi.ok {
  border-color: rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.08);
}
.kpi.bad {
  border-color: rgba(239, 68, 68, 0.35);
  background: rgba(239, 68, 68, 0.06);
}
@media (max-width: 980px) {
  .summary-grid {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 520px) {
  .summary-grid {
    grid-template-columns: 1fr;
  }
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


