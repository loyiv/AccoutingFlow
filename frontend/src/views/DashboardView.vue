<template>
  <div class="page">
    <section class="hero">
      <div class="hero-bg" aria-hidden="true"></div>
      <div class="hero-inner">
        <div class="hero-left">
          <div class="pill">主页</div>
          <div class="h-title">欢迎回来，{{ auth.me?.username || '用户' }}</div>
          <div class="h-sub">用更少的步骤完成：过账、对账、报表与下钻。</div>

          <div class="kpis">
            <button class="kpi" type="button" @click="go('/gl/drafts')">
              <div class="k">待处理草稿</div>
              <div class="v">{{ stats.draftsTodoText }}</div>
              <div class="s muted">点击进入待过账</div>
            </button>
            <button class="kpi" type="button" @click="go('/treasury/reconcile')">
              <div class="k">未完成对账会话</div>
              <div class="v">{{ stats.reconcileOpenText }}</div>
              <div class="s muted">差额为 0 后记得点完成</div>
            </button>
            <button class="kpi" type="button" @click="go('/reports')">
              <div class="k">报表快照</div>
              <div class="v">{{ stats.snapshotsText }}</div>
              <div class="s muted">ok / stale</div>
            </button>
          </div>
        </div>

        <div class="hero-right">
          <div class="actions">
            <button class="btn primary" @click="go('/gl/accounts')">进入科目</button>
            <button class="btn" @click="go('/gl/drafts')">待过账</button>
            <button class="btn" @click="go('/treasury/reconcile')">对账</button>
            <button class="btn" @click="go('/reports')">报表</button>
          </div>
        </div>
      </div>
    </section>

    <div class="grid">
      <ExampleCard
        title="快速开始（企业日常）"
        subtitle="投入资本 → 采购/销售/报销/定期交易 → 过账 → 对账 → 报表下钻。每一步都有示例按钮。"
      >
        <ol class="ol">
          <li>去“待过账”打开 MANUAL/seed-1：审批 → 过账。</li>
          <li>去“采购/销售/报销/定期交易”点“一键填充示例”，保存并生成草稿，然后审批 → 过账。</li>
          <li>去“对账”完成一次对账（差额=0 后点击完成）。</li>
          <li>去“报表”生成快照并下钻定位到凭证与分录。</li>
        </ol>
      </ExampleCard>

      <section class="card">
        <div class="card-title">快捷操作</div>
        <div class="quick">
          <button class="q" @click="go('/gl/accounts?create=1')">
            <div class="q-title">新建科目</div>
            <div class="q-sub muted">建立科目结构</div>
          </button>
          <button class="q" @click="go('/gl/drafts')">
            <div class="q-title">过账工作台</div>
            <div class="q-sub muted">预校验 → 过账入总账</div>
          </button>
          <button class="q" @click="go('/treasury/reconcile')">
            <div class="q-title">对账</div>
            <div class="q-sub muted">借/贷双栏，差额实时计算</div>
          </button>
          <button class="q" @click="go('/reports')">
            <div class="q-title">报表</div>
            <div class="q-sub muted">三大报表 + 下钻</div>
          </button>
        </div>
      </section>

      <section class="card wide">
        <div class="card-title">最近报表快照</div>
        <div class="snap">
          <div v-for="s in recentSnapshots" :key="s.id" class="snap-row">
            <div class="snap-main">
              <div class="snap-title">{{ s.period }} · {{ s.basis }}</div>
              <div class="snap-sub muted">{{ s.time }}</div>
            </div>
            <div class="snap-status" :class="{ stale: s.is_stale }">{{ s.is_stale ? 'stale' : 'ok' }}</div>
            <button class="btn" @click="go(`/reports/${s.id}`)">查看</button>
          </div>
          <div v-if="!recentSnapshots.length" class="muted">暂无快照。你可以去“报表”点击“生成报表”。</div>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '../stores/app'
import { useAuthStore } from '../stores/auth'
import ExampleCard from '../components/ExampleCard.vue'
import { api } from '../services/api'

const router = useRouter()
const app = useAppStore()
const auth = useAuthStore()

async function go(path: string) {
  await router.push(path)
}

const bookName = computed(() => {
  const b = app.books.find((x) => x.id === app.selectedBookId)
  return b?.name || '—'
})
const periodName = computed(() => {
  const p = app.periods.find((x) => x.id === app.selectedPeriodId)
  if (!p) return '—'
  return `${p.year}-${String(p.month).padStart(2, '0')}（${p.status}）`
})

const stats = reactive({
  draftsTodo: null as number | null,
  reconcileOpen: null as number | null,
  snapshotsOk: null as number | null,
  snapshotsStale: null as number | null,
  draftsTodoText: '—',
  reconcileOpenText: '—',
  snapshotsText: '—',
})

const recentSnapshots = ref<Array<{ id: string; period: string; basis: string; time: string; is_stale: boolean }>>([])

function humanTime(iso: string) {
  // 简洁显示：YYYY-MM-DD HH:mm
  const s = String(iso || '').replace('T', ' ').slice(0, 16)
  return s || '—'
}

async function loadStats() {
  if (!app.selectedBookId) {
    stats.draftsTodo = null
    stats.reconcileOpen = null
    stats.snapshotsOk = null
    stats.snapshotsStale = null
    stats.draftsTodoText = '—'
    stats.reconcileOpenText = '—'
    stats.snapshotsText = '—'
    recentSnapshots.value = []
    return
  }

  // 任何失败都不向用户报错，只显示 “—”
  try {
    const drafts = await api.listDrafts(app.selectedPeriodId || undefined)
    const todo = (drafts || []).filter((d: any) => String(d?.status || '') !== 'POSTED').length
    stats.draftsTodo = todo
    stats.draftsTodoText = String(todo)
  } catch {
    stats.draftsTodo = null
    stats.draftsTodoText = '—'
  }

  try {
    const sessions = await api.listReconcileSessions(app.selectedBookId)
    const open = (sessions || []).filter((s: any) => String(s?.status || '') === 'OPEN').length
    stats.reconcileOpen = open
    stats.reconcileOpenText = String(open)
  } catch {
    stats.reconcileOpen = null
    stats.reconcileOpenText = '—'
  }

  try {
    const snaps = await api.listSnapshots(app.selectedBookId)
    const stale = (snaps || []).filter((s: any) => !!s?.is_stale).length
    const ok = (snaps || []).length - stale
    stats.snapshotsOk = ok
    stats.snapshotsStale = stale
    stats.snapshotsText = `${ok} / ${stale}`
    recentSnapshots.value = (snaps || []).slice(0, 3).map((s: any) => ({
      id: String(s.id),
      period: String(s.period_id || ''),
      basis: String(s.basis_code || ''),
      time: humanTime(String(s.generated_at || '')),
      is_stale: !!s.is_stale,
    }))
  } catch {
    stats.snapshotsOk = null
    stats.snapshotsStale = null
    stats.snapshotsText = '—'
    recentSnapshots.value = []
  }
}

onMounted(() => {
  void loadStats()
})
watch(
  () => [app.selectedBookId, app.selectedPeriodId],
  () => void loadStats(),
)
</script>

<style scoped>
.page {
  width: 100%;
}
.hero {
  position: relative;
  border-radius: 18px;
  overflow: hidden;
  border: 1px solid rgba(191, 219, 254, 0.8);
  background: rgba(255, 255, 255, 0.72);
  backdrop-filter: blur(10px);
  box-shadow: var(--shadow);
  margin-bottom: 14px;
}
.hero-bg {
  position: absolute;
  inset: -40px;
  background: radial-gradient(900px 360px at 18% 20%, rgba(37, 99, 235, 0.32), transparent 60%),
    radial-gradient(900px 360px at 78% 0%, rgba(96, 165, 250, 0.28), transparent 60%),
    radial-gradient(900px 360px at 82% 70%, rgba(29, 78, 216, 0.18), transparent 55%);
  filter: saturate(1.1);
}
.hero-inner {
  position: relative;
  display: grid;
  grid-template-columns: 1.35fr 0.85fr;
  gap: 14px;
  padding: 18px;
}
.hero-left {
  min-width: 0;
}
.pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  font-weight: 800;
  font-size: 12px;
  color: var(--primary-900);
  border: 1px solid rgba(191, 219, 254, 0.9);
  background: rgba(239, 246, 255, 0.8);
}
.h-title {
  margin-top: 10px;
  font-size: 22px;
  font-weight: 900;
  color: var(--text);
  letter-spacing: 0.2px;
}
.h-sub {
  margin-top: 4px;
  color: var(--muted);
  font-size: 13px;
}
.kpis {
  margin-top: 14px;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}
.kpi {
  text-align: left;
  border: 1px solid rgba(191, 219, 254, 0.85);
  background: rgba(255, 255, 255, 0.82);
  border-radius: 14px;
  padding: 12px;
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
}
.kpi:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
  border-color: rgba(147, 197, 253, 0.95);
}
.kpi .k {
  font-size: 12px;
  color: var(--muted);
}
.kpi .v {
  margin-top: 6px;
  font-weight: 950;
  font-size: 22px;
  color: var(--primary-900);
}
.kpi .s {
  margin-top: 6px;
  font-size: 12px;
}
.hero-right {
  display: grid;
  gap: 12px;
  align-content: start;
}
.actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  justify-content: flex-end;
}
.grid {
  display: grid;
  gap: 14px;
  grid-template-columns: 1.4fr 1fr;
  align-items: start;
}
.wide {
  grid-column: 1 / -1;
}
.card-title {
  font-weight: 800;
  color: var(--text);
  margin-bottom: 10px;
}
.quick {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr;
}
.q {
  text-align: left;
  border: 1px solid rgba(191, 219, 254, 0.75);
  background: rgba(255, 255, 255, 0.78);
  border-radius: 14px;
  padding: 12px;
  cursor: pointer;
  transition: transform 0.12s ease, box-shadow 0.12s ease, border-color 0.12s ease;
}
.q:hover {
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
  border-color: rgba(147, 197, 253, 0.95);
}
.q-title {
  font-weight: 800;
  color: var(--text);
  font-size: 14px;
}
.q-sub {
  margin-top: 4px;
  font-size: 12px;
}
.snap {
  display: grid;
  gap: 10px;
}
.snap-row {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 10px;
  align-items: center;
  border: 1px solid rgba(191, 219, 254, 0.6);
  background: rgba(255, 255, 255, 0.76);
  border-radius: 14px;
  padding: 10px 12px;
}
.snap-title {
  font-weight: 800;
  color: var(--text);
}
.snap-sub {
  margin-top: 2px;
  font-size: 12px;
}
.snap-status {
  font-weight: 900;
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(34, 197, 94, 0.35);
  background: rgba(34, 197, 94, 0.10);
  color: rgba(21, 128, 61, 0.95);
  text-transform: uppercase;
}
.snap-status.stale {
  border-color: rgba(245, 158, 11, 0.35);
  background: rgba(245, 158, 11, 0.10);
  color: rgba(146, 64, 14, 0.95);
}
.muted {
  color: var(--muted);
}
.ol {
  margin: 8px 0 0;
  padding-left: 18px;
  color: var(--text);
  font-size: 13px;
}

@media (max-width: 980px) {
  .grid {
    grid-template-columns: 1fr;
  }
  .hero-inner {
    grid-template-columns: 1fr;
  }
  .actions {
    justify-content: flex-start;
  }
  .kpis {
    grid-template-columns: 1fr;
  }
}
</style>


