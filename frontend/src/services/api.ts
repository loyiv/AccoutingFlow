import { http } from './http'

export const api = {
  async login(username: string, password: string): Promise<string> {
    const res = await http<{ access_token: string }>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    return res.access_token
  },
  async me() {
    return await http<{ id: string; username: string; role: string }>('/auth/me')
  },
  async listBooks() {
    return await http<Array<{ id: string; name: string; base_currency_id: string }>>('/books')
  },
  async listPeriods(bookId: string) {
    return await http<Array<{ id: string; book_id: string; year: number; month: number; status: string }>>(
      `/periods?book_id=${encodeURIComponent(bookId)}`,
    )
  },
  async listDrafts(periodId?: string) {
    const q = periodId ? `?period=${encodeURIComponent(periodId)}` : ''
    return await http<
      Array<{ id: string; period_id: string; source_type: string; source_id: string; version: number; description: string; status: string }>
    >(`/gl/drafts${q}`)
  },
  async approveDraft(id: string) {
    return await http<any>(`/gl/drafts/${encodeURIComponent(id)}:approve`, { method: 'POST', body: '{}' })
  },
  async rejectDraft(id: string, reason: string) {
    return await http<any>(`/gl/drafts/${encodeURIComponent(id)}:reject`, { method: 'POST', body: JSON.stringify({ reason }) })
  },
  async getDraft(id: string) {
    return await http<any>(`/gl/drafts/${id}`)
  },
  async precheckDraft(id: string) {
    return await http<any>(`/gl/drafts/${id}:precheck`, { method: 'POST', body: '{}' })
  },
  async postDraft(id: string) {
    return await http<any>(`/gl/drafts/${id}:post`, { method: 'POST', body: '{}' })
  },
  async createDraft(payload: any) {
    return await http<{ draft_id: string }>(`/gl/drafts`, { method: 'POST', body: JSON.stringify(payload) })
  },
  async getAccountsTree(bookId: string, periodId?: string) {
    const q = periodId ? `&period_id=${encodeURIComponent(periodId)}` : ''
    return await http<any>(`/accounts/tree?book_id=${encodeURIComponent(bookId)}${q}`)
  },
  async getRegister(accountId: string, periodId?: string) {
    const q = periodId ? `?period_id=${encodeURIComponent(periodId)}` : ''
    return await http<any>(`/accounts/${accountId}/register${q}`)
  },
  async setSplitReconcile(splitId: string, state: 'n' | 'c' | 'y') {
    return await http<any>(`/accounts/splits/${encodeURIComponent(splitId)}:set_reconcile?state=${encodeURIComponent(state)}`, {
      method: 'POST',
      body: '{}',
    })
  },
  async getAccount(accountId: string) {
    return await http<any>(`/accounts/${encodeURIComponent(accountId)}`)
  },
  async createAccount(payload: any) {
    return await http<any>('/accounts', { method: 'POST', body: JSON.stringify(payload) })
  },
  async updateAccount(accountId: string, payload: any) {
    return await http<any>(`/accounts/${encodeURIComponent(accountId)}`, { method: 'PUT', body: JSON.stringify(payload) })
  },
  async generateReport(bookId: string, periodId: string, basisCode: string) {
    return await http<{ snapshot_id: string }>('/reports/generate', {
      method: 'POST',
      body: JSON.stringify({ book_id: bookId, period_id: periodId, basis_code: basisCode }),
    })
  },
  async listSnapshots(bookId: string) {
    return await http<any>(`/reports/snapshots?book_id=${encodeURIComponent(bookId)}`)
  },
  async getSnapshot(id: string) {
    return await http<any>(`/reports/snapshots/${id}`)
  },
  async drilldown(snapshotId: string, statementType: string, itemCode: string) {
    return await http<any>(
      `/reports/snapshots/${snapshotId}/drilldown?statement_type=${encodeURIComponent(statementType)}&item_code=${encodeURIComponent(itemCode)}`,
    )
  },
  async drilldownRegister(snapshotId: string, statementType: string, itemCode: string, accountId: string, includeChildren = false) {
    return await http<any>(
      `/reports/snapshots/${snapshotId}/drilldown/register?statement_type=${encodeURIComponent(statementType)}&item_code=${encodeURIComponent(
        itemCode,
      )}&account_id=${encodeURIComponent(accountId)}&include_children=${includeChildren ? 'true' : 'false'}`,
    )
  },
  async getTransaction(txnId: string) {
    return await http<any>(`/reports/transactions/${encodeURIComponent(txnId)}`)
  },
  async exportReport(snapshotId: string, format: 'pdf' | 'excel') {
    // 返回 Blob
    return await http<Blob>('/reports/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ snapshot_id: snapshotId, format }),
    })
  },

  // Business
  async listCustomers() {
    return await http<any[]>('/business/customers')
  },
  async createCustomer(payload: any) {
    return await http<any>('/business/customers', { method: 'POST', body: JSON.stringify(payload) })
  },
  async listVendors() {
    return await http<any[]>('/business/vendors')
  },
  async createVendor(payload: any) {
    return await http<any>('/business/vendors', { method: 'POST', body: JSON.stringify(payload) })
  },
  async listDocuments(docType: string, status?: string) {
    const q = status ? `&status=${encodeURIComponent(status)}` : ''
    return await http<any[]>(`/business/documents?doc_type=${encodeURIComponent(docType)}${q}`)
  },
  async getDocument(id: string) {
    return await http<any>(`/business/documents/${encodeURIComponent(id)}`)
  },
  async createPurchaseOrder(payload: any) {
    return await http<any>('/business/purchase-orders', { method: 'POST', body: JSON.stringify(payload) })
  },
  async createSalesOrder(payload: any) {
    return await http<any>('/business/sales-orders', { method: 'POST', body: JSON.stringify(payload) })
  },
  async createExpenseClaim(payload: any) {
    return await http<any>('/business/expense-claims', { method: 'POST', body: JSON.stringify(payload) })
  },
  async resubmitDocument(docId: string, payload: any) {
    return await http<any>(`/business/documents/${encodeURIComponent(docId)}:resubmit`, { method: 'POST', body: JSON.stringify(payload) })
  },

  async uploadAttachment(file: File) {
    const fd = new FormData()
    fd.append('file', file)
    return await http<any>('/attachments/upload', { method: 'POST', body: fd })
  },

  // Imports
  async previewAccountsImport(bookId: string, file: File, delimiter?: string) {
    const fd = new FormData()
    fd.append('book_id', bookId)
    fd.append('file', file)
    if (delimiter) fd.append('delimiter', delimiter)
    return await http<any>('/imports/accounts/preview', { method: 'POST', body: fd })
  },
  async commitAccountsImport(bookId: string, file: File, delimiter?: string, updateExisting = true) {
    const fd = new FormData()
    fd.append('book_id', bookId)
    fd.append('file', file)
    if (delimiter) fd.append('delimiter', delimiter)
    fd.append('update_existing', updateExisting ? 'true' : 'false')
    return await http<any>('/imports/accounts/commit', { method: 'POST', body: fd })
  },

  // Scheduled
  async listScheduled(bookId: string) {
    return await http<any[]>(`/scheduled?book_id=${encodeURIComponent(bookId)}`)
  },
  async createScheduled(payload: any) {
    return await http<any>('/scheduled', { method: 'POST', body: JSON.stringify(payload) })
  },
  async runScheduled(schedId: string, run_date?: string) {
    return await http<any>(`/scheduled/${encodeURIComponent(schedId)}:run`, {
      method: 'POST',
      body: JSON.stringify({ run_date: run_date || null }),
    })
  },

  // Reconcile
  async listReconcileSessions(bookId: string, accountId?: string) {
    const a = accountId ? `&account_id=${encodeURIComponent(accountId)}` : ''
    return await http<any[]>(`/reconcile/sessions?book_id=${encodeURIComponent(bookId)}${a}`)
  },
  async createReconcileSession(payload: any) {
    return await http<any>('/reconcile/sessions', { method: 'POST', body: JSON.stringify(payload) })
  },
  async getReconcileSession(sessionId: string) {
    return await http<any>(`/reconcile/sessions/${encodeURIComponent(sessionId)}`)
  },
  async toggleReconcile(sessionId: string, splitId: string, selected: boolean) {
    return await http<any>(`/reconcile/sessions/${encodeURIComponent(sessionId)}:toggle`, {
      method: 'POST',
      body: JSON.stringify({ split_id: splitId, selected }),
    })
  },
  async finishReconcile(sessionId: string) {
    return await http<any>(`/reconcile/sessions/${encodeURIComponent(sessionId)}:finish`, { method: 'POST', body: '{}' })
  },
}


