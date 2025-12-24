<template>
  <div class="page">
    <div class="top">
      <h2>销售订单</h2>
      <div class="actions">
        <button class="btn" @click="openCreate">新建销售订单</button>
        <button class="btn" @click="openExample">一键填充示例</button>
        <button class="btn" @click="load">刷新</button>
      </div>
    </div>

    <ExampleCard title="操作示例（企业日常）：销售咨询服务" subtitle="目标：生成销售草稿 → 审批 → 过账，形成应收/收入/税费。">
      <ol class="ol">
        <li>点击“<b>一键填充示例</b>”，客户=示例客户，收入科目=4001 主营业务收入。</li>
        <li>点击“保存并生成草稿”，进入草稿页后依次点击：审批 → 过账。</li>
        <li>过账后可在“报表”生成当期报表并下钻查看该笔凭证。</li>
      </ol>
    </ExampleCard>

    <table class="table">
      <thead>
        <tr><th>单号</th><th>日期</th><th>客户</th><th>状态</th><th>总额</th><th>草稿</th></tr>
      </thead>
      <tbody>
        <tr v-for="d in docs" :key="d.id">
          <td><RouterLink :to="`/business/documents/${d.id}`">{{ d.doc_no }}</RouterLink></td>
          <td>{{ d.doc_date }}</td>
          <td>{{ partyName(d.party_id) }}</td>
          <td>{{ d.status }}</td>
          <td>{{ d.total_amount }}</td>
          <td><RouterLink v-if="d.draft_id" :to="`/gl/drafts/${d.draft_id}`">打开草稿</RouterLink></td>
        </tr>
        <tr v-if="!docs.length"><td colspan="6" class="muted">暂无销售订单</td></tr>
      </tbody>
    </table>

    <div v-if="showDialog" class="modal">
      <div class="modal-card">
        <div class="modal-head">
          <b>新建销售订单</b>
          <button class="btn" @click="close">关闭</button>
        </div>

        <div class="form">
          <div class="frow"><label>账簿</label><input :value="app.selectedBookName" disabled /></div>
          <div class="frow">
            <label>期间</label>
            <select v-model="app.selectedPeriodId">
              <option v-for="p in app.periods" :key="p.id" :value="p.id">{{ p.year }}-{{ String(p.month).padStart(2, '0') }}</option>
            </select>
          </div>
          <div class="frow">
            <label>客户</label>
            <select v-model="form.customer_id">
              <option value="">请选择</option>
              <option v-for="c in customers" :key="c.id" :value="c.id">{{ c.name }}</option>
            </select>
          </div>
          <div class="frow"><label>项目</label><input v-model="form.project" /></div>
          <div class="frow"><label>账期(天)</label><input v-model="form.term_days" placeholder="默认按规则" /></div>
          <div class="frow"><label>说明</label><input v-model="form.description" /></div>

          <h4>明细行（贷：收入科目；借：应收账款；默认税率 13%）</h4>
          <table class="table">
            <thead><tr><th>描述</th><th>收入科目</th><th>数量</th><th>单价</th><th>税率</th><th>操作</th></tr></thead>
            <tbody>
              <tr v-for="(ln, idx) in form.lines" :key="idx">
                <td><input v-model="ln.description" /></td>
                <td>
                  <select v-model="ln.account_id">
                    <option value="">请选择</option>
                    <option v-for="a in postableAccounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</option>
                  </select>
                </td>
                <td><input v-model="ln.quantity" /></td>
                <td><input v-model="ln.unit_price" /></td>
                <td><input v-model="ln.tax_rate" placeholder="0.13" /></td>
                <td><a href="#" @click.prevent="removeLine(idx)">删除</a></td>
              </tr>
            </tbody>
          </table>
          <button class="btn" @click="addLine">+ 添加行</button>

          <h4>附件</h4>
          <input type="file" multiple @change="onFiles" />
          <div class="muted" v-if="attachmentIds.length">已上传 {{ attachmentIds.length }} 个</div>
        </div>

        <div class="modal-foot">
          <button class="btn primary" :disabled="saving" @click="save">保存并生成草稿</button>
        </div>
        <div v-if="error" class="notice">提示：{{ error }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'

const router = useRouter()
const app = useAppStore()
const docs = ref<any[]>([])
const customers = ref<any[]>([])
const partyById = ref<Record<string, any>>({})
const flatAccounts = ref<Array<{ id: string; code: string; name: string; allow_post: boolean; is_active: boolean; is_placeholder?: boolean }>>([])

const showDialog = ref(false)
const saving = ref(false)
const error = ref('')
const attachmentIds = ref<string[]>([])

const form = ref<any>({
  customer_id: '',
  project: '',
  term_days: '',
  description: '',
  lines: [{ description: '', account_id: '', quantity: '1', unit_price: '0', tax_rate: '0.13', memo: '' }],
})

function flatten(nodes: any[]): any[] {
  const out: any[] = []
  for (const n of nodes || []) {
    out.push(n)
    if (n.children?.length) out.push(...flatten(n.children))
  }
  return out
}
function byCode(code: string) {
  return flatAccounts.value.find((x) => String(x.code) === String(code))?.id || ''
}
const postableAccounts = ref<any[]>([])

function partyName(id: string | null) {
  if (!id) return '-'
  return partyById.value[id]?.name || id
}

async function load() {
  error.value = ''
  if (!app.books.length) await app.init()
  await app.reloadPeriods()
  customers.value = await api.listCustomers()
  partyById.value = Object.fromEntries(customers.value.map((x: any) => [x.id, x]))
  if (app.selectedBookId) {
    const tree = await api.getAccountsTree(app.selectedBookId)
    flatAccounts.value = flatten(tree).map((x: any) => ({
      id: x.id,
      code: x.code,
      name: x.name,
      allow_post: !!x.allow_post,
      is_active: !!x.is_active,
      is_placeholder: !!x.is_placeholder,
    }))
    postableAccounts.value = flatAccounts.value.filter((x) => x.allow_post && x.is_active && !x.is_placeholder)
  }
  docs.value = await api.listDocuments('SALES_ORDER')
}

function openCreate() {
  showDialog.value = true
  error.value = ''
  attachmentIds.value = []
  form.value = {
    customer_id: '',
    project: '',
    term_days: '',
    description: '',
    lines: [{ description: '', account_id: '', quantity: '1', unit_price: '0', tax_rate: '0.13', memo: '' }],
  }
}

function openExample() {
  openCreate()
  const c = customers.value.find((x: any) => String(x.name || '').includes('示例'))?.id || customers.value[0]?.id || ''
  form.value.customer_id = c
  form.value.project = '销售部'
  form.value.description = '示例销售：咨询服务（含税）'
  form.value.lines = [{ description: '咨询服务', account_id: byCode('4001'), quantity: '1', unit_price: '1000', tax_rate: '0.13', memo: '咨询服务收入' }]
}
function close() {
  showDialog.value = false
}

function addLine() {
  form.value.lines.push({ description: '', account_id: '', quantity: '1', unit_price: '0', tax_rate: '0.13', memo: '' })
}
function removeLine(i: number) {
  form.value.lines.splice(i, 1)
}

async function onFiles(e: any) {
  const files: FileList | null = e?.target?.files || null
  if (!files || !files.length) return
  for (const f of Array.from(files)) {
    const res = await api.uploadAttachment(f)
    attachmentIds.value.push(res.id)
  }
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (!app.selectedBookId || !app.selectedPeriodId) throw new Error('请先选择账簿与期间')
    const payload: any = {
      book_id: app.selectedBookId,
      period_id: app.selectedPeriodId,
      doc_no: '',
      doc_date: new Date().toISOString().slice(0, 10),
      customer_id: form.value.customer_id,
      project: form.value.project,
      term_days: form.value.term_days ? Number(form.value.term_days) : null,
      description: form.value.description,
      lines: form.value.lines.map((x: any) => ({
        description: x.description || '',
        account_id: x.account_id,
        quantity: Number(x.quantity || 1),
        unit_price: Number(x.unit_price || 0),
        tax_rate: x.tax_rate === '' ? null : Number(x.tax_rate),
        memo: x.memo || '',
      })),
      attachment_ids: attachmentIds.value,
    }
    const doc = await api.createSalesOrder(payload)
    showDialog.value = false
    await load()
    if (doc?.draft_id) await router.push(`/gl/drafts/${doc.draft_id}`)
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}
.actions {
  display: flex;
  gap: 8px;
}
.btn {
  border: 1px solid #ddd;
  background: white;
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
}
.btn.primary {
  background: #111827;
  color: white;
  border-color: #111827;
}
.table {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 10px;
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
.ol {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #0f172a;
  font-size: 13px;
}
input,
select {
  border: 1px solid #ddd;
  padding: 6px 10px;
  border-radius: 10px;
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
  width: min(1000px, 96vw);
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
.form {
  display: grid;
  gap: 10px;
}
.frow {
  display: grid;
  grid-template-columns: 140px 1fr;
  gap: 10px;
  align-items: center;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
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


