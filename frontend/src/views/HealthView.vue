<template>
  <div class="page">
    <div class="top">
      <h2>自检</h2>
      <button class="btn" @click="run">重新检查</button>
    </div>

    <p class="muted">用于快速判断系统是否可用（不展示 JSON/技术细节）。</p>

    <ExampleCard title="操作示例：排查“打不开/没数据”的最短路径" subtitle="目标：快速判断是前端、后端还是数据库问题。">
      <ol class="ol">
        <li>先看三项是否都显示“正常”。</li>
        <li>若“后端服务/数据库连接”为异常：请先重启后端（run_local.cmd）。</li>
        <li>若都正常但业务页没数据：回到“待过账/采购/销售/报销”，点击“刷新”或用“一键填充示例”生成一条数据。</li>
      </ol>
    </ExampleCard>

    <div class="grid">
      <section class="card">
        <h3>后端服务</h3>
        <div class="row">
          <span class="label">/health</span>
          <span class="badge" :class="healthOk ? 'ok' : 'bad'">{{ healthOk ? '正常' : '异常' }}</span>
        </div>
      </section>
      <section class="card">
        <h3>数据库连接</h3>
        <div class="row">
          <span class="label">/health/db</span>
          <span class="badge" :class="dbOk ? 'ok' : 'bad'">{{ dbOk ? '正常' : '异常' }}</span>
        </div>
      </section>
      <section class="card">
        <h3>数据库结构</h3>
        <div class="row">
          <span class="label">/health/schema</span>
          <span class="badge" :class="schemaOk ? 'ok' : 'bad'">{{ schemaOk ? '正常' : '异常' }}</span>
        </div>
      </section>
    </div>

    <div v-if="error" class="notice">提示：{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { http } from '../services/http'
import ExampleCard from '../components/ExampleCard.vue'

const healthOk = ref(false)
const dbOk = ref(false)
const schemaOk = ref(false)
const error = ref('')

async function run() {
  error.value = ''
  try {
    const h = await http<any>('/health')
    healthOk.value = !!h?.ok

    const db = await http<any>('/health/db')
    dbOk.value = !!db?.ok

    const s = await http<any>('/health/schema')
    schemaOk.value = !!s?.ok
  } catch (e: any) {
    error.value = e?.message || String(e)
  }
}

onMounted(run)
</script>

<style scoped>
.top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.btn {
  border: 1px solid #ddd;
  background: white;
  padding: 7px 10px;
  border-radius: 10px;
  cursor: pointer;
}
.grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.card {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
}
.row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
}
.label {
  color: #374151;
  font-size: 12px;
}
.badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 999px;
  border: 1px solid #e5e7eb;
  background: #f9fafb;
  color: #111827;
}
.badge.ok {
  border-color: #b7eb8f;
  background: #f6ffed;
}
.badge.bad {
  border-color: #ffccc7;
  background: #fff2f0;
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
</style>


