<template>
  <div class="page">
    <div class="top">
      <h2>定期交易（Scheduled Transactions）</h2>
      <div class="actions">
        <button class="btn" @click="openCreate">新建</button>
        <button class="btn" @click="openExample">一键填充示例</button>
        <button class="btn" @click="load">刷新</button>
      </div>
    </div>

    <ExampleCard title="操作示例（企业日常）：每月房租" subtitle="目标：定期交易生成草稿 → 审批 → 过账，然后用于对账/报表。">
      <ol class="ol">
        <li>点击“<b>一键填充示例</b>”（或直接用后端预置的“示例：每月房租”）。</li>
        <li>在列表里点击“运行一次（生成草稿）”，然后跳转到草稿页：审批 → 过账。</li>
        <li>回到“对账”页面，可用库存现金 1001 的流水做一次对账演示。</li>
      </ol>
    </ExampleCard>

    <p class="muted">
      这是参考 GnuCash 的“定期交易”能力做的最小可用版：按规则生成分录草稿（不会自动过账）。
    </p>

    <table class="table">
      <thead>
        <tr><th>名称</th><th>规则</th><th>下次运行</th><th>启用</th><th>操作</th></tr>
      </thead>
      <tbody>
        <tr v-for="s in items" :key="s.id">
          <td>{{ s.name }}</td>
          <td>{{ s.rule }} / {{ s.interval }}</td>
          <td>{{ s.next_run_date }}</td>
          <td>{{ s.enabled ? '是' : '否' }}</td>
          <td>
            <button class="btn" @click="runNow(s.id)">运行一次（生成草稿）</button>
          </td>
        </tr>
        <tr v-if="!items.length"><td colspan="5" class="muted">暂无定期交易</td></tr>
      </tbody>
    </table>

    <div v-if="showDialog" class="modal">
      <div class="modal-card">
        <div class="modal-head">
          <b>新建定期交易</b>
          <button class="btn" @click="showDialog = false">关闭</button>
        </div>

        <div class="form">
          <div class="frow"><label>账簿</label><input :value="app.selectedBookName" disabled /></div>
          <div class="frow"><label>名称</label><input v-model="form.name" /></div>
          <div class="frow"><label>说明</label><input v-model="form.description" /></div>
          <div class="frow">
            <label>规则</label>
            <select v-model="form.rule">
              <option value="DAILY">DAILY</option>
              <option value="WEEKLY">WEEKLY</option>
              <option value="MONTHLY">MONTHLY</option>
            </select>
          </div>
          <div class="frow"><label>间隔</label><input v-model="form.interval" /></div>
          <div class="frow"><label>下次运行日期</label><input v-model="form.next_run_date" placeholder="YYYY-MM-DD" /></div>
          <div class="checks"><label><input type="checkbox" v-model="form.enabled" /> 启用</label></div>

          <h4>模板分录（必须平衡，至少 2 行）</h4>
          <table class="table">
            <thead><tr><th>科目</th><th>借方</th><th>贷方</th><th>备注</th><th></th></tr></thead>
            <tbody>
              <tr v-for="(ln, idx) in form.lines" :key="idx">
                <td>
                  <select v-model="ln.account_id">
                    <option value="">请选择</option>
                    <option v-for="a in postableAccounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</option>
                  </select>
                </td>
                <td><input v-model="ln.debit" /></td>
                <td><input v-model="ln.credit" /></td>
                <td><input v-model="ln.memo" /></td>
                <td><a href="#" @click.prevent="removeLine(idx)">删除</a></td>
              </tr>
            </tbody>
          </table>
          <button class="btn" @click="addLine">+ 添加行</button>
        </div>

        <div class="modal-foot">
          <button class="btn primary" :disabled="saving" @click="save">保存</button>
        </div>
        <div v-if="error" class="notice">提示：{{ error }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'

const router = useRouter()
const app = useAppStore()
const items = ref<any[]>([])
const flatAccounts = ref<Array<{ id: string; code: string; name: string; allow_post: boolean; is_active: boolean; is_placeholder?: boolean }>>([])
const postableAccounts = ref<any[]>([])

const showDialog = ref(false)
const saving = ref(false)
const error = ref('')
const form = ref<any>({
  name: '',
  description: '',
  rule: 'MONTHLY',
  interval: '1',
  next_run_date: new Date().toISOString().slice(0, 10),
  enabled: true,
  lines: [
    { account_id: '', debit: '0', credit: '0', memo: '' },
    { account_id: '', debit: '0', credit: '0', memo: '' },
  ],
})

async function load() {
  if (!app.books.length) await app.init()
  if (!app.selectedBookId) return
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
  items.value = await api.listScheduled(app.selectedBookId)
}

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

function openCreate() {
  error.value = ''
  showDialog.value = true
  form.value = {
    name: '',
    description: '',
    rule: 'MONTHLY',
    interval: '1',
    next_run_date: new Date().toISOString().slice(0, 10),
    enabled: true,
    lines: [
      { account_id: '', debit: '0', credit: '0', memo: '' },
      { account_id: '', debit: '0', credit: '0', memo: '' },
    ],
  }
}

function openExample() {
  openCreate()
  form.value.name = '每月房租（示例）'
  form.value.description = '每月房租 2000（借：管理费用；贷：库存现金）'
  form.value.rule = 'MONTHLY'
  form.value.interval = '1'
  form.value.next_run_date = new Date().toISOString().slice(0, 10)
  form.value.enabled = true
  form.value.lines = [
    { account_id: byCode('5001'), debit: '2000', credit: '0', memo: '借：管理费用' },
    { account_id: byCode('1001'), debit: '0', credit: '2000', memo: '贷：库存现金' },
  ]
}
function addLine() {
  form.value.lines.push({ account_id: '', debit: '0', credit: '0', memo: '' })
}
function removeLine(i: number) {
  form.value.lines.splice(i, 1)
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    if (!app.selectedBookId) throw new Error('请先选择账簿')
    const payload = {
      book_id: app.selectedBookId,
      name: form.value.name,
      description: form.value.description || '',
      enabled: !!form.value.enabled,
      rule: form.value.rule,
      interval: Number(form.value.interval || 1),
      next_run_date: form.value.next_run_date,
      end_date: null,
      template: {
        description: form.value.description || form.value.name,
        lines: form.value.lines.map((x: any) => ({
          account_id: x.account_id,
          debit: Number(x.debit || 0),
          credit: Number(x.credit || 0),
          memo: x.memo || '',
          aux_json: null,
        })),
      },
    }
    await api.createScheduled(payload)
    showDialog.value = false
    await load()
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    saving.value = false
  }
}

async function runNow(id: string) {
  error.value = ''
  try {
    const r = await api.runScheduled(id)
    if (r?.draft_id) await router.push(`/gl/drafts/${r.draft_id}`)
    await load()
  } catch (e: any) {
    error.value = e?.message || String(e)
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
.checks {
  display: flex;
  gap: 10px;
  color: #666;
  font-size: 12px;
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


