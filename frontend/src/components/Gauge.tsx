import { useCountUp } from '../hooks'
import { scoreColor } from '../meta'

export function Gauge({ score, size = 190 }: { score: number; size?: number }) {
  const v = useCountUp(score)
  const color = scoreColor(score)
  const R = 80
  const len = Math.PI * R
  const h = size * 0.62
  const tick = (pct: number) => {
    const a = Math.PI * (1 - pct / 100)
    const x1 = 95 + (R - 10) * Math.cos(a), y1 = 100 - (R - 10) * Math.sin(a)
    const x2 = 95 + (R + 8) * Math.cos(a), y2 = 100 - (R + 8) * Math.sin(a)
    return <line key={pct} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#2a3a5f" strokeWidth="2" strokeLinecap="round" />
  }
  return (
    <div className="gauge" style={{ width: size, height: h }}>
      <svg viewBox="0 0 190 118" width={size} height={h}>
        <defs>
          <linearGradient id="gg" x1="0" x2="1">
            <stop offset="0" stopColor="#34d399" />
            <stop offset="0.45" stopColor="#f5a524" />
            <stop offset="1" stopColor="#fb4a6c" />
          </linearGradient>
        </defs>
        <path d="M 15 100 A 80 80 0 0 1 175 100" fill="none" stroke="#18233f" strokeWidth="13" strokeLinecap="round" />
        <path
          d="M 15 100 A 80 80 0 0 1 175 100" fill="none" stroke="url(#gg)" strokeWidth="13" strokeLinecap="round"
          strokeDasharray={len} strokeDashoffset={len * (1 - v / 100)} style={{ filter: `drop-shadow(0 0 8px ${color}88)` }}
        />
        {[30, 60, 85].map(tick)}
      </svg>
      <div className="num">
        <b style={{ color }}>{Math.round(v)}</b>
        <span>/ 100</span>
      </div>
    </div>
  )
}
