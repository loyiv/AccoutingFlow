const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

export function isUuidLike(s: string | null | undefined) {
  if (!s) return false
  return UUID_RE.test(String(s).trim())
}

export function sourceTypeLabel(type: string | null | undefined) {
  const t = String(type || '').trim().toUpperCase()
  if (!t) return '—'
  if (t === 'PURCHASE_ORDER') return '采购订单'
  if (t === 'SALES_ORDER') return '销售订单'
  if (t === 'EXPENSE_CLAIM') return '报销单'
  if (t === 'SCHEDULED') return '定期交易'
  if (t === 'MANUAL') return '手工凭证'
  if (t === 'SEED') return '示例数据'
  return t
}

function extractDocNoFromText(text: string | null | undefined) {
  const s = String(text || '')
  // 常见：PURCHASE_ORDER:PO-20251224-... / SALES_ORDER:SO-... / EXPENSE_CLAIM:EC-...
  const m1 = s.match(/\b(PO|SO|EC)-[0-9]{8}-[0-9]{4,}\b/i)
  if (m1?.[0]) return m1[0].toUpperCase()
  const m2 = s.match(/\b(PO|SO|EC)-SEED-[0-9]+\b/i)
  if (m2?.[0]) return m2[0].toUpperCase()
  const m3 = s.match(/\b(seed-[0-9]+)\b/i)
  if (m3?.[1]) return m3[1]
  return ''
}

function shortId(id: string | null | undefined) {
  const s = String(id || '').trim()
  if (!s) return ''
  if (isUuidLike(s)) return s.slice(0, 8) // 只保留前 8 位，避免“长串乱码”
  if (s.length > 24) return s.slice(0, 12) + '…'
  return s
}

/** 给用户展示的“来源”字符串：优先用单号（PO/SO/EC），否则缩短 id。 */
export function formatSourceDisplay(args: {
  source_type?: string | null
  source_id?: string | null
  version?: number | null
  description?: string | null
  // 报表交易详情可能带 source_doc
  source_doc?: { doc_type?: string; doc_no?: string } | null
}) {
  const typeText = sourceTypeLabel(args.source_type)

  const fromDoc = args.source_doc?.doc_no ? String(args.source_doc.doc_no) : ''
  const fromDesc = extractDocNoFromText(args.description)
  const ref = fromDoc || fromDesc || (args.source_id ? shortId(args.source_id) : '')

  const parts: string[] = []
  parts.push(typeText)
  if (ref) parts.push(ref)
  if (typeof args.version === 'number') parts.push(`v${args.version}`)
  return parts.join(' · ')
}


