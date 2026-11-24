import { motion } from 'framer-motion'
import { useCountUp } from '../hooks'
import { scoreColor } from '../meta'

const R = 80
const cx = 95, cy = 100
const pt = (pct: number, r = R) => {
  const a = Math.PI * (1 - pct / 100)
  return { x: cx + r * Math.cos(a), y: cy - r * Math.sin(a) }
}

export function Gauge({ score, size = 190, final = false }: { score: number; size?: number; final?: boolean }) {
  const v = useCountUp(score, 1100)
  const color = scoreColor(score)
  const h = size * 0.64
  const tip = pt(Math.max(0.5, v))
  return (
    <div className="gauge" style={{ width: size, height: h, ['--gc' as any]: color }}>
      <svg viewBox="0 0 190 122" width={size} height={h}>
        <defs>
          <linearGradient id="gg" x1="15" x2="175" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#34d399" />
            <stop offset="0.45" stopColor="#ff8a3d" />
            <stop offset="1" stopColor="#fb4a6c" />
          </linearGradient>
          <filter id="gglow" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        </defs>
        <path d="M 15 100 A 80 80 0 0 1 175 100" fill="none" stroke="#1c1c24" strokeWidth="13" strokeLinecap="round" />
        {[30, 60, 85].map((t) => {
          const a = pt(t, R - 11), b = pt(t, R + 9), l = pt(t, R + 20)
          return (
            <g key={t}>
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#3a3a46" strokeWidth="2" strokeLinecap="round" />
              <text x={l.x} y={l.y + 3} textAnchor="middle" fontSize="8.5" fill="#6c6a76" fontWeight="600">{t}</text>
            </g>
          )
        })}
        <motion.path d="M 15 100 A 80 80 0 0 1 175 100" fill="none" stroke="url(#gg)" strokeWidth="13" strokeLinecap="round" filter="url(#gglow)"
          initial={{ pathLength: 0 }} animate={{ pathLength: Math.max(0.002, score / 100) }} transition={{ type: 'spring', stiffness: 60, damping: 18 }} />
        {v > 1 && <circle cx={tip.x} cy={tip.y} r="7.5" fill="#fff" stroke={color} strokeWidth="3.5" style={{ filter: `drop-shadow(0 0 7px ${color})` }} />}
      </svg>
      {final && score >= 60 && <span className="gauge-ring" key={score} />}
      <div className="num">
        <b style={{ color }}>{Math.round(v)}</b>
        <span>/ 100</span>
      </div>
    </div>
  )
}
