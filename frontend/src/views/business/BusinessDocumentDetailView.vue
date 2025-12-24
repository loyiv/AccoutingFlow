<template>
  <div class="page">
    <div class="top">
      <div>
        <h2>业务单据详情</h2>
        <p v-if="doc" class="muted">
          {{ doc.doc_type }} · {{ doc.doc_no }} · {{ doc.status }} · revision={{ doc.revision_no }}
        </p>
      </div>
      <div class="actions">
        <button class="btn" @click="load">刷新</button>
        <RouterLink v-if="doc?.draft_id" class="btn" :to="`/gl/drafts/${doc.draft_id}`">打开草稿</RouterLink>
        <button class="btn primary" v-if="doc?.status === 'REJECTED'" @click="openResubmit">重新提交</button>
      </div>
    </div>

    <ExampleCard title="操作示例（企业日常）：单据 → 草稿 → 过账" subtitle="目标：从业务单据进入草稿并完成审批/过账，进入总账与报表。">
      <ol class="ol">
        <li>在采购/销售/报销列表点进任意单据，点击“打开草稿”。</li>
        <li>在草稿页依次点击：审批 → 过账。</li>
        <li>过账后可到“科目与寄存器/报表”验证数据。</li>
      </ol>
    </ExampleCard>

    <div v-if="doc" class="grid">
      <section class="card">
        <h3>基本信息</h3>
        <div class="kv"><b>日期</b><span>{{ doc.doc_date }}</span></div>
        <div class="kv"><b>说明</b><span>{{ doc.description }}</span></div>
        <div class="kv"><b>项目</b><span>{{ doc.project || '-' }}</span></div>
        <div class="kv"><b>账期(天)</b><span>{{ doc.term_days ?? '-' }}</span></div>
        <div class="kv"><b>往来单位</b><span>{{ doc.party_id || '-' }}</span></div>
        <div class="kv"><b>员工</b><span>{{ doc.employee_id || '-' }}</span></div>
        <div class="kv"><b>总额</b><span>{{ doc.total_amount }}</span></div>
        <div class="kv"><b>税额</b><span>{{ doc.tax_amount }}</span></div>
        <div class="kv" v-if="doc.rejected_reason"><b>退回原因</b><span class="bad">{{ doc.rejected_reason }}</span></div>
      </section>

      <section class="card">
        <h3>明细</h3>
        <table class="table">
          <thead>
            <tr><th>行</th><th>描述</th><th>科目</th><th>数量</th><th>单价</th><th>税率</th><th>金额</th><th>税额</th></tr>
          </thead>
          <tbody>
            <tr v-for="ln in doc.lines" :key="ln.line_no">
              <td>{{ ln.line_no }}</td>
              <td>{{ ln.description }}</td>
              <td>{{ accountLabel(ln.account_id) }}</td>
              <td>{{ ln.quantity }}</td>
              <td>{{ ln.unit_price }}</td>
              <td>{{ ln.tax_rate }}</td>
              <td>{{ ln.amount }}</td>
              <td>{{ ln.tax_amount }}</td>
            </tr>
            <tr v-if="!doc.lines?.length"><td colspan="8" class="muted">暂无明细</td></tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <h3>附件</h3>
        <div class="muted" v-if="!doc.attachment_ids?.length">暂无附件</div>
        <ul v-else class="list">
          <li v-for="aid in doc.attachment_ids" :key="aid">{{ aid }}</li>
        </ul>
      </section>
    </div>

    <div v-if="showResubmit" class="modal">
      <div class="modal-card">
        <div class="modal-head">
          <b>重新提交（会生成新的草稿与 revision）</b>
          <button class="btn" @click="showResubmit = false">关闭</button>
        </div>

        <div class="form">
          <div class="frow"><label>日期</label><input v-model="form.doc_date" placeholder="YYYY-MM-DD" /></div>
          <div class="frow"><label>项目</label><input v-model="form.project" /></div>
          <div class="frow"><label>账期(天)</label><input v-model="form.term_days" /></div>
          <div class="frow"><label>说明</label><input v-model="form.description" /></div>

          <h4>明细（可修改）</h4>
          <table class="table">
            <thead><tr><th>描述</th><th>科目</th><th>数量</th><th>单价</th><th>税率</th><th></th></tr></thead>
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
                <td><input v-model="ln.tax_rate" /></td>
                <td><a href="#" @click.prevent="removeLine(idx)">删除</a></td>
              </tr>
            </tbody>
          </table>
          <button class="btn" @click="addLine">+ 添加行</button>

          <h4>附件（追加上传）</h4>
          <input type="file" multiple @change="onFiles" />
          <div class="muted">当前 attachment_ids：{{ form.attachment_ids.length }}</div>
        </div>

        <div class="modal-foot">
          <button class="btn primary" :disabled="saving" @click="submit">提交</button>
        </div>
        <div v-if="error" class="notice">提示：{{ error }}</div>
      </div>
    </div>

    <div v-if="error" class="notice">提示：{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'

const route = useRoute()
const router = useRouter()
const id = computed(() => String(route.params.id))

const doc = ref<any | null>(null)
const error = ref('')
const flatAccounts = ref<Array<{ id: string; code: string; name: string; allow_post: boolean; is_active: boolean; is_placeholder?: boolean }>>([])
const postableAccounts = ref<any[]>([])

const showResubmit = ref(false)
const saving = ref(false)
const form = ref<any>({
  doc_date: '',
  project: '',
  term_days: '',
  description: '',
  lines: [],
  attachment_ids: [] as string[],
})

async function load() {
  error.value = ''
  try {
    doc.value = await api.getDocument(id.value)
    if (doc.value?.book_id) {
      const tree = await api.getAccountsTree(doc.value.book_id)
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
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

function flatten(nodes: any[]): any[] {
  const out: any[] = []
  for (const n of nodes || []) {
    out.push(n)
    if (n.children?.length) out.push(...flatten(n.children))
  }
  return out
}
function accountLabel(accountId: string) {
  const a = flatAccounts.value.find((x) => x.id === accountId)
  return a ? `${a.code} ${a.name}` : accountId
}

function openResubmit() {
  if (!doc.value) return
  showResubmit.value = true
  error.value = ''
  form.value = {
    doc_date: doc.value.doc_date,
    project: doc.value.project || '',
    term_days: doc.value.term_days ?? '',
    description: doc.value.description || '',
    lines: (doc.value.lines || []).map((x: any) => ({
      description: x.description || '',
      account_id: x.account_id,
      quantity: String(x.quantity ?? '1'),
      unit_price: String(x.unit_price ?? '0'),
      tax_rate: String(x.tax_rate ?? ''),
      memo: x.memo || '',
    })),
    attachment_ids: [...(doc.value.attachment_ids || [])],
  }
}

function addLine() {
  form.value.lines.push({ description: '', account_id: '', quantity: '1', unit_price: '0', tax_rate: '', memo: '' })
}
function removeLine(i: number) {
  form.value.lines.splice(i, 1)
}

async function onFiles(e: any) {
  const files: FileList | null = e?.target?.files || null
  if (!files || !files.length) return
  for (const f of Array.from(files)) {
    const res = await api.uploadAttachment(f)
    form.value.attachment_ids.push(res.id)
  }
}

async function submit() {
  if (!doc.value) return
  saving.value = true
  error.value = ''
  try {
    const payload: any = {
      doc_date: form.value.doc_date || null,
      project: form.value.project || null,
      term_days: form.value.term_days === '' ? null : Number(form.value.term_days),
      description: form.value.description || null,
      lines: (form.value.lines || []).map((x: any) => ({
        description: x.description || '',
        account_id: x.account_id,
        quantity: Number(x.quantity || 1),
        unit_price: Number(x.unit_price || 0),
        tax_rate: x.tax_rate === '' ? null : Number(x.tax_rate),
        memo: x.memo || '',
      })),
      attachment_ids: form.value.attachment_ids,
    }
    const updated = await api.resubmitDocument(doc.value.id, payload)
    showResubmit.value = false
    doc.value = updated
    if (updated?.draft_id) await router.push(`/gl/drafts/${updated.draft_id}`)
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
  text-decoration: none;
  color: inherit;
}
.btn.primary {
  background: #111827;
  color: white;
  border-color: #111827;
}
.grid {
  display: grid;
  gap: 12px;
}
.card {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
}
.kv {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed #eee;
  font-size: 14px;
}
.bad {
  color: #b42318;
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
.list {
  margin: 6px 0 0 18px;
  color: #333;
}
input {
  border: 1px solid #ddd;
  padding: 6px 10px;
  border-radius: 10px;
}
select {
  border: 1px solid #ddd;
  padding: 6px 10px;
  border-radius: 10px;
}
.ol {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #0f172a;
  font-size: 13px;
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


