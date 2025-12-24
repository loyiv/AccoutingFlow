<template>
  <div class="card">
    <h2>登录</h2>
    <div class="row">
      <label>用户名</label>
      <input v-model="username" />
    </div>
    <div class="row">
      <label>密码</label>
      <input v-model="password" type="password" />
    </div>
    <button class="btn" :disabled="loading" @click="onLogin">登录</button>
    <p class="hint">默认：accountant / accountant123（可过账与生成报表）</p>
    <div v-if="error" class="notice">提示：{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useAppStore } from '../stores/app'

const auth = useAuthStore()
const app = useAppStore()
const router = useRouter()
const route = useRoute()

const username = ref('accountant')
const password = ref('accountant123')
const loading = ref(false)
const error = ref('')

async function onLogin() {
  error.value = ''
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    await app.init()
    // 支持从 401 自动跳转回来的 next 参数
    const next = (route.query.next as string) || '/home'
    await router.push(next)
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.card {
  max-width: 420px;
  border: 1px solid var(--primary-100);
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(10px);
  padding: 16px;
  border-radius: 12px;
  box-shadow: var(--shadow);
}
.row {
  display: grid;
  gap: 6px;
  margin-bottom: 10px;
}
input {
  border: 1px solid var(--primary-200);
  padding: 8px 10px;
  border-radius: 10px;
}
.btn {
  border: 1px solid var(--primary-600);
  background: linear-gradient(135deg, var(--primary-600), var(--primary-500));
  color: #fff;
  padding: 8px 12px;
  border-radius: 10px;
  cursor: pointer;
}
.btn:hover {
  background: linear-gradient(135deg, var(--primary-700), var(--primary-600));
  border-color: var(--primary-700);
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.hint {
  margin-top: 10px;
  color: var(--muted);
  font-size: 12px;
}
.notice {
  margin-top: 10px;
  border: 1px solid var(--primary-200);
  background: var(--primary-50);
  color: var(--primary-900);
  padding: 10px 12px;
  border-radius: 10px;
  font-size: 12px;
}
</style>


