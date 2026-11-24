import { motion } from 'framer-motion'
import { useLang } from '../i18n'
import { RISK } from '../meta'

export interface Dot { id: string; source: string; flagged: boolean; verdict?: string | null; host: string; case_id?: string | null }

const C = 220
const SECTORS: Record<string, { a0: number; a1: number; en: string; ar: string; lx: number; ly: number; anchor: 'start' | 'end' }> = {
  ct: { a0: 190, a1: 260, en: 'New domains', ar: 'نطاقات جديدة', lx: 24, ly: 28, anchor: 'start' },
  search: { a0: 280, a1: 350, en: 'Search and ads', ar: 'البحث والإعلانات', lx: 416, ly: 28, anchor: 'end' },
  maps: { a0: 10, a1: 80, en: 'Google Maps', ar: 'خرائط جوجل', lx: 416, ly: 404, anchor: 'end' },
  report: { a0: 100, a1: 170, en: 'Citizen reports', ar: 'بلاغات المواطنين', lx: 24, ly: 404, anchor: 'start' },
}
const sector = (src: string) => SECTORS[src === 'search_ad' ? 'search' : src] ?? SECTORS.search

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) }
  return ((h >>> 0) % 10000) / 10000
}
const at = (deg: number, r: number) => ({ x: C + r * Math.cos((deg * Math.PI) / 180), y: C + r * Math.sin((deg * Math.PI) / 180) })

const VERDICT_COLOR: Record<string, string> = { confirmed_scam: RISK.high, likely_scam: RISK.high, suspicious: RISK.mid }

export function Radar({ dots, running, confirmed, onPick }: { dots: Dot[]; running: boolean; confirmed: number; onPick?: (d: Dot) => void }) {
  const { p, lang } = useLang()
  const counts: Record<string, number> = {}
  for (const d of dots) { const k = d.source === 'search_ad' ? 'search' : d.source; counts[k] = (counts[k] ?? 0) + (d.flagged ? 1 : 0) }
  return (
    <svg viewBox="0 0 440 440" width="100%" className="radar" role="img" aria-label={p('Hunt radar', 'رادار الرصد')}>
      <defs>
        <linearGradient id="sweepg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#ededed" stopOpacity="0" /><stop offset="1" stopColor="#ededed" stopOpacity="0.12" /></linearGradient>
      </defs>
      {[60, 110, 160, 208].map((r, i) => <circle key={r} cx={C} cy={C} r={r} fill="none" stroke="rgba(237,237,237,0.08)" strokeWidth="1" strokeDasharray={i === 3 ? undefined : '2 6'} />)}
      {[0, 90, 180, 270].map((a) => { const e = at(a, 208); return <line key={a} x1={C} y1={C} x2={e.x} y2={e.y} stroke="rgba(237,237,237,0.06)" /> })}
      {running && (
        <g className="sweep" style={{ transformOrigin: `${C}px ${C}px` }}>
          <path d={`M ${C} ${C} L ${C + 208} ${C} A 208 208 0 0 0 ${at(-38, 208).x} ${at(-38, 208).y} Z`} fill="url(#sweepg)" />
          <line x1={C} y1={C} x2={C + 208} y2={C} stroke="#ededed" strokeWidth="1" opacity="0.5" />
        </g>
      )}
      {dots.map((d) => {
        const s = sector(d.source)
        const ang = s.a0 + hash(d.id) * (s.a1 - s.a0)
        const outer = at(ang, 150 + hash(d.id + 'r') * 56)
        if (!d.flagged) return <motion.circle key={d.id} cx={outer.x} cy={outer.y} fill="#55555a" initial={{ r: 0, opacity: 0 }} animate={{ r: 1.6, opacity: 0.8 }} transition={{ duration: 0.3 }} />
        const inner = at(ang, 46 + hash(d.id + 'i') * 78)
        const color = d.verdict ? VERDICT_COLOR[d.verdict] ?? '#a1a1a6' : '#a1a1a6'
        return (
          <motion.circle key={d.id} fill={color} stroke="#19191b" strokeWidth="1.5" style={{ cursor: d.case_id ? 'pointer' : 'default' }} onClick={() => onPick?.(d)}
            initial={{ cx: outer.x, cy: outer.y, r: 2 }} animate={{ cx: inner.x, cy: inner.y, r: 5 }} transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}>
            <title>{d.host}</title>
          </motion.circle>
        )
      })}
      <circle cx={C} cy={C} r="36" fill="#19191b" stroke="rgba(237,237,237,0.14)" />
      <text x={C} y={C + 4} textAnchor="middle" fontSize="22" fontWeight="500" fill="#ededed" style={{ fontVariantNumeric: 'tabular-nums' }}>{confirmed}</text>
      <text x={C} y={C + 20} textAnchor="middle" fontSize="10" fill="#85858b">{lang === 'ar' ? 'مؤكد' : 'confirmed'}</text>
      {Object.entries(SECTORS).map(([k, s]) => (
        <g key={k}>
          <text x={s.lx} y={s.ly} textAnchor={s.anchor} fontSize="12" fontWeight="500" fill="#a1a1a6">{lang === 'ar' ? s.ar : s.en}</text>
          <text x={s.lx} y={s.ly + 16} textAnchor={s.anchor} fontSize="11" fill="#85858b" style={{ fontVariantNumeric: 'tabular-nums' }}>{counts[k] ?? 0} {p('flagged', 'مشتبه')}</text>
        </g>
      ))}
    </svg>
  )
}
