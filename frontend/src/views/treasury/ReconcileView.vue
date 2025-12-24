<template>
  <div class="window">
    <!-- 顶部菜单：对齐你截图里的“对账/科目/交易/帮助” -->
    <div class="menubar" @click.stop>
      <div class="menu" v-for="m in menus" :key="m.label" @click.stop>
        <span class="menu-label" :class="{ active: openMenuLabel === m.label }" @click.stop="toggleMenu(m.label)">{{ m.label }}</span>
        <div v-if="openMenuLabel === m.label" class="menu-pop">
          <div v-for="it in m.items" :key="it.label" class="menu-item" :class="{ disabled: !!it.disabled }" @click="onMenuClick(it)">
            <span>{{ it.label }}</span>
            <span class="hotkey">{{ it.hotkey || '' }}</span>
          </div>
      </div>
      </div>
      <div class="spacer"></div>
      <div class="muted">差额必须为 0 才能完成对账</div>
    </div>

    <!-- 工具栏：平衡/核对选中/取消核对/打开/完成 -->
    <div ref="toolbarRef" class="toolbar" @click.stop>
      <button class="tool" :disabled="!detail || almostZero(detail.difference)" @click="openBalance">
        <span>平衡</span>
      </button>
      <button
        class="tool"
        :disabled="!activeItem || !detailIsOpen"
        :title="!detailIsOpen ? '该会话已完成，无法再勾选' : ''"
        @click="toggleActive(true)"
      >
        <span>核对选中</span>
      </button>
      <button
        class="tool"
        :disabled="!activeItem || !detailIsOpen"
        :title="!detailIsOpen ? '该会话已完成，无法再勾选' : ''"
        @click="toggleActive(false)"
      >
        <span>取消核对</span>
      </button>
      <button class="tool" :disabled="!activeItem" @click="openTxn">
        <span>打开</span>
      </button>
      <button
        class="tool primary"
        :disabled="!canFinish"
        :title="finishHint"
        ref="finishBtnRef"
        @click="finish"
      >
        <span>完成</span>
      </button>
    </div>

    <!-- 醒目指引：当差额为 0 时，提示用户点击“完成” -->
    <div v-if="finishNudge.show" class="finish-nudge" @click="jumpTo(finishBtnRef)">
      <div class="finish-nudge-inner">
        <span class="finish-nudge-dot" aria-hidden="true"></span>
        <b>差额已为 0</b>，请点击上侧 <b>【完成】</b> 结束本次对账
        <span class="finish-nudge-arrow" aria-hidden="true">→</span>
      </div>
    </div>

    <ExampleCard title="对账操作指引（一步一步来）" subtitle="每一步都可以点“定位”跳到需要操作的位置。">
      <div class="guide">
        <ol class="guide-ol">
          <li>
            <b>生成示例数据（推荐）</b>：点击“一键生成可对账示例”
            <button class="btn mini" @click="jumpTo(exampleRef)">定位</button>
          </li>
          <li>
            <b>确认对账参数</b>：选择科目、截止日、期末余额（可点“自动填入”）
            <button class="btn mini" @click="jumpTo(createCardRef)">定位</button>
          </li>
          <li>
            <b>选择会话</b>：在会话列表点击状态为 OPEN 的一行
            <button class="btn mini" @click="jumpTo(sessionListRef)">定位</button>
          </li>
          <li>
            <b>勾选分录</b>：点击复选框或双击整行（已完成会话会禁用勾选）
            <button class="btn mini" @click="jumpTo(debitPaneRef)">定位借方</button>
            <button class="btn mini" @click="jumpTo(creditPaneRef)">定位贷方</button>
          </li>
          <li>
            <b>完成</b>：差额为 0 时点击“完成”；差额不为 0 可点击“平衡”自动补差
            <button class="btn mini" @click="jumpTo(toolbarRef)">定位</button>
          </li>
        </ol>
        <div class="muted"><b>当前建议：</b>{{ nextHint }}</div>
      </div>

      <div ref="exampleRef" class="ex-actions">
        <button class="btn primary" :disabled="demo.running" @click="createDemo">一键生成可对账示例</button>
        <span class="muted" v-if="demo.running">正在生成示例数据…</span>
        <span class="muted" v-else>会自动创建“对账示例现金”科目、两笔收支交易，并打开示例对账会话。</span>
      </div>
      <div v-if="demo.msg" class="notice">提示：{{ demo.msg }}</div>
    </ExampleCard>

    <!-- 创建对账会话 + 会话列表 -->
    <div class="top" @click.stop>
      <div ref="createCardRef" class="card">
        <div class="head"><b>新建对账会话</b></div>
        <div class="form">
          <div class="frow"><label>账簿</label><input :value="app.selectedBookName" disabled /></div>
          <div class="frow">
            <label>科目</label>
            <select v-model="create.account_id">
              <option value="">请选择</option>
              <option v-for="a in flatAccounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</option>
            </select>
          </div>
          <div class="frow"><label>截止日</label><input v-model="create.statement_date" placeholder="YYYY-MM-DD" /></div>
          <div class="frow">
            <label>期末余额</label>
            <div class="row-inline">
              <input v-model="create.ending_balance" />
              <button class="btn" :disabled="!create.account_id" @click="autoFillEnding">自动填入</button>
            </div>
          </div>
        </div>
        <div class="foot">
          <button class="btn primary" :disabled="creating" @click="createSession">开始对账</button>
          <button class="btn" @click="load">刷新</button>
        </div>
        <div v-if="error" class="notice">提示：{{ error }}</div>
        </div>

      <div ref="sessionListRef" class="card">
        <div class="head"><b>会话列表</b></div>
        <table class="table">
          <thead><tr><th>日期</th><th>科目</th><th>状态</th></tr></thead>
          <tbody>
            <tr v-for="s in sessions" :key="s.id" :class="{ active: s.id === selectedSessionId }" @click="selectSession(s.id)">
              <td>{{ s.statement_date }}</td>
              <td>{{ nameOf(s.account_id) }}</td>
              <td>{{ s.status }}</td>
            </tr>
            <tr v-if="!sessions.length"><td colspan="3" class="muted">暂无会话</td></tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 借/贷双栏对账（对齐最后一张图） -->
    <div v-if="detail" class="recon" @click.stop>
      <div class="recon-head">
        <div class="title">
          <b>对账：{{ nameOf(detail.session.account_id) }}</b>
          <span class="muted">截至 {{ detail.session.statement_date }} | 期末余额 {{ fmt(detail.session.ending_balance) }}</span>
        </div>
        <div class="sum">
          <span>已选借方：{{ fmt(selectedDebit) }}</span>
          <span>已选贷方：{{ fmt(selectedCredit) }}</span>
          <span><b>已选合计：{{ fmt(selectedTotalSigned) }}</b></span>
          <span :class="{ bad: !almostZero(differenceNow) }"><b>差额：{{ fmt(differenceNow) }}</b></span>
        </div>
        </div>

      <div class="two">
        <div ref="debitPaneRef" class="pane">
          <div class="pane-head"><b>借方</b></div>
          <table class="table small">
            <thead><tr><th></th><th>日期</th><th>编号</th><th>描述</th><th class="right">金额</th></tr></thead>
            <tbody>
              <tr
                v-for="it in debitItems"
                :key="it.split_id"
                :class="{ active: activeSplitId === it.split_id }"
                @click="setActive(it)"
                @dblclick="toggle(it)"
              >
                <td>
                  <input
                    type="checkbox"
                    :checked="!!it.selected"
                    :disabled="!detailIsOpen"
                    :title="!detailIsOpen ? '该会话已完成，无法再勾选' : ''"
                    @click.stop.prevent="toggleCheck(it)"
                  />
                </td>
                <td>{{ it.txn_date }}</td>
                <td>{{ it.txn_num }}</td>
                <td class="ellipsis">{{ it.description }}</td>
                <td class="right mono">{{ fmt(absNorm(it)) }}</td>
              </tr>
              <tr v-if="!debitItems.length">
                <td colspan="5" class="muted">
                  暂无借方候选。可尝试：调整“截止日”到交易日期当天、或点击上方“一键生成可对账示例”创建两笔收支。
                </td>
              </tr>
            </tbody>
          </table>
      </div>

        <div ref="creditPaneRef" class="pane">
          <div class="pane-head"><b>贷方</b></div>
          <table class="table small">
            <thead><tr><th></th><th>日期</th><th>编号</th><th>描述</th><th class="right">金额</th></tr></thead>
        <tbody>
              <tr
                v-for="it in creditItems"
                :key="it.split_id"
                :class="{ active: activeSplitId === it.split_id }"
                @click="setActive(it)"
                @dblclick="toggle(it)"
              >
                <td>
                  <input
                    type="checkbox"
                    :checked="!!it.selected"
                    :disabled="!detailIsOpen"
                    :title="!detailIsOpen ? '该会话已完成，无法再勾选' : ''"
                    @click.stop.prevent="toggleCheck(it)"
                  />
                </td>
            <td>{{ it.txn_date }}</td>
            <td>{{ it.txn_num }}</td>
                <td class="ellipsis">{{ it.description }}</td>
                <td class="right mono">{{ fmt(absNorm(it)) }}</td>
          </tr>
              <tr v-if="!creditItems.length">
                <td colspan="5" class="muted">
                  暂无贷方候选。可尝试：调整“截止日”到交易日期当天、或点击上方“一键生成可对账示例”创建两笔收支。
                </td>
              </tr>
        </tbody>
      </table>
        </div>
      </div>
    </div>

    <!-- 平衡分录弹窗：生成草稿 -> 审批 -> 过账（把差额补齐到 0） -->
    <div v-if="balance.show" class="modal" @click="balance.show = false">
      <div class="modal-card" @click.stop>
        <div class="modal-head">
          <b>对账平衡分录</b>
          <button class="btn" @click="balance.show = false">关闭</button>
        </div>
        <div class="form">
          <div class="muted">
            当前差额：<b>{{ fmt(detail?.difference || 0) }}</b>（将生成一张两行草稿并自动审批+过账）
          </div>
          <div class="frow">
            <label>对方科目</label>
            <select v-model="balance.counter_account_id">
              <option value="">请选择</option>
              <option v-for="a in flatAccounts" :key="a.id" :value="a.id">{{ a.code }} {{ a.name }}</option>
            </select>
          </div>
          <div class="frow">
            <label>摘要</label>
            <input v-model="balance.memo" />
          </div>
        </div>
        <div class="modal-foot">
          <button class="btn primary" :disabled="balancing || !balance.counter_account_id || !detail" @click="doBalance">
            生成并过账
          </button>
        </div>
        <div v-if="balance.error" class="notice">提示：{{ balance.error }}</div>
      </div>
    </div>

    <div v-if="successMsg" class="notice">提示：{{ successMsg }}</div>

    <!-- 成功弹窗已统一为全局 Toast（AppToast） -->
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '../../stores/app'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'
import { useToastStore } from '../../stores/toast'

const app = useAppStore()
const route = useRoute()
const router = useRouter()
const toast = useToastStore()

const flatAccounts = ref<Array<{ id: string; code: string; name: string; type: string }>>([])
const sessions = ref<any[]>([])
const selectedSessionId = ref('')
const detail = ref<any | null>(null)
const detailIsOpen = computed(() => String(detail.value?.session?.status || '') === 'OPEN')
const successMsg = ref('')
// 兼容：successMsg 仅用于页面内的文字提示；弹窗统一用全局 Toast

// 指引定位用 refs（点击“定位”会滚动并高亮）
const toolbarRef = ref<HTMLElement | null>(null)
const exampleRef = ref<HTMLElement | null>(null)
const createCardRef = ref<HTMLElement | null>(null)
const sessionListRef = ref<HTMLElement | null>(null)
const debitPaneRef = ref<HTMLElement | null>(null)
const creditPaneRef = ref<HTMLElement | null>(null)
const finishBtnRef = ref<HTMLElement | null>(null)
const finishNudge = reactive<{ show: boolean; _t?: number }>({ show: false, _t: undefined })

function flash(el: HTMLElement) {
  el.classList.remove('flash')
  // 强制重绘，确保重复点击也能触发动画
  void el.offsetWidth
  el.classList.add('flash')
  window.setTimeout(() => el.classList.remove('flash'), 1200)
}
function jumpTo(target: HTMLElement | null | { value: HTMLElement | null }) {
  const el: HTMLElement | null = (target as any)?.value ?? (target as any)
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth', block: 'center' })
  flash(el)
}

function maybeShowFinishNudge() {
  // 仅在会话 OPEN 且差额为 0 时提示
  if (!detailIsOpen.value) {
    finishNudge.show = false
    return
  }
  if (!detail.value) {
    finishNudge.show = false
    return
  }
  // 有选中的分录，且差额为 0
  if ((detail.value?.items || []).some((x: any) => x.selected) && almostZero(differenceNow.value)) {
    if (finishNudge._t) window.clearTimeout(finishNudge._t)
    finishNudge.show = true
    // 6 秒后自动收起（不打扰），再次达到差额为 0 会重新出现
    finishNudge._t = window.setTimeout(() => {
      finishNudge.show = false
    }, 6000)
  } else {
    finishNudge.show = false
  }
}

const creating = ref(false)
const finishing = ref(false)
const error = ref('')

const activeSplitId = ref('')
const activeItem = computed(() => (detail.value?.items || []).find((x: any) => x.split_id === activeSplitId.value) || null)

const create = ref<any>({
  account_id: '',
  statement_date: new Date().toISOString().slice(0, 10),
  ending_balance: '0',
})

const demo = reactive({ running: false, msg: '' })

type MenuItem = {
  label: string
  action?: 'home' | 'refresh' | 'finish' | string
  to?: string
  hotkey?: string
  disabled?: boolean
}
type MenuDef = { label: string; items: MenuItem[] }

const openMenuLabel = ref<string>('')
const menus: MenuDef[] = [
  {
    label: '对账(R)',
    items: [
      { label: '刷新', action: 'refresh' },
      { label: '完成', action: 'finish', hotkey: 'Ctrl+Enter' },
    ],
  },
  { label: '科目(A)', items: [{ label: '返回科目树', action: 'home' }] },
  { label: '交易(T)', items: [{ label: '打开待过账…', to: '/gl/drafts' }] },
  { label: '帮助(H)', items: [{ label: '关于（占位）', disabled: true }] },
]

function toggleMenu(label: string) {
  openMenuLabel.value = openMenuLabel.value === label ? '' : label
}
async function onMenuClick(it: any) {
  if (it.disabled) return
  openMenuLabel.value = ''
  if (it.to) return await router.push(it.to)
  if (it.action === 'home') return await router.push('/home-tree')
  if (it.action === 'refresh') return await load()
  if (it.action === 'finish') return await finish()
}

function flatten(nodes: any[]): any[] {
  const out: any[] = []
  for (const n of nodes || []) {
    out.push(n)
    if (n.children?.length) out.push(...flatten(n.children))
  }
  return out
}
function nameOf(id: string) {
  return flatAccounts.value.find((x) => x.id === id)?.name || id
}
function typeOf(id: string) {
  return flatAccounts.value.find((x) => x.id === id)?.type || ''
}

function pickByCode(code: string) {
  return flatAccounts.value.find((x) => x.code === code)
}

async function load() {
  error.value = ''
  if (!app.books.length) await app.init()
  if (!app.selectedBookId) return
  await app.reloadPeriods()
  const tree = await api.getAccountsTree(app.selectedBookId)
  flatAccounts.value = flatten(tree).map((x: any) => ({ id: x.id, code: x.code, name: x.name, type: x.type }))

  const qAccountId = String((route.query as any)?.account_id || '')
  if (qAccountId && !create.value.account_id) create.value.account_id = qAccountId

  sessions.value = await api.listReconcileSessions(app.selectedBookId, qAccountId || undefined)
  // 若之前选中的会话已不存在（或被筛掉），避免继续请求详情造成“莫名报错”
  if (selectedSessionId.value && !sessions.value.find((s: any) => s.id === selectedSessionId.value)) {
    selectedSessionId.value = ''
    detail.value = null
    activeSplitId.value = ''
  }
  if (selectedSessionId.value) {
    detail.value = await api.getReconcileSession(selectedSessionId.value)
    if (!activeSplitId.value && (detail.value?.items || []).length) activeSplitId.value = detail.value.items[0].split_id
  }
}

async function createSession() {
  creating.value = true
  error.value = ''
  try {
    if (!app.selectedBookId) throw new Error('请先选择账簿')
    if (!create.value.account_id) throw new Error('请先选择科目')
    if (!create.value.statement_date) throw new Error('请填写截止日')
    const eb = Number(create.value.ending_balance)
    if (!Number.isFinite(eb)) throw new Error('请填写期末余额（数字）')
    const payload = {
      book_id: app.selectedBookId,
      account_id: create.value.account_id,
      statement_date: create.value.statement_date,
      ending_balance: eb,
    }
    const s = await api.createReconcileSession(payload)
    await load()
    await selectSession(s.id)
  } catch (e: any) {
    const msg = e?.message || String(e)
    error.value = msg
  } finally {
    creating.value = false
  }
}

async function selectSession(id: string) {
  selectedSessionId.value = id
  detail.value = await api.getReconcileSession(id)
  activeSplitId.value = (detail.value?.items || [])[0]?.split_id || ''
}

async function toggle(it: any) {
  if (!selectedSessionId.value) return
  if (!detailIsOpen.value) return
  // 双击行：走同一套“设定选中状态”的逻辑
  await setSelected(it, !it.selected)
}

function toggleCheck(it: any) {
  if (!detailIsOpen.value) return
  void setSelected(it, !it.selected)
}

async function setSelected(it: any, selected: boolean) {
  if (!selectedSessionId.value) return
  if (!detailIsOpen.value) return
  successMsg.value = ''
  error.value = ''
  const before = !!it.selected
  it.selected = selected
  try {
    const next = await api.toggleReconcile(selectedSessionId.value, it.split_id, selected)
    detail.value = next
    activeSplitId.value = (detail.value?.items || []).find((x: any) => x.split_id === it.split_id)?.split_id || activeSplitId.value
    maybeShowFinishNudge()
  } catch (e: any) {
    it.selected = before
    error.value = e?.message || '操作未完成，请稍后重试。'
  }
}

function setActive(it: any) {
  activeSplitId.value = it.split_id
}

function nextHintText() {
  if (!app.selectedBookId) return '先在顶部选择账簿'
  if (!create.value.account_id) return '在“新建对账会话”里先选择科目（建议用“一键生成可对账示例”自动带入）'
  if (!selectedSessionId.value) return '在右侧“会话列表”里点击一行（建议选 OPEN）'
  if (!detail.value) return '请先选择会话'
  if (!detailIsOpen.value) return '当前会话已完成（FINISHED），请新建一个 OPEN 会话继续对账'
  const anyItems = (detail.value?.items || []).length > 0
  if (!anyItems) return '借/贷栏暂无候选：请调整截止日或点“一键生成可对账示例”'
  if (almostZero(differenceNow.value)) return '差额已为 0：点击顶部工具栏“完成”即可'
  return '请继续勾选分录直到差额为 0；或点击“平衡”自动补差'
}
const nextHint = computed(() => nextHintText())

async function autoFillEnding() {
  error.value = ''
  try {
    if (!create.value.account_id) throw new Error('请先选择科目')
    const reg = await api.getRegister(create.value.account_id)
    const asof = String(create.value.statement_date || '')
    if (!asof) throw new Error('请先填写截止日')
    const accType = String(typeOf(create.value.account_id) || '').toUpperCase()
    const creditTypes = new Set(['LIABILITY', 'EQUITY', 'INCOME', 'AP'])
    const sum = (reg.items || [])
      .filter((x: any) => x.reconcile_state !== 'y' && String(x.txn_date || '') <= asof)
      .reduce((s: number, x: any) => {
        const v = Number(x.value || 0)
        return s + (creditTypes.has(accType) ? -v : v)
      }, 0)
    create.value.ending_balance = String((sum || 0).toFixed(2))
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

async function finish() {
  if (!selectedSessionId.value) return
  finishing.value = true
  error.value = ''
  try {
    await api.finishReconcile(selectedSessionId.value)
    detail.value = await api.getReconcileSession(selectedSessionId.value)
    await load()
    finishNudge.show = false
    // 对账成功：延时 1 秒弹出，展示 1 秒
    toast.success('对账成功', { delayMs: 1000, durationMs: 1000, scale: 3 })
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    finishing.value = false
  }
}

const CREDIT_TYPES = new Set(['LIABILITY', 'EQUITY', 'INCOME', 'AP'])
function normValue(item: any) {
  const t = typeOf(detail.value?.session?.account_id || '')
  const v = Number(item.value || 0)
  if (CREDIT_TYPES.has(String(t || '').toUpperCase())) return -v
  return v
}
function absNorm(item: any) {
  return Math.abs(normValue(item))
}
const debitItems = computed(() => (detail.value?.items || []).filter((x: any) => normValue(x) >= 0))
const creditItems = computed(() => (detail.value?.items || []).filter((x: any) => normValue(x) < 0))
const selectedDebit = computed(() => debitItems.value.filter((x: any) => x.selected).reduce((s: number, x: any) => s + absNorm(x), 0))
const selectedCredit = computed(() => creditItems.value.filter((x: any) => x.selected).reduce((s: number, x: any) => s + absNorm(x), 0))

// 让“已选合计/差额”始终实时可见（不依赖后端返回字段是否刷新）
const selectedTotalSigned = computed(() =>
  (detail.value?.items || []).filter((x: any) => x.selected).reduce((s: number, x: any) => s + Number(normValue(x) || 0), 0),
)
const differenceNow = computed(() => {
  const eb = Number(detail.value?.session?.ending_balance || 0)
  return eb - selectedTotalSigned.value
})

const canFinish = computed(() => !!detail.value && detailIsOpen.value && !finishing.value && almostZero(differenceNow.value))
const finishHint = computed(() => {
  if (!detail.value) return '请先选择一个对账会话'
  if (!detailIsOpen.value) return '该会话已完成，无法再次完成'
  if (!almostZero(differenceNow.value)) return '差额不为 0，无法完成（请继续勾选或点“平衡”）'
  return ''
})

function fmt(v: any) {
  const n = Number(v)
  const num = Number.isFinite(n) ? n : Number(String(v || 0))
  return `¥${(num || 0).toFixed(2)}`
}
function almostZero(v: any) {
  return Math.abs(Number(v || 0)) <= 0.01
}

async function toggleActive(selected: boolean) {
  if (!activeItem.value || !selectedSessionId.value) return
  if (!detailIsOpen.value) return
  await setSelected(activeItem.value, selected)
}

async function openTxn() {
  if (!activeItem.value) return
  // 先给一个稳定入口：跳到报表页（后续可做“交易详情弹窗”）
  await router.push(`/reports`)
}

async function createDemo() {
  demo.running = true
  demo.msg = ''
  try {
    if (!app.books.length) await app.init()
    if (!app.selectedBookId) throw new Error('请先选择账簿')
    await app.reloadPeriods()
    const periodId = app.selectedPeriodId || app.periods?.[0]?.id
    if (!periodId) throw new Error('缺少会计期间，请先初始化期间')
    if (!app.selectedPeriodId) app.selectedPeriodId = periodId

    // 确保 flatAccounts 已加载（用于查找/创建科目）
    if (!flatAccounts.value.length) {
      const tree = await api.getAccountsTree(app.selectedBookId)
      flatAccounts.value = flatten(tree).map((x: any) => ({ id: x.id, code: x.code, name: x.name, type: x.type }))
    }

    const assets = pickByCode('1000')
    const capital = pickByCode('3001')
    const fee = pickByCode('5001')
    if (!assets) throw new Error('找不到资产类父科目(1000)，请先初始化科目树')
    if (!capital || !fee) throw new Error('找不到示例用科目(3001/5001)，请先初始化科目树')

    // 创建/复用“对账示例现金”科目（避免污染 1001 库存现金的历史数据）
    let demoAcc = flatAccounts.value.find((x) => x.code === '1099') || flatAccounts.value.find((x) => x.name === '对账示例现金')
    if (!demoAcc) {
      const b = app.books.find((x) => x.id === app.selectedBookId)
      const commodityId = b?.base_currency_id
      if (!commodityId) throw new Error('缺少本位币信息')
      const basePayload: any = {
        book_id: app.selectedBookId,
        parent_id: assets.id,
        name: '对账示例现金',
        description: '用于演示对账功能（可安全删除）',
        type: 'CASH',
        commodity_id: commodityId,
        allow_post: true,
        is_active: true,
        is_hidden: false,
        is_placeholder: false,
      }
      // 可能存在隐藏同码/并发创建导致的冲突：自动换一个新 code，避免用户看到“服务不可用”
      let created: any | null = null
      const codes = ['1099', `D${String(Date.now()).slice(-6)}`]
      for (const c of codes) {
        try {
          created = await api.createAccount({ ...basePayload, code: c })
          break
        } catch {
          // 继续尝试下一个 code
        }
      }
      if (!created) throw new Error('示例科目创建失败，请稍后重试')
      demoAcc = { id: created.id, code: created.code, name: created.name, type: created.type }
      flatAccounts.value.push(demoAcc)
    }

    // 生成两笔已过账交易：收款 + 支出（确保借/贷两栏都有候选）
    const today = new Date().toISOString().slice(0, 10)

    // 用户友好：先清理旧示例（只清理“对账示例：”开头的分录，避免越点越多导致列表爆炸）
    try {
      const reg0 = await api.getRegister(demoAcc.id)
      const olds = (reg0.items || []).filter((x: any) => String(x.description || '').includes('对账示例：') && x.reconcile_state !== 'y')
      for (const x of olds) {
        await api.setSplitReconcile(x.split_id, 'y')
      }
    } catch {
      // 清理失败不阻塞示例生成
    }

    const pay1 = {
      book_id: app.selectedBookId,
      period_id: app.selectedPeriodId,
      // 双保险：让交易时间落在截止日当天 00:00，避免后端按“截止日”过滤时把当天交易排除
      txn_date: `${today}T00:00:00`,
      description: `对账示例：收到投入资本 1000（用于对账）`,
      lines: [
        { account_id: demoAcc.id, debit: 1000, credit: 0, memo: '借：对账示例现金' },
        { account_id: capital.id, debit: 0, credit: 1000, memo: '贷：实收资本' },
      ],
    }
    const pay2 = {
      book_id: app.selectedBookId,
      period_id: app.selectedPeriodId,
      txn_date: `${today}T00:00:00`,
      description: `对账示例：支付房租 200（用于对账）`,
      lines: [
        { account_id: fee.id, debit: 200, credit: 0, memo: '借：管理费用' },
        { account_id: demoAcc.id, debit: 0, credit: 200, memo: '贷：对账示例现金' },
      ],
    }
    const d1 = await api.createDraft(pay1)
    await api.approveDraft(d1.draft_id)
    await api.postDraft(d1.draft_id)
    const d2 = await api.createDraft(pay2)
    await api.approveDraft(d2.draft_id)
    await api.postDraft(d2.draft_id)

    // 用寄存器计算：截止到今天、且未对账(y)的分录合计，作为期末余额（确保能直接“完成”）
    const reg = await api.getRegister(demoAcc.id)
    const eb = (reg.items || [])
      .filter((x: any) => x.reconcile_state !== 'y' && String(x.txn_date || '') <= today)
      .reduce((s: number, x: any) => s + Number(x.value || 0), 0)

    create.value.account_id = demoAcc.id
    create.value.statement_date = today
    create.value.ending_balance = String(eb.toFixed(2))

    const s = await api.createReconcileSession({
      book_id: app.selectedBookId,
      account_id: demoAcc.id,
      statement_date: today,
      ending_balance: eb,
    })
    await load()
    await selectSession(s.id)
    demo.msg = '示例已生成：请在借/贷栏勾选两条分录，差额为 0 后点击“完成”。（也可以故意少选一条，再点“平衡”体验自动补差）'
  } catch (e: any) {
    demo.msg = e?.message || String(e)
  } finally {
    demo.running = false
  }
}

const balance = reactive({ show: false, counter_account_id: '', memo: '对账差额调整', error: '' })
const balancing = ref(false)

function openBalance() {
  balance.error = ''
  balance.show = true
  const prefer = flatAccounts.value.find((x) => x.code === '5001') || flatAccounts.value.find((x) => x.code === '1001')
  if (!balance.counter_account_id && prefer) balance.counter_account_id = prefer.id
}

async function doBalance() {
  if (!detail.value) return
  balancing.value = true
  balance.error = ''
  try {
    if (!app.selectedBookId || !app.selectedPeriodId) throw new Error('缺少账簿/期间')
    // 以“当前前端所见差额”为准（避免后端字段未及时刷新导致按钮逻辑与用户感知不一致）
    const diff = Number(differenceNow.value || 0)
    if (almostZero(diff)) throw new Error('差额已为 0，无需平衡')

    const accId = String(detail.value.session.account_id)
    const accType = String(typeOf(accId) || '').toUpperCase()
    const v1 = CREDIT_TYPES.has(accType) ? -diff : diff
    const line1 = v1 >= 0 ? { debit: v1, credit: 0 } : { debit: 0, credit: -v1 }
    const v2 = -v1
    const line2 = v2 >= 0 ? { debit: v2, credit: 0 } : { debit: 0, credit: -v2 }

    const payload = {
      book_id: app.selectedBookId,
      period_id: app.selectedPeriodId,
      description: balance.memo,
      lines: [
        { account_id: accId, ...line1, memo: `${balance.memo}（对账科目）` },
        { account_id: balance.counter_account_id, ...line2, memo: `${balance.memo}（对方科目）` },
      ],
    }
    const r = await api.createDraft(payload)
    await api.approveDraft(r.draft_id)
    await api.postDraft(r.draft_id)
    balance.show = false
    await selectSession(selectedSessionId.value)
    maybeShowFinishNudge()
  } catch (e: any) {
    balance.error = e?.message || String(e)
  } finally {
    balancing.value = false
  }
}

function onDocClick() {
  openMenuLabel.value = ''
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))

onMounted(load)
</script>

<style scoped>
.window {
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
  background: #fff;
}
.menubar {
  display: flex;
  gap: 10px;
  align-items: center;
  padding: 6px 10px;
  border-bottom: 1px solid #e5e7eb;
  background: linear-gradient(#fafafa, #f3f4f6);
  user-select: none;
}
.menu {
  position: relative;
}
.menu-label {
  padding: 4px 8px;
  border-radius: 6px;
  cursor: default;
}
.menu-label.active {
  background: #e5e7eb;
}
.menu-pop {
  position: absolute;
  top: 26px;
  left: 0;
  min-width: 220px;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 6px;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12);
  z-index: 1000;
}
.menu-item {
  display: flex;
  justify-content: space-between;
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.menu-item:hover {
  background: #f2f4f7;
}
.menu-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.hotkey {
  color: #6b7280;
  font-size: 12px;
}
.spacer {
  flex: 1;
}

.toolbar {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}
.tool {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  border: 1px solid #e5e7eb;
  background: white;
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
}
.tool.primary {
  background: #111827;
  color: white;
  border-color: #111827;
}
.tool:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.top {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}
.card {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
}
.head {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
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
}
.table th,
.table td {
  border-bottom: 1px solid #eee;
  padding: 10px;
  text-align: left;
  font-size: 14px;
}
.table tr.active {
  background: #f8fafc;
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
.ex-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.row-inline {
  display: flex;
  gap: 8px;
  align-items: center;
}
.finish-nudge {
  padding: 0 12px;
  margin-top: 8px;
}
.finish-nudge-inner {
  border: 2px solid #fb7185;
  background: linear-gradient(135deg, #fff1f2, #ffe4e6);
  color: #9f1239;
  border-radius: 16px;
  padding: 10px 12px;
  display: flex;
  gap: 10px;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  user-select: none;
  box-shadow: 0 16px 40px rgba(251, 113, 133, 0.22);
  animation: nudgePulse 1.1s ease-in-out infinite;
}
.finish-nudge-dot {
  width: 10px;
  height: 10px;
  border-radius: 999px;
  background: #fb7185;
  box-shadow: 0 0 0 6px rgba(251, 113, 133, 0.18);
}
.finish-nudge-arrow {
  font-weight: 900;
  font-size: 16px;
  animation: nudgeMove 0.9s ease-in-out infinite;
}
@keyframes nudgePulse {
  0% {
    transform: translateY(0);
    filter: saturate(1);
  }
  50% {
    transform: translateY(-2px);
    filter: saturate(1.15);
  }
  100% {
    transform: translateY(0);
    filter: saturate(1);
  }
}
@keyframes nudgeMove {
  0%,
  100% {
    transform: translateX(0);
  }
  50% {
    transform: translateX(6px);
  }
}
.btn.mini {
  padding: 4px 8px;
  border-radius: 10px;
  font-size: 12px;
}
.guide {
  border: 1px solid #e5e7eb;
  background: #f8fafc;
  border-radius: 12px;
  padding: 10px 12px;
  margin-bottom: 10px;
}
.guide-ol {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 6px;
  font-size: 13px;
}
.flash {
  outline: 3px solid #2563eb;
  box-shadow: 0 0 0 6px rgba(37, 99, 235, 0.14);
  border-radius: 14px;
  transition: box-shadow 0.2s ease;
}
input[type='checkbox'] {
  width: 16px;
  height: 16px;
  cursor: pointer;
}
input,
select {
  border: 1px solid #ddd;
  padding: 6px 10px;
  border-radius: 10px;
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
.foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
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

.recon {
  padding: 12px;
}
.recon-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: end;
  margin-bottom: 10px;
}
.sum {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 12px;
  color: #374151;
}
.sum .bad {
  color: #b42318;
}
.two {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.pane {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 10px;
}
.pane-head {
  margin-bottom: 8px;
}
.table.small th,
.table.small td {
  padding: 8px;
  font-size: 13px;
}
.right {
  text-align: right;
}
.mono {
  font-variant-numeric: tabular-nums;
}
.ellipsis {
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.table tr.active {
  background: #1d4ed8;
  color: white;
}
.table tr.active td {
  border-bottom-color: rgba(255, 255, 255, 0.18);
}

.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: grid;
  place-items: center;
  padding: 16px;
  z-index: 2000;
}
.modal-card {
  width: min(720px, 96vw);
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
.modal-foot {
  display: flex;
  justify-content: flex-end;
  margin-top: 10px;
}
</style>