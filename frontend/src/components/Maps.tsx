import { motion } from 'framer-motion'
import { useLang } from '../i18n'
import { EMIRATE_AR } from '../meta'

// A stylised tile map of the seven emirates (not geographic precision, just position).
const TILES: Record<string, { x: number; y: number; w: number; h: number }> = {
  'Ras Al Khaimah': { x: 222, y: 12, w: 100, h: 62 },
  'Umm Al Quwain': { x: 150, y: 40, w: 66, h: 46 },
  Fujairah: { x: 330, y: 58, w: 84, h: 104 },
  Ajman: { x: 150, y: 92, w: 66, h: 42 },
  Sharjah: { x: 222, y: 80, w: 102, h: 56 },
  Dubai: { x: 150, y: 140, w: 96, h: 58 },
  'Abu Dhabi': { x: 10, y: 92, w: 134, h: 146 },
}

export function UaeMap({ counts, unit }: { counts: Record<string, number>; unit?: string }) {
  const { lang, p } = useLang()
  const max = Math.max(1, ...Object.values(counts))
  return (
    <svg viewBox="0 0 424 250" width="100%" role="img" aria-label={p('UAE map', 'خريطة الإمارات')}>
      {Object.entries(TILES).map(([name, t]) => {
        const n = counts[name] ?? 0
        const k = n / max
        return (
          <g key={name} className="tile">
            <motion.rect x={t.x} y={t.y} width={t.w} height={t.h} rx={12} initial={{ opacity: 0, scale: 0.9 }} animate={{ opacity: 1, scale: 1, fill: n ? `rgba(251, 74, 108,${0.14 + 0.5 * k})` : '#15151c' }} transition={{ duration: 0.5, delay: Object.keys(TILES).indexOf(name) * 0.06 }} style={{ transformOrigin: `${t.x + t.w / 2}px ${t.y + t.h / 2}px` }} stroke={n ? '#fb4a6c' : '#2c2c38'} strokeOpacity={n ? 0.5 + 0.5 * k : 1} />
            <text x={t.x + t.w / 2} y={t.y + t.h / 2 - (n ? 4 : -4)} textAnchor="middle" fontSize={name === 'Umm Al Quwain' || name === 'Ajman' ? 9 : 11} fontWeight={600} fill={n ? '#ffe3e9' : '#8a8794'}>
              {lang === 'ar' ? EMIRATE_AR[name] : name === 'Ras Al Khaimah' ? 'Ras Al Khaimah' : name}
            </text>
            {n > 0 && <text x={t.x + t.w / 2} y={t.y + t.h / 2 + 14} textAnchor="middle" fontSize={14} fontWeight={800} fill="#fff">{n}{unit ?? ''}</text>}
          </g>
        )
      })}
    </svg>
  )
}
