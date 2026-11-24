import { motion } from 'framer-motion'
import { useCountUp } from '../hooks'
import { scoreColor } from '../meta'

const R = 80
const cx = 95, cy = 100
const pt = (pct: number, r = R) => {
  const a = Math.PI * (1 - pct / 100)
  return { x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) }
}

/** The risk score: one arc in the colour of its risk band, with the 30 / 60 / 85 thresholds marked. */
export function Gauge({ score, size = 192 }: { score: number; size?: number; final?: boolean }) {
  const v = useCountUp(score, 1100)
  const color = scoreColor(score)
  const h = size * 0.64
  const tip = pt(Math.max(0.5, v))
  return (
    <div className="gauge" style={{ width: size, height: h }}>
      <svg viewBox="0 0 190 122" width={size} height={h}>
        <path d="M 15 100 A 80 80 0 0 1 175 100" fill="none" stroke="#232325" strokeWidth="10" strokeLinecap="butt" />
        {[30, 60, 85].map((t) => {
          const a = pt(t, R - 8), b = pt(t, R + 8), l = pt(t, R + 18)
          return (
            <g key={t}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#55555a" strokeWidth="1.5" />
              <text x={l.x} y={l.y + 3} textAnchor="middle" fontSize="9" fill="#85858b" style={{ fontVariantNumeric: 'tabular-nums' }}>{t}</text>
            </g>
          )
        })}
        <motion.path d="M 15 100 A 80 80 0 0 1 175 100" fill="none" stroke={color} strokeWidth="10" strokeLinecap="butt"
          initial={{ pathLength: 0 }} animate={{ pathLength: Math.max(0.002, score / 100) }} transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }} />
        {v > 1 && <circle cx={tip.x} cy={tip.y} r="5" fill="#ededed" stroke="#19191b" strokeWidth="2" />}
      </svg>
      <div className="num">
        <b style={{ color }}>{Math.round(v)}</b>
        <span>/ 100</span>
      </div>
    </div>
  )
}
