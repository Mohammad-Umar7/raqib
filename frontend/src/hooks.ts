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
  done: boolean
  error: string | null
}

const initial = (runId: string): InvState => ({
  runId, mode: '', phase: 'queued', phaseLabel: '', meta: null, frame: null, cursor: null, notes: [], requests: [], signals: [], flagged: {}, score: 0,
  verdict: 'no_indicators', indicators: null, evidence: [], fingerprint: null, nodes: [], edges: [], related: [], blocks: null, source: '', headline: null, followUps: [], done: false, error: null,
})

const TAGS: Record<string, string> = {
  card_number: 'CARD', card_cvv: 'CVV', card_expiry: 'EXPIRY', card_holder: 'CARD', otp: 'OTP', emirates_id: 'EMIRATES ID', password: 'PASSWORD', username: 'LOGIN',
}
const SOFT_TAGS: Record<string, string> = {
  'fraud.urgency': 'PRESSURE', 'fraud.guaranteed_returns': 'GUARANTEED RETURNS', 'fraud.upfront_fee': 'UPFRONT FEE', 'fraud.fake_license': 'UNVERIFIED LICENCE',
}

type Action = { type: 'reset'; runId: string } | { type: 'ev'; ev: { type: string; data: any } }

function reduce(s: InvState, a: Action): InvState {
  if (a.type === 'reset') return initial(a.runId)
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
    case 'ui': return { ...s, blocks: d.blocks, source: d.source, headline: { en: d.headline, ar: d.headline_ar }, followUps: d.follow_ups ?? [] }
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
