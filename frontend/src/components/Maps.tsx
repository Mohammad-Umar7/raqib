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

export function HostingBars({ data }: { data: Record<string, number> }) {
  const { p } = useLang()
  const rows = Object.entries(data).sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...rows.map((r) => r[1]))
  const NAMES: Record<string, [string, string]> = { NL: ['Netherlands', 'هولندا'], US: ['United States', 'الولايات المتحدة'], DE: ['Germany', 'ألمانيا'], SG: ['Singapore', 'سنغافورة'], TR: ['Türkiye', 'تركيا'], AE: ['UAE', 'الإمارات'] }
  return (
    <div className="col" style={{ gap: 8 }}>
      {rows.map(([cc, n]) => (
        <div key={cc} className="row" style={{ gap: 10 }}>
          <span className="chip mono" style={{ width: 38, justifyContent: 'center' }}>{cc}</span>
          <span className="muted" style={{ width: 118, fontSize: 12.5 }}>{p(NAMES[cc]?.[0] ?? cc, NAMES[cc]?.[1] ?? cc)}</span>
          <div className="grow f-bar"><motion.i initial={{ width: 0 }} animate={{ width: `${(n / max) * 100}%` }} transition={{ duration: 0.8, ease: 'easeOut' }} style={{ background: 'linear-gradient(90deg,#9a8cff,#e5b85c)' }} /></div>
          <b style={{ width: 24, textAlign: 'end' }}>{n}</b>
        </div>
      ))}
      <div className="faint" style={{ fontSize: 11.5, marginTop: 2 }}>{p('Where the servers are. This is an infrastructure indicator, not the location of the people running the scam.', 'مواقع الخوادم فقط، وهو مؤشر تقني ولا يدل على مكان المحتالين.')}</div>
    </div>
  )
}
