import { useAuthStore } from '../stores/auth'

// 默认走 Vite 同域代理 /api -> 后端（避免 CORS / 系统代理干扰）
const API_BASE = (import.meta as any).env?.VITE_API_BASE || '/api'

function toStr(v: any): string {
  if (v == null) return ''
  return typeof v === 'string' ? v : String(v)
}

function friendlyMessage(status: number, detail: string, path: string): string {
  const d = toStr(detail)

  // 针对常见“业务可解释”的 400，给用户可理解的提示（不暴露技术名词/JSON）
  if (status === 400) {
    if (d.includes('会计期间未开放')) return '当前会计期间未开放，暂时无法完成该操作。请先打开对应期间。'
    if (d.includes('借贷不平衡')) return '借贷不平衡，请检查金额后再提交。'
    if (d.includes('科目不允许记账') || d.includes('不允许记账')) return '所选科目不允许记账，请更换可记账科目。'
    if (d.includes('科目已停用') || d.includes('已停用')) return '所选科目已停用，请更换科目。'
    if (d.includes('草稿不存在')) return '草稿不存在或已被删除，请刷新后重试。'
    if (d.includes('重复过账') || d.includes('幂等')) return '该单据已过账，无需重复操作。'
    if (d.includes('缺少汇率') || d.includes('Price') || d.includes('价格')) return '缺少汇率/价格数据，暂时无法完成该操作。请先维护汇率。'
    if (d.includes('至少包含') || d.includes('分录行不足')) return '分录行不完整，请补齐后再提交。'
    return '提交的数据不符合要求，请检查后重试。'
  }

  if (status === 403) return '权限不足，无法执行该操作。'
  if (status === 404) return '页面或数据不存在（可能已被删除），请刷新后重试。'
  if (status === 409) {
    if (d.includes('对账') && d.includes('已完成')) return '该截止日已完成对账，请更换截止日后再开始。'
    if (d.includes('科目代码') && d.includes('已存在')) return '科目代码已存在，请更换代码后再试。'
    if (d.includes('过账') && d.includes('冲突')) return '过账发生冲突，请刷新后重试。'
    return '数据发生冲突，请刷新页面后重试。'
  }
  if (status === 422) return '填写内容有误，请检查必填项与格式后重试。'
  if (status >= 500) return '服务暂时不可用，请稍后重试。'

  // 兜底：不把技术细节吐给用户
  return `操作未完成（${status}），请稍后重试。`
}

export async function http<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const auth = useAuthStore()
  const headers: Record<string, string> = { ...(opts.headers as any) }
  // FormData 上传不能手动设置 Content-Type（浏览器需要自动带 boundary）
  const isForm = typeof FormData !== 'undefined' && opts.body instanceof FormData
  if (!isForm && !headers['Content-Type']) headers['Content-Type'] = 'application/json'
  if (auth.token) headers.Authorization = `Bearer ${auth.token}`

  // API_BASE 支持绝对（http://...）或同域相对（/api）
  let res: Response
  try {
    res = await fetch(`${API_BASE}${path}`, { ...opts, headers })
  } catch (e: any) {
    // 不把技术细节暴露给用户；调试信息仅输出到控制台
    console.error('[API][network]', { path, error: e })
    throw new Error('网络连接失败，请检查网络/后端服务是否已启动后重试。')
  }

  // 统一处理登录态失效：清理 token 并跳回登录页（避免用户卡在业务页面反复“无效 token”）
  if (res.status === 401) {
    auth.logout()
    const cur = `${location.pathname}${location.search}${location.hash}`
    if (!location.pathname.startsWith('/login')) {
      location.replace(`/login?next=${encodeURIComponent(cur)}`)
    }
    // 用户可理解的提示
    const ct = res.headers.get('content-type') || ''
    if (ct.includes('application/json')) {
      const j: any = await res.json().catch(() => null)
      const detail = j?.detail || j?.message || ''
      if (String(detail).includes('无效') || String(detail).includes('过期')) {
        throw new Error('登录已失效，请重新登录')
      }
      throw new Error('登录已失效，请重新登录')
    }
    throw new Error('登录已失效，请重新登录')
  }
  if (!res.ok) {
    const ct = res.headers.get('content-type') || ''
    if (ct.includes('application/json')) {
      const j: any = await res.json().catch(() => null)
      const detail = j?.detail || j?.message || ''
      console.error('[API][error]', { path, status: res.status, detail, body: j })
      throw new Error(friendlyMessage(res.status, String(detail || ''), path))
    }
    const txt = await res.text().catch(() => '')
    console.error('[API][error]', { path, status: res.status, text: txt })
    throw new Error(friendlyMessage(res.status, txt || '', path))
  }
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('application/json')) return (await res.json()) as T
  // export 文件等
  return (await (res as any).blob()) as T
}


