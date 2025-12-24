<template>
  <div class="page">
    <div class="top">
      <div>
        <h2>草稿预览</h2>
        <p class="muted">
          来源：{{ sourceText }} · 状态：{{ statusText }}
        </p>
      </div>
      <div class="actions">
        <button class="btn" @click="load">刷新</button>
        <button class="btn" @click="doPrecheck" :disabled="loadingPrecheck">预校验</button>
      <button class="btn" @click="doApprove" :disabled="!canApprove">审批</button>
      <button class="btn" @click="doReject" :disabled="!canReject">退回</button>
        <button class="btn primary" @click="doPost" :disabled="!canPost">过账</button>
      </div>
    </div>

    <ExampleCard title="操作示例（企业日常）：审批并过账" subtitle="你可以用：MANUAL/seed-1（投入资本）、EC-SEED-1（差旅报销）、PO-SEED-1（采购）、SO-SEED-1（销售）。">
      <ol class="ol">
        <li>如果状态不是“已审批”，先点击“审批”。</li>
        <li>点击“过账”即可（系统会自动预校验；不通过会给出可理解的提示）。</li>
        <li>过账后到“科目与寄存器”查看流水，或到“报表”生成并下钻验证。</li>
      </ol>
    </ExampleCard>

    <div v-if="posted" class="success">
      过账成功：凭证号 <b>{{ posted.voucher_num }}</b>
    </div>

    <h3>分录明细</h3>
    <table class="table">
      <thead>
        <tr>
          <th>行</th>
          <th>科目</th>
          <th>借方</th>
          <th>贷方</th>
          <th>备注</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="l in draft?.lines || []" :key="l.id">
          <td>{{ l.line_no }}</td>
          <td>{{ l.account_code }} {{ l.account_name }}</td>
          <td>{{ l.debit }}</td>
          <td>{{ l.credit }}</td>
          <td>{{ l.memo }}</td>
        </tr>
      </tbody>
    </table>

    <h3>预校验结果</h3>
    <div v-if="!precheck" class="muted">点击“预校验”查看校验清单</div>
    <ul v-else class="checks">
      <li v-for="c in precheck.checks" :key="c.code" :class="c.passed ? 'ok' : 'bad'">
        <b>{{ c.passed ? '通过' : '未通过' }}</b> · {{ titleOf(c.code) }}
        <div class="muted" v-if="messageOf(c)">{{ messageOf(c) }}</div>
        <ul v-if="detailsOf(c).length" class="detail-list">
          <li v-for="(t, idx) in detailsOf(c)" :key="idx">{{ t }}</li>
        </ul>
      </li>
    </ul>

    <div v-if="error" class="notice">提示：{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'
import { formatSourceDisplay } from '../../utils/sourceDisplay'
import { useToastStore } from '../../stores/toast'

const route = useRoute()
const id = computed(() => String(route.params.id))
const toast = useToastStore()

const draft = ref<any | null>(null)
const precheck = ref<any | null>(null)
const posted = ref<any | null>(null)

const sourceText = computed(() =>
  formatSourceDisplay({
    source_type: draft.value?.source_type,
    source_id: draft.value?.source_id,
    version: typeof draft.value?.version === 'number' ? draft.value.version : Number(draft.value?.version),
    description: draft.value?.description,
  }),
)
const error = ref('')
const loadingPrecheck = ref(false)
const loadingPost = ref(false)

const statusText = computed(() => {
  const s = String(draft.value?.status || '')
  const map: Record<string, string> = {
    DRAFT: '草稿',
    SUBMITTED: '已提交',
    APPROVED: '已审批',
    REJECTED: '已退回',
    POSTED: '已过账',
  }
  return map[s] || (s ? '处理中' : '-')
})

const canPost = computed(() => {
  if (!draft.value) return false
  if (loadingPost.value) return false
  if (draft.value.status !== 'APPROVED') return false
  // 允许“先点过账”，在 doPost 中会自动执行预校验并展示失败原因
  if (!precheck.value) return true
  return !!precheck.value.ok
})

const canApprove = computed(() => {
  if (!draft.value) return false
  return draft.value.status === 'DRAFT' || draft.value.status === 'SUBMITTED' || draft.value.status === 'REJECTED'
})
const canReject = computed(() => {
  if (!draft.value) return false
  return draft.value.status !== 'POSTED'
})

async function load() {
  error.value = ''
  posted.value = null
  try {
    draft.value = await api.getDraft(id.value)
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function doPrecheck() {
  error.value = ''
  loadingPrecheck.value = true
  try {
    precheck.value = await api.precheckDraft(id.value)
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    loadingPrecheck.value = false
  }
}

async function doPost() {
  error.value = ''
  try {
    if (!draft.value) return
    if (draft.value.status !== 'APPROVED') {
      error.value = '请先审批后再过账'
      return
    }

    // 过账前始终做一次预校验：避免“按钮不可用/点了没反应”的困惑，并把原因展示出来
    const pc = await api.precheckDraft(id.value)
    precheck.value = pc
    if (!pc?.ok) {
      error.value = '预校验未通过，无法过账。请根据下方提示修正后重试。'
      return
    }

    loadingPost.value = true
    posted.value = await api.postDraft(id.value)
    await load()
    toast.success(`过账成功`, { scale: 3 })
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    loadingPost.value = false
  }
}

async function doApprove() {
  error.value = ''
  try {
    await api.approveDraft(id.value)
    await load()
    toast.success(`审批成功`, { scale: 3 })
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function doReject() {
  error.value = ''
  try {
    const reason = prompt('请输入退回原因（必填）') || ''
    if (!reason.trim()) return
    await api.rejectDraft(id.value, reason.trim())
    await load()
    toast.success(`退回成功`, { scale: 3 })
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

function titleOf(code: string) {
  const map: Record<string, string> = {
    MIN_SPLITS: '分录行数量',
    BALANCE_VALUE_ZERO: '借贷平衡',
    PERIOD_OPEN: '会计期间状态',
    ACCOUNT_ALLOW_POST: '科目可记账',
    IDEMPOTENCY: '是否重复过账',
  }
  return map[String(code || '')] || '校验项'
}

function messageOf(c: any): string {
  const code = String(c?.code || '')
  const passed = !!c?.passed
  if (code === 'MIN_SPLITS') return passed ? '分录行数量满足要求。' : '分录行不足，请补齐后重试。'
  if (code === 'BALANCE_VALUE_ZERO') return passed ? '借贷已平衡。' : '借贷不平衡，请检查借贷金额。'
  if (code === 'PERIOD_OPEN') return passed ? '会计期间已开放。' : '会计期间未开放，暂时无法过账。'
  if (code === 'ACCOUNT_ALLOW_POST') return passed ? '科目可用且允许记账。' : '存在不可记账/已停用科目，请更换。'
  if (code === 'IDEMPOTENCY') return passed ? '未检测到重复过账。' : '检测到重复过账，该单据可能已过账。'
  return passed ? '通过。' : '未通过。'
}

function detailsOf(c: any): string[] {
  const code = String(c?.code || '')
  const d = c?.details || {}
  try {
    if (code === 'MIN_SPLITS') {
      const n = d?.line_count
      return typeof n === 'number' ? [`当前分录行数：${n}`] : []
    }
    if (code === 'BALANCE_VALUE_ZERO') {
      const out: string[] = []
      if (d?.sum_value != null) out.push(`当前差额：${d.sum_value}`)
      const issues = Array.isArray(d?.line_issues) ? d.line_issues : []
      for (const it of issues) {
        const ln = it?.line_no != null ? `第${it.line_no}行` : '某行'
        const reason = it?.reason ? String(it.reason) : '存在问题'
        out.push(`${ln}：${reason}`)
      }
      return out
    }
    if (code === 'PERIOD_OPEN') {
      const st = d?.status
      return st ? [`期间状态：${st === 'OPEN' ? 'OPEN（已开放）' : String(st)}`] : []
    }
    if (code === 'ACCOUNT_ALLOW_POST') {
      const bad = Array.isArray(d?.bad_accounts) ? d.bad_accounts : []
      return bad.slice(0, 5).map((x: any) => `科目：${x?.account_id || '-'}（${x?.reason || '不可用'}）`)
    }
    if (code === 'IDEMPOTENCY') {
      const existed = d?.existing_txn_id
      return existed ? ['该来源单据可能已生成凭证。'] : []
    }
  } catch {
    return []
  }
  return []
}

onMounted(async () => {
  await load()
})
</script>

<style scoped>
.top {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: center;
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
.btn.primary {
  background: #111827;
  color: white;
  border-color: #111827;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.muted {
  color: #666;
  font-size: 12px;
}
.ol {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #0f172a;
  font-size: 13px;
}
.success {
  margin: 10px 0 12px;
  padding: 10px 12px;
  border: 1px solid #b7eb8f;
  background: #f6ffed;
  border-radius: 10px;
}
.table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 12px;
}
.table th,
.table td {
  border-bottom: 1px solid #eee;
  padding: 10px;
  text-align: left;
  font-size: 14px;
}
.checks {
  list-style: none;
  padding: 0;
}
.checks li {
  border: 1px solid #eee;
  border-radius: 10px;
  padding: 10px;
  margin-bottom: 8px;
}
.checks li.ok {
  border-color: #b7eb8f;
  background: #f6ffed;
}
.checks li.bad {
  border-color: #ffccc7;
  background: #fff2f0;
}
.detail-list {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #374151;
  font-size: 12px;
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


