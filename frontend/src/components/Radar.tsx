import { motion } from 'framer-motion'
import { useLang } from '../i18n'

export interface Dot { id: string; source: string; flagged: boolean; verdict?: string | null; host: string; case_id?: string | null }

const C = 220
const SECTORS: Record<string, { a0: number; a1: number; en: string; ar: string; lx: number; ly: number; anchor: 'start' | 'end' }> = {
  ct: { a0: 190, a1: 260, en: 'New certificates', ar: 'شهادات جديدة', lx: 26, ly: 30, anchor: 'start' },
  search: { a0: 280, a1: 350, en: 'Search & ads', ar: 'البحث والإعلانات', lx: 414, ly: 30, anchor: 'end' },
  maps: { a0: 10, a1: 80, en: 'Google Maps', ar: 'خرائط جوجل', lx: 414, ly: 420, anchor: 'end' },
  report: { a0: 100, a1: 170, en: 'Citizen reports', ar: 'بلاغات المواطنين', lx: 26, ly: 420, anchor: 'start' },
}
const sector = (src: string) => SECTORS[src === 'search_ad' ? 'search' : src] ?? SECTORS.search

function hash(s: string): number {
  let h = 2166136261
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) }
  return ((h >>> 0) % 10000) / 10000
}
const at = (deg: number, r: number) => ({ x: C + r * Math.cos((deg * Math.PI) / 180), y: C + r * Math.sin((deg * Math.PI) / 180) })

const VERDICT_COLOR: Record<string, string> = { confirmed_scam: '#fb4a6c', likely_scam: '#fb7a4a', suspicious: '#ff8a3d' }

export function Radar({ dots, running, confirmed, onPick }: { dots: Dot[]; running: boolean; confirmed: number; onPick?: (d: Dot) => void }) {
  const { p, lang } = useLang()
  const counts: Record<string, number> = {}
  for (const d of dots) { const k = d.source === 'search_ad' ? 'search' : d.source; counts[k] = (counts[k] ?? 0) + (d.flagged ? 1 : 0) }
  return (
    <svg viewBox="0 0 440 440" width="100%" className="radar" role="img" aria-label={p('Hunt radar', 'رادار الرصد')}>
      <defs>
        <radialGradient id="rbg"><stop offset="0" stopColor="#1d1a14" stopOpacity="0.9" /><stop offset="1" stopColor="#0a0a0e" stopOpacity="0" /></radialGradient>
        <linearGradient id="sweepg" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stopColor="#e5b85c" stopOpacity="0" /><stop offset="1" stopColor="#e5b85c" stopOpacity="0.5" /></linearGradient>
        <filter id="rglow" x="-100%" y="-100%" width="300%" height="300%"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>
      <circle cx={C} cy={C} r="214" fill="url(#rbg)" />
      {[60, 110, 160, 208].map((r, i) => <circle key={r} cx={C} cy={C} r={r} fill="none" stroke="#24242e" strokeWidth="1" strokeDasharray={i === 3 ? undefined : '2 6'} />)}
      {[0, 90, 180, 270].map((a) => { const e = at(a, 208); return <line key={a} x1={C} y1={C} x2={e.x} y2={e.y} stroke="#1d1d26" /> })}
      <g className={`sweep ${running ? 'run' : ''}`} style={{ transformOrigin: `${C}px ${C}px` }}>
        <path d={`M ${C} ${C} L ${C + 208} ${C} A 208 208 0 0 0 ${at(-38, 208).x} ${at(-38, 208).y} Z`} fill="url(#sweepg)" />
        <line x1={C} y1={C} x2={C + 208} y2={C} stroke="#f2d39a" strokeWidth="1.5" opacity="0.8" />
      </g>
      {dots.map((d) => {
        const s = sector(d.source)
        const ang = s.a0 + hash(d.id) * (s.a1 - s.a0)
        const outer = at(ang, 150 + hash(d.id + 'r') * 56)
        if (!d.flagged) return <motion.circle key={d.id} cx={outer.x} cy={outer.y} fill="#6f6b7d" initial={{ r: 0, opacity: 0 }} animate={{ r: 1.7, opacity: 0.5 }} transition={{ duration: 0.4 }} />
        const inner = at(ang, 46 + hash(d.id + 'i') * 78)
        const color = d.verdict ? VERDICT_COLOR[d.verdict] ?? '#e5b85c' : '#e5b85c'
        return (
          <motion.g key={d.id} initial={{ opacity: 0 }} animate={{ opacity: 1 }} style={{ cursor: d.case_id ? 'pointer' : 'default' }} onClick={() => onPick?.(d)}>
            <motion.circle fill="none" stroke={color} strokeWidth="1.5" initial={{ cx: outer.x, cy: outer.y, r: 3, opacity: 0.9 }} animate={{ cx: inner.x, cy: inner.y, r: 17, opacity: 0 }} transition={{ duration: 1.5, ease: 'easeOut' }} />
            <motion.circle fill={color} filter="url(#rglow)" initial={{ cx: outer.x, cy: outer.y, r: 2 }} animate={{ cx: inner.x, cy: inner.y, r: 5.2 }} transition={{ type: 'spring', stiffness: 70, damping: 14 }}>
              <title>{d.host}</title>
            </motion.circle>
          </motion.g>
        )
      })}
      <circle cx={C} cy={C} r="35" fill="#101015" stroke="#34343f" />
      <text x={C} y={C + 3} textAnchor="middle" fontSize="23" fontWeight="750" fill="#fff" style={{ fontVariantNumeric: 'tabular-nums' }}>{confirmed}</text>
      <text x={C} y={C + 19} textAnchor="middle" fontSize="8.5" fill="#8c8996" fontWeight="600" letterSpacing=".08em">{lang === 'ar' ? 'مؤكد' : 'CONFIRMED'}</text>
      {Object.entries(SECTORS).map(([k, s]) => (
        <g key={k}>
          <text x={s.lx} y={s.ly} textAnchor={s.anchor} fontSize="11" fontWeight="650" fill="#b2afba">{lang === 'ar' ? s.ar : s.en}</text>
          <text x={s.lx} y={s.ly + 14} textAnchor={s.anchor} fontSize="10" fill="#fb7a8c" fontWeight="600">{counts[k] ?? 0} {p('flagged', 'مشتبه')}</text>
        </g>
      ))}
    </svg>
  )
}
