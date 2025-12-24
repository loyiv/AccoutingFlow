<template>
  <div class="page">
    <div class="top">
      <div>
        <h2>报表快照</h2>
        <p class="muted">
          snapshot={{ id }} · 期间={{ snapshot?.period_id }} · 口径={{ snapshot?.basis_code }} · stale={{ snapshot?.is_stale }}
        </p>
      </div>
      <div class="actions">
        <button class="btn" @click="tab = tab === 'table' ? 'charts' : 'table'">{{ tab === 'table' ? '图表' : '表格' }}</button>
        <button class="btn" @click="load">刷新</button>
        <button class="btn" @click="download('excel')">导出 Excel</button>
        <button class="btn" @click="download('pdf')">导出 PDF</button>
      </div>
    </div>

    <ExampleCard title="操作示例（企业日常）：报表下钻到凭证" subtitle="目标：从报表 → 科目 → 凭证 → 分录，验证业务已入账。">
      <ol class="ol">
        <li>在表格页点击某一行的“下钻”。</li>
        <li>先选科目，再进入凭证列表，最后点“查看详情”看分录。</li>
        <li>你可以用示例：SO-SEED-1/PO-SEED-1/EC-SEED-1 过账后的凭证来验证。</li>
      </ol>
    </ExampleCard>

    <div v-if="summary" class="card summary">
      <div class="summary-grid">
        <div class="kpi">
          <div class="k">资产合计</div>
          <div class="v">{{ summary.assets }}</div>
        </div>
        <div class="kpi">
          <div class="k">负债与权益合计</div>
          <div class="v">{{ summary.liabEquity }}</div>
        </div>
        <div class="kpi">
          <div class="k">净利润</div>
          <div class="v">{{ summary.netProfit }}</div>
        </div>
        <div class="kpi" :class="{ ok: summary.bsOk, bad: !summary.bsOk }">
          <div class="k">资产负债表是否平衡</div>
          <div class="v">{{ summary.bsOk ? '平衡' : '不平衡' }}</div>
        </div>
      </div>
    </div>

    <div v-if="snapshot && tab === 'charts'" class="grid">
      <section class="card">
        <h3>资产负债表（可视化）</h3>
        <div class="chart-grid">
          <EChart v-if="bsTotalOption" :option="bsTotalOption" :height="320" />
          <EChart v-if="bsAssetsBreakdownOption" :option="bsAssetsBreakdownOption" :height="320" />
          <EChart v-if="bsLiabEqBreakdownOption" :option="bsLiabEqBreakdownOption" :height="320" />
        </div>
        <div v-if="chartError" class="notice">提示：{{ chartError }}</div>
      </section>

      <section class="card">
        <h3>利润表（可视化）</h3>
        <div class="chart-grid">
          <EChart v-if="isMainOption" :option="isMainOption" :height="320" />
          <EChart v-if="isExpenseBreakdownOption" :option="isExpenseBreakdownOption" :height="320" />
          <EChart v-if="isRevenueBreakdownOption" :option="isRevenueBreakdownOption" :height="320" />
        </div>
      </section>
    </div>

    <div v-if="snapshot && tab === 'table'" class="grid">
      <StatementTable title="资产负债表" type="BS" :items="snapshot.result?.statements?.BS || []" @drill="onDrill" />
      <StatementTable title="利润表" type="IS" :items="snapshot.result?.statements?.IS || []" @drill="onDrill" />
      <StatementTable title="现金流量表（最小口径）" type="CF" :items="snapshot.result?.statements?.CF || []" @drill="onDrill" />
    </div>

    <div v-if="drill" class="modal">
      <div class="modal-card">
        <div class="modal-head">
          <b>下钻：{{ drill.statement_type }} / {{ drill.item_code }}</b>
          <button class="btn" @click="drill = null">关闭</button>
        </div>
        <div v-if="drillStep === 'accounts'">
          <table class="table">
            <thead>
              <tr>
                <th>科目</th>
                <th>金额</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in drill.accounts" :key="a.account_id">
                <td>{{ a.code }} {{ a.name }}</td>
                <td>{{ a.amount }}</td>
                <td><a href="#" @click.prevent="openRegister(a.account_id)">查看凭证</a></td>
              </tr>
              <tr v-if="!drill.accounts?.length">
                <td colspan="3" class="muted">该行暂无映射（或为公式项），可尝试点击明细项行下钻</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-else-if="drillStep === 'register'">
          <div class="subhead">
            <button class="btn" @click="drillStep = 'accounts'">← 返回科目</button>
            <span class="muted">account={{ selectedAccountId }}</span>
          </div>
          <table class="table">
            <thead>
              <tr>
                <th>凭证号</th>
                <th>日期</th>
                <th>摘要</th>
                <th>金额</th>
                <th>来源</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="it in register?.items || []" :key="it.txn_id + ':' + it.split_line_no">
                <td>{{ it.txn_num }}</td>
                <td>{{ it.txn_date }}</td>
                <td>{{ it.description }}</td>
                <td>{{ it.value }}</td>
                <td>{{ sourceText(it) }}</td>
                <td><a href="#" @click.prevent="openTxn(it.txn_id)">查看详情</a></td>
              </tr>
              <tr v-if="!(register?.items || []).length">
                <td colspan="6" class="muted">暂无明细</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-else-if="drillStep === 'txn'">
          <div class="subhead">
            <button class="btn" @click="drillStep = 'register'">← 返回凭证</button>
            <span class="muted">txn={{ txn?.num }}</span>
          </div>
          <div v-if="txn" class="card-inner">
            <div class="row"><b>凭证号</b>：{{ txn.num }}</div>
            <div class="row"><b>日期</b>：{{ txn.txn_date }}</div>
            <div class="row"><b>摘要</b>：{{ txn.description }}</div>
            <div class="row"><b>来源</b>：{{ sourceText(txn) }}</div>
            <div v-if="txn.source_doc" class="row">
              <b>来源单据</b>：{{ txn.source_doc.doc_type }} {{ txn.source_doc.doc_no }}（{{ txn.source_doc.status }}）
            </div>

            <h4>分录</h4>
            <table class="table">
              <thead>
                <tr>
                  <th>行</th>
                  <th>科目</th>
                  <th>金额</th>
                  <th>备注</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="s in txn.splits" :key="s.line_no">
                  <td>{{ s.line_no }}</td>
                  <td>{{ s.account_code }} {{ s.account_name }}</td>
                  <td>{{ s.value }}</td>
                  <td>{{ s.memo }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <div v-if="error" class="notice">提示：{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../services/api'
import EChart from '../../components/EChart.vue'
import ExampleCard from '../../components/ExampleCard.vue'
import { formatSourceDisplay } from '../../utils/sourceDisplay'

const route = useRoute()
const id = computed(() => String(route.params.id))

const snapshot = ref<any | null>(null)
const drill = ref<any | null>(null)
const drillStep = ref<'accounts' | 'register' | 'txn'>('accounts')
const selectedAccountId = ref('')
const register = ref<any | null>(null)

function sourceText(x: any) {
  return formatSourceDisplay({
    source_type: x?.source_type,
    source_id: x?.source_id,
    description: x?.description,
    // 报表交易详情会带 source_doc（若有）
    source_doc: x?.source_doc || null,
  })
}
const txn = ref<any | null>(null)
const error = ref('')
// 默认展示图表（更直观）；也支持 URL query：?tab=table
const tab = ref<'table' | 'charts'>(String(route.query.tab || 'charts') === 'table' ? 'table' : 'charts')

const chartError = ref('')
const chartData = ref<any>({
  bs_assets_accounts: null,
  bs_liab_accounts: null,
  bs_eq_accounts: null,
  is_rev_accounts: null,
  is_exp_accounts: null,
})

const StatementTable = {
  props: ['title', 'type', 'items'],
  emits: ['drill'],
  template: `
    <section class="card">
      <h3>{{ title }}</h3>
      <table class="table">
        <thead>
          <tr><th>项目</th><th>金额</th><th>操作</th></tr>
        </thead>
        <tbody>
          <tr v-for="it in items" :key="it.code">
            <td>{{ it.code }} {{ it.name }}</td>
            <td>{{ it.amount }}</td>
            <td><a href="#" @click.prevent="$emit('drill', type, it.code)">下钻</a></td>
          </tr>
          <tr v-if="!items?.length"><td colspan="3" class="muted">暂无数据</td></tr>
        </tbody>
      </table>
    </section>
  `,
}

async function load() {
  error.value = ''
  drill.value = null
  try {
    snapshot.value = await api.getSnapshot(id.value)
    chartError.value = ''
    // 只有在图表页才加载分解数据（更省请求）；基础图表直接来自 snapshot.result
    if (tab.value === 'charts') await loadChartData()
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

function fmtMoney(v: any) {
  const n = Number(v)
  const x = Number.isFinite(n) ? n : Number(String(v || 0))
  return `¥${(x || 0).toFixed(2)}`
}

const summary = computed(() => {
  const s = snapshot.value
  if (!s?.result) return null
  const checks = s.result?.checks || {}
  const assets = checks?.BS_ASSETS_TOTAL ?? null
  const le = checks?.BS_LIAB_EQUITY_TOTAL ?? null
  const bsOk = !!checks?.BS_BALANCE_OK
  const isRows: any[] = s?.result?.statements?.IS || []
  const npRow = isRows.find((x) => x?.code === 'IS_NET_PROFIT')
  const netProfit = npRow?.amount ?? null
  return {
    assets: fmtMoney(assets),
    liabEquity: fmtMoney(le),
    netProfit: fmtMoney(netProfit),
    bsOk,
  }
})

function toNum(v: any): number {
  const n = Number(v)
  if (Number.isFinite(n)) return n
  const s = String(v || '').trim()
  const m = s.match(/-?\d+(\.\d+)?/)
  return m ? Number(m[0]) : 0
}

function topNForPie(rows: any[], n = 8) {
  const sorted = [...rows].sort((a, b) => Math.abs(toNum(b.amount)) - Math.abs(toNum(a.amount)))
  const top = sorted.slice(0, n)
  const rest = sorted.slice(n)
  const restSum = rest.reduce((acc, x) => acc + toNum(x.amount), 0)
  const data = top.map((x) => ({ name: `${x.code} ${x.name}`, value: toNum(x.amount) }))
  if (rest.length) data.push({ name: '其他', value: restSum })
  return data.filter((x) => x.value !== 0)
}

function pieOption(title: string, data: Array<{ name: string; value: number }>) {
  return {
    title: { text: title, left: 'center', textStyle: { fontSize: 12 } },
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['35%', '70%'],
        avoidLabelOverlap: true,
        label: { formatter: '{b}\n{d}%' },
        data,
      },
    ],
  }
}

function barOption(title: string, labels: string[], values: number[]) {
  return {
    title: { text: title, left: 'center', textStyle: { fontSize: 12 } },
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 50, bottom: 40 },
    xAxis: { type: 'category', data: labels },
    yAxis: { type: 'value' },
    series: [{ type: 'bar', data: values, itemStyle: { color: '#2563eb' } }],
  }
}

async function loadChartData() {
  if (!snapshot.value) return
  chartError.value = ''
  const sid = id.value
  const reqs = [
    { key: 'bs_assets_accounts', p: api.drilldown(sid, 'BS', 'BS_ASSETS') },
    { key: 'bs_liab_accounts', p: api.drilldown(sid, 'BS', 'BS_LIABILITIES') },
    { key: 'bs_eq_accounts', p: api.drilldown(sid, 'BS', 'BS_EQUITY') },
    { key: 'is_rev_accounts', p: api.drilldown(sid, 'IS', 'IS_REVENUE') },
    { key: 'is_exp_accounts', p: api.drilldown(sid, 'IS', 'IS_EXPENSE') },
  ] as const

  // 容错：任意一个分解接口失败，都不影响基础图表展示；也不再把 404 文案展示给用户
  const settled = await Promise.allSettled(reqs.map((x) => x.p))
  let anyRejected = false
  for (let i = 0; i < settled.length; i++) {
    const r = settled[i]
    const k = reqs[i].key
    if (r.status === 'fulfilled') {
      ;(chartData.value as any)[k] = (r.value as any)?.accounts || []
    } else {
      anyRejected = true
      ;(chartData.value as any)[k] = []
      // 调试信息仅输出控制台
      console.error('[Report][charts]', { key: k, error: r.reason })
    }
  }
  if (anyRejected) {
    chartError.value = '科目分解图暂不可用（不影响查看总览图与表格下钻）。'
  }
}

// 若用户从列表页带 ?tab=charts 进入，或在页面切换 tab，自动加载图表分解数据
watch(
  () => String(route.query.tab || ''),
  (v) => {
    tab.value = v === 'table' ? 'table' : 'charts'
  },
)
watch(
  () => tab.value,
  (v) => {
    if (v === 'charts' && snapshot.value) void loadChartData()
  },
)

const bsTotals = computed(() => {
  const items = snapshot.value?.result?.statements?.BS || []
  const byCode = Object.fromEntries(items.map((x: any) => [x.code, x]))
  return {
    assets: toNum(byCode.BS_ASSETS?.amount),
    liab: toNum(byCode.BS_LIABILITIES?.amount),
    eq: toNum(byCode.BS_EQUITY?.amount),
  }
})

const isTotals = computed(() => {
  const items = snapshot.value?.result?.statements?.IS || []
  const byCode = Object.fromEntries(items.map((x: any) => [x.code, x]))
  const rev = toNum(byCode.IS_REVENUE?.amount)
  const exp = toNum(byCode.IS_EXPENSE?.amount)
  const profit = toNum(byCode.IS_NET_PROFIT?.amount || rev - exp)
  return { rev, exp, profit }
})

const bsTotalOption = computed(() => {
  if (!snapshot.value) return null
  const d = [
    { name: '资产', value: bsTotals.value.assets },
    { name: '负债', value: bsTotals.value.liab },
    { name: '所有者权益', value: bsTotals.value.eq },
  ].filter((x) => x.value !== 0)
  return d.length ? pieOption('资产/负债/权益构成', d) : null
})

const bsAssetsBreakdownOption = computed(() => {
  const rows = chartData.value.bs_assets_accounts || []
  const data = topNForPie(rows, 8)
  return data.length ? pieOption('资产（按科目分解）', data) : null
})

const bsLiabEqBreakdownOption = computed(() => {
  const liab = topNForPie(chartData.value.bs_liab_accounts || [], 6)
  const eq = topNForPie(chartData.value.bs_eq_accounts || [], 6)
  const data = [
    ...liab.map((x) => ({ name: `负债: ${x.name}`, value: x.value })),
    ...eq.map((x) => ({ name: `权益: ${x.name}`, value: x.value })),
  ].filter((x) => x.value !== 0)
  return data.length ? pieOption('负债+权益（按科目分解）', data) : null
})

const isMainOption = computed(() => {
  if (!snapshot.value) return null
  return barOption('收入/费用/净利润', ['收入', '费用', '净利润'], [isTotals.value.rev, isTotals.value.exp, isTotals.value.profit])
})

const isExpenseBreakdownOption = computed(() => {
  const data = topNForPie(chartData.value.is_exp_accounts || [], 10)
  return data.length ? pieOption('费用（按科目分解）', data) : null
})

const isRevenueBreakdownOption = computed(() => {
  const data = topNForPie(chartData.value.is_rev_accounts || [], 10)
  return data.length ? pieOption('收入（按科目分解）', data) : null
})

async function onDrill(statementType: string, itemCode: string) {
  error.value = ''
  try {
    drill.value = await api.drilldown(id.value, statementType, itemCode)
    drillStep.value = 'accounts'
    selectedAccountId.value = ''
    register.value = null
    txn.value = null
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function openRegister(accountId: string) {
  if (!drill.value) return
  error.value = ''
  try {
    selectedAccountId.value = accountId
    register.value = await api.drilldownRegister(id.value, drill.value.statement_type, drill.value.item_code, accountId, false)
    drillStep.value = 'register'
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function openTxn(txnId: string) {
  error.value = ''
  try {
    txn.value = await api.getTransaction(txnId)
    drillStep.value = 'txn'
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function download(format: 'pdf' | 'excel') {
  error.value = ''
  try {
    const blob = await api.exportReport(id.value, format)
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `report-${id.value}.${format === 'excel' ? 'xlsx' : 'pdf'}`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

onMounted(async () => {
  await load()
})
</script>

<style scoped>
.card.summary {
  border: 1px solid #e5e7eb;
  background: #fff;
  border-radius: 14px;
  padding: 12px;
  box-shadow: var(--shadow-sm);
  margin: 10px 0 14px;
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
.top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
  margin-bottom: 12px;
}
.actions {
  display: flex;
  gap: 8px;
}
.btn {
  border: 1px solid #ddd;
  background: white;
  padding: 7px 10px;
  border-radius: 10px;
  cursor: pointer;
}
.grid {
  display: grid;
  gap: 12px;
}
.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 12px;
}
@media (max-width: 980px) {
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
.card {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
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
  font-size: 12px;
}
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: grid;
  place-items: center;
  padding: 16px;
}
.modal-card {
  width: min(900px, 96vw);
  background: white;
  border-radius: 12px;
  padding: 12px;
}
.modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.subhead {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}
.card-inner {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 10px;
}
.row {
  margin: 6px 0;
  font-size: 14px;
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


