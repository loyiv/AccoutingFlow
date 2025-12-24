<template>
  <div class="layout">
    <section class="content">
      <div class="topbar">
        <div class="field">
          <label>账簿</label>
          <select v-model="app.selectedBookId" @change="loadTree">
            <option v-for="b in app.books" :key="b.id" :value="b.id">{{ b.name }}</option>
          </select>
        </div>
        <div class="field">
          <label>期间</label>
          <select v-model="periodFilter" @change="loadTree">
            <option value="">截至全部期间</option>
            <option v-for="p in app.periods" :key="p.id" :value="p.id">{{ p.year }}-{{ String(p.month).padStart(2, '0') }}</option>
          </select>
        </div>
        <div class="spacer"></div>
        <button class="btn" @click="openCreate">新建科目</button>
        <button class="btn" :disabled="!selectedAccountId" @click="openEdit">编辑科目</button>
        <button class="btn" @click="openImport">导入CSV</button>
        <button class="btn" @click="loadTree">刷新</button>
      </div>

      <ExampleCard title="操作示例（企业日常）：查看流水 & 做准备工作" subtitle="目标：定位常用科目（1001/1002/5001/4001），为采购/销售/报销/定期交易选择科目。">
        <ol class="ol">
          <li>在左侧科目树点击“1001 库存现金”或“1002 银行存款”，右侧即可看到寄存器流水。</li>
          <li>如果要新建科目：点“新建科目”，例如新增“1003 备用金”（资产类）。</li>
          <li>在寄存器里可把分录状态从 n→c→y，用于对账演示。</li>
        </ol>
      </ExampleCard>

      <div class="split">
        <aside class="sidebar">
          <h3>科目（名称 / 描述 / 合计）</h3>
          <div class="header-row">
            <span></span>
            <span>代码</span>
            <span>名称</span>
            <span>描述</span>
            <span class="right">合计</span>
          </div>
          <div class="tree">
            <AccountTreeNode v-for="n in tree" :key="n.id" :node="n" :selected="selectedAccountId" @select="onSelect" />
          </div>
        </aside>

        <section class="register">
          <h3>寄存器</h3>
          <p v-if="!selectedAccountId" class="muted">请选择左侧科目查看流水</p>

          <template v-else>
            <div class="reg-tools">
              <input v-model="registerQuery" placeholder="搜索：摘要/凭证号/备注" />
              <div class="summary">
                <span>总笔数：{{ filteredItems.length }}</span>
                <span>已清算(c)：{{ countC }}</span>
                <span>已对账(y)：{{ countY }}</span>
              </div>
            </div>

            <table class="table">
              <thead>
                <tr>
                  <th>凭证号</th>
                  <th>日期</th>
                  <th>摘要</th>
                  <th>分录行</th>
                  <th>状态</th>
                  <th>金额(value)</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="it in filteredItems" :key="it.split_id || (it.txn_id + '-' + it.split_line_no)">
                  <td>{{ it.txn_num }}</td>
                  <td>{{ it.txn_date }}</td>
                  <td>{{ it.description }}</td>
                  <td>{{ it.split_line_no }}</td>
                  <td>
                    <button class="pill" @click="cycleState(it)">{{ it.reconcile_state || 'n' }}</button>
                  </td>
                  <td>{{ it.value }}</td>
                </tr>
                <tr v-if="!filteredItems.length">
                  <td colspan="6" class="muted">暂无流水</td>
                </tr>
              </tbody>
            </table>
          </template>

          <div v-if="error" class="notice">提示：{{ error }}</div>
        </section>
      </div>
    </section>

    <div v-if="showDialog" class="modal">
      <div class="modal-card">
        <div class="modal-head">
          <b>{{ dialogMode === 'create' ? '新建科目' : '编辑科目' }}</b>
          <button class="btn" @click="closeDialog">关闭</button>
        </div>
        <div class="tabs">
          <button class="tab" :class="{ active: tab === 'general' }" @click="tab = 'general'">常规</button>
          <button class="tab" :class="{ active: tab === 'more' }" @click="tab = 'more'">更多属性</button>
          <button class="tab" :class="{ active: tab === 'opening' }" @click="tab = 'opening'">期初余额</button>
        </div>

        <div v-if="tab === 'general'" class="form">
          <div class="frow">
            <label>科目名称</label>
            <input v-model="form.name" />
          </div>
          <div class="frow">
            <label>科目代码</label>
            <input v-model="form.code" />
          </div>
          <div class="frow">
            <label>描述</label>
            <input v-model="form.description" />
          </div>
          <div class="frow">
            <label>父科目</label>
            <select v-model="form.parent_id">
              <option value="">（无）</option>
              <option v-for="a in flatAccounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</option>
            </select>
          </div>
        </div>

        <div v-else-if="tab === 'more'" class="form">
          <div class="frow">
            <label>科目类型</label>
            <select v-model="form.type">
              <option v-for="t in accountTypes" :key="t" :value="t">{{ t }}</option>
            </select>
          </div>
          <div class="frow">
            <label>货币/证券</label>
            <input v-model="form.commodity_id" disabled />
            <span class="muted">（当前固定为账簿本位币）</span>
          </div>
          <div class="checks">
            <label><input type="checkbox" v-model="form.is_placeholder" /> 占位科目（不允许记账）</label>
            <label><input type="checkbox" v-model="form.is_hidden" /> 隐藏</label>
            <label><input type="checkbox" v-model="form.is_active" /> 启用</label>
            <label><input type="checkbox" v-model="form.allow_post" :disabled="form.is_placeholder" /> 允许记账</label>
          </div>
        </div>

        <div v-else class="form">
          <p class="muted">期初余额：后续会做“期初余额凭证/期间结转”。目前可通过创建一张草稿并过账来录入。</p>
        </div>

        <div class="modal-foot">
          <button class="btn primary" :disabled="saving" @click="saveAccount">保存</button>
        </div>
        <div v-if="dialogError" class="notice">提示：{{ dialogError }}</div>
      </div>
    </div>

    <div v-if="showImport" class="modal">
      <div class="modal-card">
        <div class="modal-head">
          <b>导入科目 CSV</b>
          <button class="btn" @click="showImport = false">关闭</button>
        </div>
        <div class="form">
          <div class="muted">
            推荐表头（任意顺序）：<code>code,name,parent_code,description,type,allow_post,is_active,is_hidden,is_placeholder</code>
            （也支持中文表头：科目代码/科目名称/父科目代码/描述/科目类型/允许记账/启用/隐藏/占位科目）
          </div>
          <div class="frow">
            <label>选择文件</label>
            <input type="file" accept=".csv,text/csv" @change="onImportFile" />
          </div>
          <div class="frow">
            <label>分隔符</label>
            <select v-model="importDelimiter">
              <option value="">自动识别</option>
              <option value=",">逗号 (,)</option>
              <option value=";">分号 (;)</option>
              <option value="\t">制表符 (TAB)</option>
            </select>
          </div>
          <div class="checks">
            <label><input type="checkbox" v-model="importUpdateExisting" /> 若 code 已存在则更新（可重复导入）</label>
          </div>

          <div v-if="importPreview" class="card-inner">
            <div class="muted">识别分隔符：<code>{{ importPreview.detected_delimiter === '\t' ? 'TAB' : importPreview.detected_delimiter }}</code></div>
            <table class="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th v-for="h in importPreview.headers" :key="h">{{ h }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in importPreview.rows" :key="r.row_no">
                  <td>{{ r.row_no }}</td>
                  <td v-for="h in importPreview.headers" :key="h">{{ r.data[h] }}</td>
                </tr>
              </tbody>
            </table>
            <div v-if="importPreview.warnings?.length" class="muted">
              <div v-for="(w, i) in importPreview.warnings" :key="i">注意：{{ w }}</div>
            </div>
          </div>
        </div>

        <div class="modal-foot">
          <button class="btn primary" :disabled="importing || !importFile" @click="commitImport">确认导入</button>
        </div>
        <div v-if="importError" class="notice">提示：{{ importError }}</div>
        <p v-if="importResult" class="muted">
          导入完成：created={{ importResult.created }}, updated={{ importResult.updated }}, skipped={{ importResult.skipped }}
        </p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { api } from '../../services/api'
import AccountTreeNode from '../../components/AccountTreeNode.vue'
import ExampleCard from '../../components/ExampleCard.vue'

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

const app = useAppStore()
const route = useRoute()
const tree = ref<Node[]>([])
const selectedAccountId = ref('')
const register = ref<any>({ items: [] })
const registerQuery = ref('')
const error = ref('')
const periodFilter = ref<string>('')

const showDialog = ref(false)
const dialogMode = ref<'create' | 'edit'>('create')
const tab = ref<'general' | 'more' | 'opening'>('general')
const saving = ref(false)
const dialogError = ref('')

const accountTypes = [
  'ASSET',
  'LIABILITY',
  'EQUITY',
  'INCOME',
  'EXPENSE',
  'CASH',
  'BANK',
  'AR',
  'AP',
  'LIABILITY',
]

const flatAccounts = ref<Array<{ id: string; code: string; name: string }>>([])
const baseCommodityId = ref<string>('')

const form = ref<any>({
  book_id: '',
  parent_id: '',
  code: '',
  name: '',
  description: '',
  type: 'ASSET',
  commodity_id: '',
  allow_post: true,
  is_active: true,
  is_hidden: false,
  is_placeholder: false,
})

// import csv
const showImport = ref(false)
const importFile = ref<File | null>(null)
const importDelimiter = ref<string>('')
const importUpdateExisting = ref(true)
const importPreview = ref<any | null>(null)
const importing = ref(false)
const importError = ref('')
const importResult = ref<any | null>(null)

async function loadTree() {
  error.value = ''
  try {
    if (!app.books.length) await app.init()
    await app.reloadPeriods()
    tree.value = await api.getAccountsTree(app.selectedBookId, periodFilter.value || undefined)
    flatAccounts.value = flatten(tree.value).map((x) => ({ id: x.id, code: x.code, name: x.name }))
    baseCommodityId.value = app.books.find((b) => b.id === app.selectedBookId)?.base_currency_id || ''
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function loadRegister() {
  if (!selectedAccountId.value) return
  error.value = ''
  try {
    register.value = await api.getRegister(selectedAccountId.value, app.selectedPeriodId || undefined)
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

function flatten(nodes: Node[]): Node[] {
  const out: Node[] = []
  for (const n of nodes) {
    out.push(n)
    if (n.children?.length) out.push(...flatten(n.children))
  }
  return out
}

function onSelect(id: string) {
  selectedAccountId.value = id
  loadRegister()
}

function _match(it: any, q: string) {
  const s = (q || '').trim().toLowerCase()
  if (!s) return true
  const hay = `${it.txn_num || ''} ${it.description || ''} ${it.memo || ''}`.toLowerCase()
  return hay.includes(s)
}

const filteredItems = computed(() => (register.value?.items || []).filter((x: any) => _match(x, registerQuery.value)))
const countC = computed(() => filteredItems.value.filter((x: any) => x.reconcile_state === 'c').length)
const countY = computed(() => filteredItems.value.filter((x: any) => x.reconcile_state === 'y').length)

async function cycleState(it: any) {
  const cur = it.reconcile_state || 'n'
  const next = cur === 'n' ? 'c' : cur === 'c' ? 'y' : 'n'
  try {
    if (!it.split_id) throw new Error('缺少 split_id，后端需要升级后才能切换状态')
    await api.setSplitReconcile(it.split_id, next)
    it.reconcile_state = next
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

function openCreate() {
  dialogMode.value = 'create'
  tab.value = 'general'
  dialogError.value = ''
  showDialog.value = true
  form.value = {
    book_id: app.selectedBookId,
    parent_id: selectedAccountId.value || '',
    code: '',
    name: '',
    description: '',
    type: 'ASSET',
    commodity_id: baseCommodityId.value,
    allow_post: true,
    is_active: true,
    is_hidden: false,
    is_placeholder: false,
  }
}

async function openEdit() {
  if (!selectedAccountId.value) return
  dialogMode.value = 'edit'
  tab.value = 'general'
  dialogError.value = ''
  showDialog.value = true
  const a = await api.getAccount(selectedAccountId.value)
  form.value = { ...a, parent_id: a.parent_id || '' }
}

function closeDialog() {
  showDialog.value = false
}

async function saveAccount() {
  saving.value = true
  dialogError.value = ''
  try {
    const payload = { ...form.value }
    payload.parent_id = payload.parent_id || null
    payload.commodity_id = payload.commodity_id || baseCommodityId.value
    if (dialogMode.value === 'create') {
      await api.createAccount(payload)
    } else {
      const id = String(form.value.id)
      await api.updateAccount(id, payload)
    }
    showDialog.value = false
    await loadTree()
  } catch (e: any) {
    dialogError.value = e?.message || String(e)
  } finally {
    saving.value = false
  }
}

function openImport() {
  showImport.value = true
  importFile.value = null
  importDelimiter.value = ''
  importPreview.value = null
  importError.value = ''
  importResult.value = null
}

async function onImportFile(e: any) {
  const f: File | null = e?.target?.files?.[0] || null
  if (!f) return
  importFile.value = f
  importError.value = ''
  importResult.value = null
  try {
    if (!app.selectedBookId) throw new Error('请先选择账簿')
    importPreview.value = await api.previewAccountsImport(app.selectedBookId, f, importDelimiter.value || undefined)
  } catch (err: any) {
    importError.value = err?.message || String(err)
  }
}

async function commitImport() {
  if (!importFile.value) return
  importing.value = true
  importError.value = ''
  try {
    if (!app.selectedBookId) throw new Error('请先选择账簿')
    const res = await api.commitAccountsImport(app.selectedBookId, importFile.value, importDelimiter.value || undefined, importUpdateExisting.value)
    importResult.value = res
    await loadTree()
  } catch (err: any) {
    importError.value = err?.message || String(err)
  } finally {
    importing.value = false
  }
}

onMounted(async () => {
  await loadTree()
  // 支持从“主页”跳转：自动选中/打开编辑/新建
  const q: any = route.query || {}
  const accountId = String(q.account_id || '')
  const create = String(q.create || '') === '1'
  const edit = String(q.edit || '') === '1'
  const parentId = String(q.parent_id || '')

  if (accountId) {
    selectedAccountId.value = accountId
    await loadRegister()
  }
  if (create) {
    if (parentId) selectedAccountId.value = parentId
    openCreate()
  } else if (edit && accountId) {
    selectedAccountId.value = accountId
    await openEdit()
  }
})
</script>

<style scoped>
.layout {
  display: grid;
  gap: 16px;
}
.topbar {
  display: flex;
  gap: 12px;
  align-items: end;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
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
.split {
  display: grid;
  grid-template-columns: 540px 1fr;
  gap: 12px;
}
.sidebar {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
}
.header-row {
  display: grid;
  grid-template-columns: 18px 70px 1fr 1.2fr 90px;
  gap: 8px;
  padding: 6px 6px;
  font-size: 12px;
  color: #667085;
  border-bottom: 1px solid #eee;
  margin-bottom: 6px;
}
.header-row .right {
  text-align: right;
}
.tree {
  font-size: 13px;
}
.content {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
}
.register {
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
.reg-tools {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 8px 0 10px;
}
.reg-tools input {
  flex: 1;
  border: 1px solid #ddd;
  padding: 8px 10px;
  border-radius: 10px;
}
.summary {
  display: flex;
  gap: 10px;
  color: #666;
  font-size: 12px;
}
.pill {
  border: 1px solid #ddd;
  background: #f8fafc;
  padding: 2px 8px;
  border-radius: 999px;
  cursor: pointer;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
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
.notice {
  margin-top: 12px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #111827;
  padding: 10px 12px;
  border-radius: 10px;
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
.tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 10px;
}
.tab {
  border: 1px solid #ddd;
  background: white;
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
}
.tab.active {
  border-color: #111827;
  background: #111827;
  color: white;
}
.form {
  display: grid;
  gap: 10px;
}
.frow {
  display: grid;
  grid-template-columns: 120px 1fr;
  gap: 10px;
  align-items: center;
}
input,
textarea {
  border: 1px solid #ddd;
  padding: 8px 10px;
  border-radius: 10px;
}
.checks {
  display: grid;
  gap: 8px;
  padding: 8px 0;
}
.modal-foot {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>


