import { createRouter, createWebHistory } from 'vue-router'
import LoginView from '../views/LoginView.vue'
import HealthView from '../views/HealthView.vue'
import DashboardLayout from '../layouts/DashboardLayout.vue'
import DashboardView from '../views/DashboardView.vue'
import HomeTreeView from '../views/HomeView.vue'
import DraftListView from '../views/gl/DraftListView.vue'
import DraftDetailView from '../views/gl/DraftDetailView.vue'
import AccountsView from '../views/gl/AccountsView.vue'
import ReportsView from '../views/reports/ReportsView.vue'
import ReportSnapshotView from '../views/reports/ReportSnapshotView.vue'
import PartiesView from '../views/business/PartiesView.vue'
import PurchaseOrdersView from '../views/business/PurchaseOrdersView.vue'
import SalesOrdersView from '../views/business/SalesOrdersView.vue'
import ExpenseClaimsView from '../views/business/ExpenseClaimsView.vue'
import BusinessDocumentDetailView from '../views/business/BusinessDocumentDetailView.vue'
import ScheduledView from '../views/tools/ScheduledView.vue'
import ReconcileView from '../views/treasury/ReconcileView.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    {
      path: '/',
      component: DashboardLayout,
      children: [
        { path: '', redirect: '/home' },
        // 新主页（原“仪表盘”）
        { path: 'home', component: DashboardView },
        // 兼容旧链接
        { path: 'dashboard', redirect: '/home' },
        { path: 'health', component: HealthView },
        // 旧主页（桌面风格科目树）：保留为“科目树（旧版）”，避免功能回归
        { path: 'home-tree', component: HomeTreeView },
        { path: 'gl/drafts', component: DraftListView },
        { path: 'gl/drafts/:id', component: DraftDetailView, props: true },
        { path: 'gl/accounts', component: AccountsView },
        { path: 'business/parties', component: PartiesView },
        { path: 'business/purchase-orders', component: PurchaseOrdersView },
        { path: 'business/sales-orders', component: SalesOrdersView },
        { path: 'business/expense-claims', component: ExpenseClaimsView },
        { path: 'business/documents/:id', component: BusinessDocumentDetailView, props: true },
        { path: 'tools/scheduled', component: ScheduledView },
        { path: 'treasury/reconcile', component: ReconcileView },
        { path: 'reports', component: ReportsView },
        { path: 'reports/:id', component: ReportSnapshotView, props: true },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  if (to.path === '/login') return true
  const token = localStorage.getItem('token') || ''
  if (!token) return `/login?next=${encodeURIComponent(to.fullPath)}`
  return true
})


