import { useEffect, useReducer, useRef, useState } from 'react'
import { stream } from './api'
import type { Block, EvItem, Frame, GEdge, GNode, Indicators, Req, Signal, Verdict } from './types'

export interface InvState {
  runId: string
  mode: string
  phase: string
  phaseLabel: string
  meta: any
  frame: Frame | null
  cursor: { target?: string; x?: number | null; y?: number | null; action: string; label: string; seq: number } | null
  notes: { text: string; text_ar?: string }[]
  requests: Req[]
  signals: Signal[]
  flagged: Record<string, { tag: string; soft: boolean }>
  score: number
  verdict: Verdict
  indicators: Indicators | null
  evidence: EvItem[]
  fingerprint: any
  nodes: GNode[]
  edges: GEdge[]
  related: any[]
  blocks: Block[] | null
  source: string
  headline: { en: string; ar: string } | null
  followUps: { q: string; q_ar: string }[]
  model: string
  timeline: TL[]
  done: boolean
  error: string | null
}

/** One line in the agent activity log. `agent` says which member of the crew did it. */
export interface TL { id: number; t: number; agent: 'browser' | 'detector' | 'linker' | 'writer' | 'system'; kind: string; text: string; text_ar?: string; tone?: string; sub?: string }

const initial = (runId: string): InvState => ({
  runId, mode: '', phase: 'queued', phaseLabel: '', meta: null, frame: null, cursor: null, notes: [], requests: [], signals: [], flagged: {}, score: 0,
  verdict: 'no_indicators', indicators: null, evidence: [], fingerprint: null, nodes: [], edges: [], related: [], blocks: null, source: '', headline: null, followUps: [], model: '', timeline: [], done: false, error: null,
})

const SEV_TONE: Record<string, string> = { critical: 'danger', high: 'warn', medium: 'info', low: 'muted' }

/** Turn a raw event into an activity-log line (or nothing, for noisy events). */
function toLine(ev: { id: number; t: number; type: string; data: any }, s: InvState): Omit<TL, 'id' | 't'> | null {
  const d = ev.data
  switch (ev.type) {
    case 'meta': return d.mode === 'replay' || d.mode === 'live' ? { agent: 'system', kind: 'start', text: 'Isolated browser started', text_ar: 'بدأ المتصفح المعزول', sub: d.profile } : null
    case 'note': return { agent: 'browser', kind: 'think', text: d.text, text_ar: d.text_ar }
    case 'frame': return { agent: 'browser', kind: 'page', text: `Page loaded: ${d.title || 'untitled'}`, text_ar: `تم تحميل الصفحة: ${d.title || ''}`, sub: d.url }
    case 'cursor':
      if (d.action === 'click') return { agent: 'browser', kind: 'click', text: `Clicked “${d.label}”`, text_ar: `نقر على «${d.label}»` }
      if (d.action === 'type') return { agent: 'browser', kind: 'type', text: `Typed a harmless test value into “${d.label}”`, text_ar: `أدخل قيمة تجريبية في «${d.label}»` }
      if (d.action === 'move') return { agent: 'browser', kind: 'inspect', text: `Inspected “${d.label}”`, text_ar: `فحص «${d.label}»` }
      if (d.action === 'scroll') return { agent: 'browser', kind: 'scroll', text: 'Scrolled through the page', text_ar: 'مرّر الصفحة' }
      return null
    case 'request':
      if (d.flag === 'redirect') return { agent: 'browser', kind: 'redirect', text: `Followed a ${d.status} redirect`, text_ar: `تابع تحويلاً ${d.status}`, sub: d.url, tone: 'warn' }
      if (d.flag === 'kit') return { agent: 'detector', kind: 'kit', text: 'Script matches a scam-kit file', text_ar: 'سكربت يطابق ملف أدوات احتيال', sub: d.url, tone: 'warn' }
      return null
    case 'signal': return { agent: 'detector', kind: 'signal', text: d.label, text_ar: d.label_ar, tone: SEV_TONE[d.severity], sub: `+${Math.round(d.weight * 100)} · ${d.category}` }
    case 'fingerprint': return { agent: 'linker', kind: 'fingerprint', text: 'Built the scam fingerprint', text_ar: 'أنشأ بصمة الاحتيال', sub: [...(d.exfil ?? []), ...(d.wallets ?? []), ...(d.phones ?? [])].slice(0, 2).join(' · ') }
    case 'related_case': return { agent: 'linker', kind: 'link', text: `Linked ${d.host}`, text_ar: `ربط ${d.host}`, sub: d.reason, tone: d.strength === 'strong' ? 'danger' : 'warn' }
    case 'ui': return { agent: 'writer', kind: 'compose', text: `Composed the case file (${d.blocks?.length ?? 0} blocks)`, text_ar: `ركّب ملف القضية (${d.blocks?.length ?? 0} كتلة)`, tone: 'violet' }
    case 'done': return { agent: 'system', kind: 'done', text: `Investigation complete · score ${d.score}`, text_ar: `اكتمل التحقيق · الدرجة ${d.score}`, tone: 'ok' }
    case 'error': return { agent: 'system', kind: 'error', text: d.message, tone: 'danger' }
    default: return null
  }
  void s
}

const TAGS: Record<string, string> = {
  card_number: 'CARD', card_cvv: 'CVV', card_expiry: 'EXPIRY', card_holder: 'CARD', otp: 'OTP', emirates_id: 'EMIRATES ID', password: 'PASSWORD', username: 'LOGIN',
}
const SOFT_TAGS: Record<string, string> = {
  'fraud.urgency': 'PRESSURE', 'fraud.guaranteed_returns': 'GUARANTEED RETURNS', 'fraud.upfront_fee': 'UPFRONT FEE', 'fraud.fake_license': 'UNVERIFIED LICENCE',
}

type Action = { type: 'reset'; runId: string } | { type: 'ev'; ev: { type: string; data: any } }

function reduce(s0: InvState, a: Action): InvState {
  if (a.type === 'reset') return initial(a.runId)
  const line = toLine(a.ev as any, s0)
  const s = line ? { ...s0, timeline: [...s0.timeline.slice(-160), { ...line, id: (a.ev as any).id ?? s0.timeline.length, t: (a.ev as any).t ?? 0 }] } : s0
  const { type, data: d } = a.ev
  switch (type) {
    case 'status': return { ...s, phase: d.phase, phaseLabel: d.label }
    case 'meta': return { ...s, meta: d, mode: d.mode }
    case 'frame': return { ...s, frame: d, cursor: null }
    case 'cursor': return { ...s, cursor: { ...d, seq: (s.cursor?.seq ?? 0) + 1 } }
    case 'note': return { ...s, notes: [...s.notes.slice(-60), d] }
    case 'request': return { ...s, requests: [...s.requests.slice(-60), d] }
    case 'signal': {
      const flagged = { ...s.flagged }
      for (const e of d.evidence ?? []) {
        if (e.page && e.element) {
          const tag = e.type === 'field' ? TAGS[e.note] ?? 'SENSITIVE' : SOFT_TAGS[d.id] ?? ''
          if (tag) flagged[`${e.page}:${e.element}`] = { tag, soft: e.type !== 'field' }
        }
      }
      return { ...s, signals: [...s.signals, d], flagged }
    }
    case 'score': return { ...s, score: d.score, verdict: d.verdict }
    case 'indicators': return { ...s, indicators: d }
    case 'evidence': return { ...s, evidence: [...s.evidence, d] }
    case 'fingerprint': return { ...s, fingerprint: d }
    case 'graph': {
      const nodes = d.reset ? [] : [...s.nodes]
      const edges = d.reset ? [] : [...s.edges]
      for (const n of d.nodes) if (!nodes.some((x) => x.case_id === n.case_id)) nodes.push(n)
      for (const e of d.edges) if (!edges.some((x) => x.source === e.source && x.target === e.target)) edges.push(e)
      return { ...s, nodes, edges }
    }
    case 'related_case': return { ...s, related: [...s.related, d] }
    case 'ui': return { ...s, blocks: d.blocks, source: d.source, headline: { en: d.headline, ar: d.headline_ar }, followUps: d.follow_ups ?? [], model: d.model ?? '' }
    case 'done': return { ...s, done: true, phase: 'done' }
    case 'error': return { ...s, error: d.message, done: true }
    default: return s
  }
}

export function useInvestigation(runId: string | null): InvState {
  const [state, dispatch] = useReducer(reduce, initial(runId ?? ''))
  useEffect(() => {
    dispatch({ type: 'reset', runId: runId ?? '' })
    if (!runId) return
    return stream(`/api/investigations/${runId}/events`, (ev) => dispatch({ type: 'ev', ev }))
  }, [runId])
  return state
}

/** Smoothly count toward `target`. */
export function useCountUp(target: number, ms = 900): number {
  const [v, setV] = useState(target)
  const from = useRef(target)
  useEffect(() => {
    const start = performance.now()
    const a = from.current
    let raf = 0
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms)
      const e = 1 - Math.pow(1 - k, 3)
      const val = a + (target - a) * e
      setV(val)
      from.current = val
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [target, ms])
  return v
}
