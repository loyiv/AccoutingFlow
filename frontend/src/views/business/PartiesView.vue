<template>
  <div class="page">
    <h2>往来单位</h2>

    <ExampleCard title="操作示例（企业日常）：维护客户/供应商" subtitle="目标：为采购/销售单据选择往来单位。">
      <ol class="ol">
        <li>如果你是第一次使用：点击“客户/供应商”的“新增”，可直接创建往来单位。</li>
        <li>示例：客户填“上海示例客户有限公司”，供应商填“华东示例供应商有限公司”。</li>
        <li>创建后，到“采购订单/销售订单”页面即可在下拉框选到这些单位。</li>
      </ol>
      <template #actions>
        <button class="btn" @click="openExampleCustomer">一键新增示例客户</button>
        <button class="btn" @click="openExampleVendor">一键新增示例供应商</button>
      </template>
    </ExampleCard>

    <div class="grid">
      <section class="card">
        <div class="head">
          <b>客户</b>
          <button class="btn" @click="openCreate('CUSTOMER')">新增</button>
        </div>
        <table class="table">
          <thead>
            <tr><th>名称</th><th>信用额度</th><th>账期(天)</th></tr>
          </thead>
          <tbody>
            <tr v-for="c in customers" :key="c.id">
              <td>{{ c.name }}</td>
              <td>{{ c.credit_limit ?? '-' }}</td>
              <td>{{ c.payment_term_days ?? '-' }}</td>
            </tr>
            <tr v-if="!customers.length"><td colspan="3" class="muted">暂无客户</td></tr>
          </tbody>
        </table>
      </section>

      <section class="card">
        <div class="head">
          <b>供应商</b>
          <button class="btn" @click="openCreate('VENDOR')">新增</button>
        </div>
        <table class="table">
          <thead>
            <tr><th>名称</th><th>信用额度</th><th>账期(天)</th></tr>
          </thead>
          <tbody>
            <tr v-for="v in vendors" :key="v.id">
              <td>{{ v.name }}</td>
              <td>{{ v.credit_limit ?? '-' }}</td>
              <td>{{ v.payment_term_days ?? '-' }}</td>
            </tr>
            <tr v-if="!vendors.length"><td colspan="3" class="muted">暂无供应商</td></tr>
          </tbody>
        </table>
      </section>
    </div>

    <div v-if="showDialog" class="modal">
      <div class="modal-card">
        <div class="modal-head">
          <b>新增 {{ createType === 'CUSTOMER' ? '客户' : '供应商' }}</b>
          <button class="btn" @click="close">关闭</button>
        </div>
        <div class="form">
          <div class="frow"><label>名称</label><input v-model="form.name" /></div>
          <div class="frow"><label>税号</label><input v-model="form.tax_no" /></div>
          <div class="frow"><label>信用额度</label><input v-model="form.credit_limit" placeholder="可空" /></div>
          <div class="frow"><label>账期(天)</label><input v-model="form.payment_term_days" placeholder="可空" /></div>
        </div>
        <div class="foot">
          <button class="btn primary" :disabled="saving" @click="save">保存</button>
        </div>
        <div v-if="error" class="notice">提示：{{ error }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../../services/api'
import ExampleCard from '../../components/ExampleCard.vue'

const customers = ref<any[]>([])
const vendors = ref<any[]>([])
const showDialog = ref(false)
const createType = ref<'CUSTOMER' | 'VENDOR'>('CUSTOMER')
const saving = ref(false)
const error = ref('')
const form = ref<any>({ name: '', tax_no: '', credit_limit: '', payment_term_days: '' })

async function load() {
  customers.value = await api.listCustomers()
  vendors.value = await api.listVendors()
}

function openCreate(t: 'CUSTOMER' | 'VENDOR') {
  createType.value = t
  form.value = { name: '', tax_no: '', credit_limit: '', payment_term_days: '' }
  error.value = ''
  showDialog.value = true
}

function openExampleCustomer() {
  openCreate('CUSTOMER')
  form.value = { name: '上海示例客户有限公司', tax_no: '', credit_limit: '50000', payment_term_days: '30' }
}
function openExampleVendor() {
  openCreate('VENDOR')
  form.value = { name: '华东示例供应商有限公司', tax_no: '', credit_limit: '', payment_term_days: '30' }
}

function close() {
  showDialog.value = false
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const payload: any = {
      name: form.value.name,
      tax_no: form.value.tax_no || '',
      credit_limit: form.value.credit_limit ? Number(form.value.credit_limit) : null,
      payment_term_days: form.value.payment_term_days ? Number(form.value.payment_term_days) : null,
      contact_json: createType.value === 'CUSTOMER' ? { grade: 'A' } : { annual_purchase_over_10m: false },
    }
    if (createType.value === 'CUSTOMER') await api.createCustomer(payload)
    else await api.createVendor(payload)
    showDialog.value = false
    await load()
  } catch (e: any) {
    error.value = e?.message || String(e)
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.card {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
}
.head {
  display: flex;
  justify-content: space-between;
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
.modal {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.35);
  display: grid;
  place-items: center;
  padding: 16px;
}
.modal-card {
  width: min(800px, 96vw);
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
  grid-template-columns: 120px 1fr;
  gap: 10px;
  align-items: center;
}
input {
  border: 1px solid #ddd;
  padding: 8px 10px;
  border-radius: 10px;
}
.foot {
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


