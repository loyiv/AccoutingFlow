<template>
  <div class="shell" :style="{ gridTemplateColumns: collapsed ? '72px 1fr' : '260px 1fr' }">
    <aside class="sidebar" :class="{ collapsed }">
      <div class="logo" @click="go('/home')">
        <div class="mark">AF</div>
        <div v-if="!collapsed" class="name">AccountingFlow</div>
      </div>

      <nav class="nav" aria-label="主导航">
        <div class="group">
          <div v-if="!collapsed" class="group-title">工作台</div>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/home') }"
            :title="collapsed ? '主页' : ''"
            @click="go('/home')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">主页</span>
          </button>
        </div>

        <div class="group">
          <div v-if="!collapsed" class="group-title">总账</div>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/gl/accounts') }"
            :title="collapsed ? '科目与寄存器' : ''"
            @click="go('/gl/accounts')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">科目与寄存器</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/home-tree') }"
            :title="collapsed ? '科目树（旧版）' : ''"
            @click="go('/home-tree')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">科目树（旧版）</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/gl/drafts') }"
            :title="collapsed ? '待过账' : ''"
            @click="go('/gl/drafts')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">待过账</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/treasury/reconcile') }"
            :title="collapsed ? '对账' : ''"
            @click="go('/treasury/reconcile')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">对账</span>
          </button>
        </div>

        <div class="group">
          <div v-if="!collapsed" class="group-title">报表与工具</div>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/reports') }"
            :title="collapsed ? '报表' : ''"
            @click="go('/reports')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">报表</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/tools/scheduled') }"
            :title="collapsed ? '定期交易' : ''"
            @click="go('/tools/scheduled')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">定期交易</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/health') }"
            :title="collapsed ? '自检' : ''"
            @click="go('/health')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">自检</span>
          </button>
        </div>

        <div class="group">
          <div v-if="!collapsed" class="group-title">企业</div>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/business/parties') }"
            :title="collapsed ? '往来单位' : ''"
            @click="go('/business/parties')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">往来单位</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/business/purchase-orders') }"
            :title="collapsed ? '采购' : ''"
            @click="go('/business/purchase-orders')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">采购</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/business/sales-orders') }"
            :title="collapsed ? '销售' : ''"
            @click="go('/business/sales-orders')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">销售</span>
          </button>
          <button
            class="item"
            type="button"
            :class="{ active: isActive('/business/expense-claims') }"
            :title="collapsed ? '报销' : ''"
            @click="go('/business/expense-claims')"
          >
            <span class="dot"></span>
            <span v-if="!collapsed" class="label">报销</span>
          </button>
        </div>
      </nav>

      <div class="side-bottom">
        <button class="collapse" @click="collapsed = !collapsed">{{ collapsed ? '›' : '‹' }}</button>
      </div>
    </aside>

    <section class="main">
      <header class="topbar">
        <div class="left">
          <div class="title">{{ title }}</div>
          <div class="sub muted">{{ subtitle }}</div>
        </div>
        <div class="right">
          <div class="me">
            <div class="me-name">{{ auth.me?.username || '—' }}</div>
            <div class="me-role muted">{{ auth.me?.role || '' }}</div>
          </div>
          <button class="btn" @click="logout">退出</button>
        </div>
      </header>

      <main class="content">
        <RouterView />
      </main>
    </section>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const app = useAppStore()

const collapsed = ref(false)

function isActive(prefix: string) {
  return route.path === prefix || route.path.startsWith(prefix + '/')
}
async function go(path: string) {
  await router.push(path)
}
async function logout() {
  auth.logout()
  await router.push('/login')
}

const title = computed(() => {
  const p = route.path
  if (p === '/home') return '主页'
  if (p.startsWith('/home-tree')) return '科目树（旧版）'
  if (p.startsWith('/gl/accounts')) return '科目与寄存器'
  if (p.startsWith('/gl/drafts')) return '待过账'
  if (p.startsWith('/treasury/reconcile')) return '对账'
  if (p.startsWith('/reports')) return '报表'
  if (p.startsWith('/tools/scheduled')) return '定期交易'
  if (p.startsWith('/business/')) return '企业'
  if (p.startsWith('/health')) return '自检'
  return 'AccountingFlow'
})
const subtitle = computed(() => {
  if (!app.selectedBookId) return '请选择账簿后开始'
  return `账簿：${app.selectedBookName} · 期间：${app.selectedPeriodLabel}`
})

onMounted(async () => {
  if (auth.token && !app.books.length) {
    // 只要登录态存在，就尽早加载账簿/期间，供顶部栏展示与页面使用
    await app.init().catch(() => void 0)
  }
  if (auth.token && !auth.me) {
    await auth.loadMe().catch(() => void 0)
  }
})
</script>

<style scoped>
.shell {
  min-height: 100vh;
  display: grid;
  background: transparent;
  font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
}
.sidebar {
  background: linear-gradient(180deg, #0b1b3a 0%, #08122a 100%);
  color: rgba(241, 245, 249, 0.95);
  border-right: 1px solid rgba(147, 197, 253, 0.18);
  display: grid;
  grid-template-rows: auto 1fr auto;
}
.sidebar.collapsed {
  width: 72px;
}
.logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 14px 14px;
  cursor: pointer;
  user-select: none;
}
.mark {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  background: linear-gradient(135deg, var(--primary-600), var(--primary-400));
  font-weight: 800;
  color: #fff;
}
.name {
  font-weight: 700;
  letter-spacing: 0.2px;
}
.nav {
  padding: 8px;
  overflow: auto;
}
.group {
  margin-bottom: 12px;
}
.group-title {
  font-size: 12px;
  color: rgba(241, 245, 249, 0.62);
  padding: 8px 10px 6px;
}
.item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 10px;
  border-radius: 12px;
  cursor: pointer;
  color: rgba(241, 245, 249, 0.9);
  user-select: none;
  width: 100%;
  text-align: left;
  border: none;
  background: transparent;
}
.item:hover {
  background: rgba(59, 130, 246, 0.14);
}
.item.active {
  background: rgba(59, 130, 246, 0.24);
  outline: 1px solid rgba(147, 197, 253, 0.22);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 99px;
  background: rgba(147, 197, 253, 0.45);
}
.item.active .dot {
  background: #93c5fd;
}
.label {
  font-size: 14px;
}
.side-bottom {
  padding: 10px;
}
.collapse {
  width: 100%;
  border: 1px solid rgba(255, 255, 255, 0.10);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(241, 245, 249, 0.95);
  border-radius: 12px;
  padding: 8px 10px;
  cursor: pointer;
}
.collapse:hover {
  background: rgba(59, 130, 246, 0.16);
  border-color: rgba(147, 197, 253, 0.24);
}

.main {
  background: transparent;
  display: grid;
  grid-template-rows: auto 1fr;
  min-width: 0;
}
.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  background: rgba(255, 255, 255, 0.78);
  backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--primary-100);
}
.title {
  font-size: 16px;
  font-weight: 800;
  color: var(--text);
}
.sub {
  font-size: 12px;
  margin-top: 2px;
}
.right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.me {
  text-align: right;
}
.me-name {
  font-weight: 700;
  color: var(--text);
  font-size: 13px;
}
.me-role {
  font-size: 12px;
}
.btn {
  border: 1px solid var(--primary-200);
  background: rgba(255, 255, 255, 0.92);
  padding: 7px 10px;
  border-radius: 10px;
  cursor: pointer;
  color: var(--primary-900);
}
.btn:hover {
  border-color: var(--primary-300);
  background: #fff;
}
.content {
  padding: 16px 18px;
  min-width: 0;
}
.muted {
  color: var(--muted);
}

/* 蓝色系：统一覆盖子页面里的常用控件（避免每页逐个改） */
:deep(.btn) {
  border: 1px solid var(--primary-200) !important;
  background: rgba(255, 255, 255, 0.92) !important;
  color: var(--primary-900) !important;
  border-radius: 12px !important;
}
:deep(.btn:hover) {
  border-color: var(--primary-300) !important;
  background: #fff !important;
}
:deep(.btn.primary) {
  background: linear-gradient(135deg, var(--primary-600), var(--primary-500)) !important;
  border-color: var(--primary-600) !important;
  color: #fff !important;
  box-shadow: var(--shadow-sm) !important;
}
:deep(.btn.primary:hover) {
  background: linear-gradient(135deg, var(--primary-700), var(--primary-600)) !important;
  border-color: var(--primary-700) !important;
}
:deep(.notice) {
  border: 1px solid var(--primary-200) !important;
  background: var(--primary-50) !important;
  color: var(--primary-900) !important;
}
:deep(.card) {
  border-color: var(--primary-100) !important;
  box-shadow: var(--shadow-sm);
}
:deep(.table th),
:deep(.table td) {
  border-bottom-color: rgba(191, 219, 254, 0.65) !important;
}
:deep(.muted) {
  color: var(--muted) !important;
}

@media (max-width: 960px) {
  .shell {
    grid-template-columns: 72px 1fr;
  }
}
</style>


