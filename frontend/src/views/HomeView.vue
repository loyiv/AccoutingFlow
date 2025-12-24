<template>
  <div class="window">
    <!-- Menu bar -->
    <div class="menubar" @click.stop>
      <!-- 菜单改为“点击展开/收起”，避免 hover 模式下鼠标下移穿过空隙导致菜单瞬间关闭 -->
      <div class="menu" v-for="m in menus" :key="m.label" @click.stop>
        <span class="menu-label" :class="{ active: openMenuLabel === m.label }" @click.stop="toggleMenu(m.label)">{{ m.label }}</span>
        <div v-if="openMenuLabel === m.label" class="menu-pop">
          <div
            v-for="it in m.items"
            :key="it.label"
            class="menu-item"
            :class="{ disabled: isDisabled(it) }"
            @click="onMenuClick(it)"
          >
            <span>{{ it.label }}</span>
            <span class="hotkey">{{ it.hotkey || '' }}</span>
          </div>
        </div>
      </div>
      <div class="spacer"></div>
      <div class="hint muted">提示：右键科目可打开菜单</div>
    </div>

    <!-- Toolbar -->
    <div class="toolbar">
      <button class="tool" @click="go('/gl/drafts')">
        <span>打开</span>
      </button>
      <button class="tool" :disabled="!selectedId" @click="openAccount">
        <span>打开科目</span>
      </button>
      <button class="tool" @click="createAccount">
        <span>新建</span>
      </button>
      <button class="tool" :disabled="!selectedId" @click="editAccount">
        <span>编辑</span>
      </button>
      <button class="tool" @click="refresh">
        <span>刷新</span>
      </button>
    </div>

    <ExampleCard title="操作示例（企业日常）：从科目树进入业务" subtitle="这是旧主页（桌面风格）。你可以用它快速选科目、打开寄存器、进入对账/待过账。">
      <ol class="ol">
        <li>在下方科目表双击“库存现金/银行存款”可快速打开科目详情。</li>
        <li>右键科目选择“对账…”，进入对账页面完成一次对账演示。</li>
        <li>点击工具栏“打开”进入“待过账”，对 seed-1/EC-SEED-1/PO-SEED-1/SO-SEED-1 做审批与过账。</li>
      </ol>
    </ExampleCard>

    <!-- Tabs -->
    <div class="tabs">
      <div class="tab active">科目</div>
    </div>

    <!-- Accounts tree table -->
    <div class="panel">
      <div class="table-head">
        <div>科目名称</div>
        <div>描述</div>
        <div class="right">合计</div>
      </div>

      <div class="table-body" @click="hideCtx">
        <div
          v-for="r in visibleRows"
          :key="r.id"
          class="row"
          :class="{ selected: selectedId === r.id }"
          @click.stop="select(r.id)"
          @dblclick.stop="openAccount"
          @contextmenu.prevent.stop="openCtx($event, r.id)"
        >
          <div class="cell name">
            <span class="indent" :style="{ width: `${r.depth * 16}px` }"></span>
            <span class="tw" @click.stop="toggle(r)" :class="{ clickable: r.hasChildren }">
              {{ r.hasChildren ? (isOpen(r.id) ? '▾' : '▸') : ' ' }}
            </span>
            <span class="acc-ico">◈</span>
            <span class="acc-name">{{ r.name }}</span>
          </div>
          <div class="cell desc">{{ r.description || '' }}</div>
          <div class="cell total right">{{ formatMoney(r.total) }}</div>
        </div>

        <div v-if="!visibleRows.length" class="muted empty">暂无科目数据</div>
      </div>
    </div>

    <!-- Context menu -->
    <div v-if="ctx.show" class="ctx" :style="{ left: `${ctx.x}px`, top: `${ctx.y}px` }" @click.stop>
      <div class="ctx-item" @click="noop('按条件筛选')">按条件筛选…</div>
      <div class="ctx-item" @click="noop('重命名页面')">重命名页面…</div>
      <div class="ctx-sep"></div>
      <div class="ctx-item" :class="{ disabled: !selectedId }" @click="openAccount">打开科目</div>
      <div class="ctx-item" :class="{ disabled: !selectedId }" @click="openSubAccounts">打开子科目</div>
      <div class="ctx-item" :class="{ disabled: !selectedId }" @click="editAccount">编辑科目…</div>
      <div class="ctx-sep"></div>
      <div class="ctx-item" :class="{ disabled: !selectedId }" @click="goReconcile">对账…</div>
      <div class="ctx-item" @click="createAccount">新建科目…</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { api } from '../services/api'
import ExampleCard from '../components/ExampleCard.vue'

type Node = {
  id: string
  name: string
  description: string
  total: string | number
  children: Node[]
}

type Row = {
  id: string
  name: string
  description: string
  total: string | number
  depth: number
  hasChildren: boolean
}

const router = useRouter()
const app = useAppStore()

const tree = ref<Node[]>([])
const selectedId = ref('')
const openSet = reactive(new Set<string>())

const ctx = reactive({ show: false, x: 0, y: 0 })

const openMenuLabel = ref<string>('')
const menus = [
  {
    label: '文件(F)',
    items: [
      { label: '打开待过账…', to: '/gl/drafts' },
      { label: '保存', disabled: true },
      { label: '关闭', to: '/home' },
      { label: '退出', action: 'logout' },
    ],
  },
  {
    label: '编辑(E)',
    items: [
      { label: '新建科目…', action: 'create_account', hotkey: 'Ctrl+N' },
      { label: '编辑科目…', action: 'edit_account', disabled: () => !selectedId.value },
    ],
  },
  {
    label: '查看(V)',
    items: [{ label: '科目/寄存器', to: '/gl/accounts' }],
  },
  {
    label: '操作(A)',
    items: [
      { label: '对账…', action: 'reconcile', disabled: () => !selectedId.value },
      { label: '定期交易', to: '/tools/scheduled' },
    ],
  },
  {
    label: '企业(B)',
    items: [
      { label: '往来单位', to: '/business/parties' },
      { label: '采购', to: '/business/purchase-orders' },
      { label: '销售', to: '/business/sales-orders' },
      { label: '报销', to: '/business/expense-claims' },
    ],
  },
  {
    label: '报表(R)',
    items: [{ label: '报表', to: '/reports' }],
  },
  {
    label: '工具(T)',
    items: [{ label: '自检', to: '/health' }],
  },
  { label: '帮助(H)', items: [{ label: '关于（占位）', disabled: true }] },
]

function openMenu(label: string) {
  openMenuLabel.value = label
}
function closeMenu() {
  openMenuLabel.value = ''
}
function toggleMenu(label: string) {
  openMenuLabel.value = openMenuLabel.value === label ? '' : label
}
async function onMenuClick(it: any) {
  if (isDisabled(it)) return
  openMenuLabel.value = ''
  if (it.to) return await router.push(it.to)
  if (it.action === 'create_account') return createAccount()
  if (it.action === 'edit_account') return editAccount()
  if (it.action === 'reconcile') return goReconcile()
  if (it.action === 'logout') {
    localStorage.removeItem('token')
    await router.push('/login')
  }
}

function isDisabled(it: any) {
  return typeof it.disabled === 'function' ? !!it.disabled() : !!it.disabled
}

function hideCtx() {
  ctx.show = false
}

function openCtx(ev: MouseEvent, id: string) {
  selectedId.value = id
  ctx.show = true
  ctx.x = ev.clientX
  ctx.y = ev.clientY
}

function select(id: string) {
  selectedId.value = id
  ctx.show = false
}

function isOpen(id: string) {
  return openSet.has(id)
}

function toggle(r: Row) {
  if (!r.hasChildren) return
  if (openSet.has(r.id)) openSet.delete(r.id)
  else openSet.add(r.id)
}

function flatten(nodes: Node[], depth = 0, out: Row[] = []): Row[] {
  for (const n of nodes) {
    const hasChildren = (n.children?.length || 0) > 0
    out.push({ id: n.id, name: n.name, description: n.description, total: n.total, depth, hasChildren })
    if (hasChildren && openSet.has(n.id)) flatten(n.children, depth + 1, out)
  }
  return out
}

const visibleRows = computed(() => flatten(tree.value, 0, []))

function formatMoney(v: any) {
  const n = Number(v)
  const num = Number.isFinite(n) ? n : Number(String(v || 0))
  try {
    return new Intl.NumberFormat('zh-CN', { style: 'currency', currency: 'CNY' }).format(num || 0)
  } catch {
    return `¥${(num || 0).toFixed(2)}`
  }
}

async function refresh() {
  if (!app.books.length) await app.init()
  await app.reloadPeriods()
  tree.value = await api.getAccountsTree(app.selectedBookId)
  // 默认展开所有第一层
  for (const n of tree.value) openSet.add(n.id)
}

function go(path: string) {
  hideCtx()
  router.push(path)
}

function openAccount() {
  if (!selectedId.value) return
  hideCtx()
  router.push(`/gl/accounts?account_id=${encodeURIComponent(selectedId.value)}`)
}

function openSubAccounts() {
  // 主页当前只展示树，子科目已经在树中；这里做占位，保持菜单结构
  hideCtx()
}

function editAccount() {
  if (!selectedId.value) return
  hideCtx()
  router.push(`/gl/accounts?account_id=${encodeURIComponent(selectedId.value)}&edit=1`)
}

function createAccount() {
  hideCtx()
  const pid = selectedId.value ? `&parent_id=${encodeURIComponent(selectedId.value)}` : ''
  router.push(`/gl/accounts?create=1${pid}`)
}

function goReconcile() {
  if (!selectedId.value) return
  hideCtx()
  router.push(`/treasury/reconcile?account_id=${encodeURIComponent(selectedId.value)}`)
}

function noop(_x: string) {
  hideCtx()
}

onMounted(refresh)

// 点击页面空白处自动关闭菜单（更符合桌面软件交互）
function onDocClick() {
  closeMenu()
  hideCtx()
}
onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
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
.muted {
  color: #6b7280;
  font-size: 12px;
}
.ol {
  margin: 8px 0 0;
  padding-left: 18px;
  color: #0f172a;
  font-size: 13px;
}

.toolbar {
  display: flex;
  gap: 8px;
  padding: 8px 10px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}
.tool {
  display: grid;
  grid-template-columns: 18px 1fr;
  gap: 6px;
  align-items: center;
  border: 1px solid #e5e7eb;
  background: white;
  padding: 6px 10px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 13px;
}
.tool:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.ico {
  width: 18px;
}

.tabs {
  display: flex;
  gap: 8px;
  padding: 8px 10px 0;
  border-bottom: 1px solid #e5e7eb;
  background: #fff;
}
.tab {
  padding: 8px 12px;
  border: 1px solid #e5e7eb;
  border-bottom: none;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  background: #f9fafb;
  font-size: 13px;
}
.tab.active {
  background: #fff;
}

.panel {
  padding: 10px;
}
.table-head {
  display: grid;
  grid-template-columns: 1.2fr 1.4fr 160px;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  background: #f9fafb;
  font-size: 13px;
  font-weight: 600;
}
.table-body {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  margin-top: 8px;
  overflow: hidden;
}
.row {
  display: grid;
  grid-template-columns: 1.2fr 1.4fr 160px;
  gap: 10px;
  padding: 7px 10px;
  border-bottom: 1px solid #f1f5f9;
  font-size: 13px;
}
.row:last-child {
  border-bottom: none;
}
.row.selected {
  background: #1d4ed8;
  color: white;
}
.row.selected .desc,
.row.selected .total,
.row.selected .acc-name {
  color: white;
}
.cell {
  display: flex;
  gap: 6px;
  align-items: center;
}
.indent {
  display: inline-block;
}
.tw {
  width: 16px;
  text-align: center;
  color: #6b7280;
}
.row.selected .tw {
  color: white;
}
.tw.clickable {
  cursor: pointer;
}
.acc-ico {
  width: 14px;
  color: #6b7280;
}
.row.selected .acc-ico {
  color: white;
}
.desc {
  color: #4b5563;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}
.total {
  font-variant-numeric: tabular-nums;
}
.right {
  justify-content: flex-end;
  text-align: right;
}
.empty {
  padding: 12px;
}

.ctx {
  position: fixed;
  width: 220px;
  background: white;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 6px;
  box-shadow: 0 14px 28px rgba(0, 0, 0, 0.18);
  z-index: 100;
}
.ctx-item {
  padding: 7px 10px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
}
.ctx-item:hover {
  background: #f2f4f7;
}
.ctx-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
  pointer-events: none;
}
.ctx-sep {
  height: 1px;
  background: #e5e7eb;
  margin: 6px 0;
}
</style>


