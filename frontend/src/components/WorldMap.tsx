import { motion } from 'framer-motion'
import { geoNaturalEarth1, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import world from 'world-atlas/countries-110m.json'
import { useLang } from '../i18n'

const W = 960, H = 470

// [lon, lat] for country markers; ISO numeric id for shading the country itself.
const COUNTRY: Record<string, { ll: [number, number]; id?: string; en: string; ar: string }> = {
  AE: { ll: [54.4, 24.2], id: '784', en: 'UAE', ar: 'الإمارات' },
  NL: { ll: [5.3, 52.1], id: '528', en: 'Netherlands', ar: 'هولندا' },
  US: { ll: [-98.5, 39.5], id: '840', en: 'United States', ar: 'الولايات المتحدة' },
  DE: { ll: [10.4, 51.2], id: '276', en: 'Germany', ar: 'ألمانيا' },
  SG: { ll: [103.8, 1.35], en: 'Singapore', ar: 'سنغافورة' },
  TR: { ll: [35.2, 39.0], id: '792', en: 'Türkiye', ar: 'تركيا' },
  GB: { ll: [-2, 54], id: '826', en: 'United Kingdom', ar: 'المملكة المتحدة' },
  FR: { ll: [2.2, 46.2], id: '250', en: 'France', ar: 'فرنسا' },
  RU: { ll: [60, 57], id: '643', en: 'Russia', ar: 'روسيا' },
  CN: { ll: [104, 35], id: '156', en: 'China', ar: 'الصين' },
  HK: { ll: [114.2, 22.3], en: 'Hong Kong', ar: 'هونغ كونغ' },
  IN: { ll: [78.9, 21], id: '356', en: 'India', ar: 'الهند' },
  RO: { ll: [25, 45.9], id: '642', en: 'Romania', ar: 'رومانيا' },
  BG: { ll: [25.5, 42.7], id: '100', en: 'Bulgaria', ar: 'بلغاريا' },
  UA: { ll: [31.2, 48.4], id: '804', en: 'Ukraine', ar: 'أوكرانيا' },
  CA: { ll: [-106, 56], id: '124', en: 'Canada', ar: 'كندا' },
  JP: { ll: [138, 36], id: '392', en: 'Japan', ar: 'اليابان' },
  BR: { ll: [-52, -10], id: '076', en: 'Brazil', ar: 'البرازيل' },
  SA: { ll: [45, 24], id: '682', en: 'Saudi Arabia', ar: 'السعودية' },
  EG: { ll: [30, 27], id: '818', en: 'Egypt', ar: 'مصر' },
}

const countries = (feature(world as any, (world as any).objects.countries) as any).features.filter((f: any) => f.id !== '010')
const projection = geoNaturalEarth1().fitExtent([[8, 8], [W - 8, H - 8]], { type: 'FeatureCollection', features: countries } as any)
const path = geoPath(projection)
const SHAPES = countries.map((f: any) => ({ id: f.id as string, d: path(f) ?? '' }))
const pt = (cc: string) => projection(COUNTRY[cc]?.ll ?? [0, 0]) ?? [0, 0]

export function WorldMap({ data, compact = false }: { data: Record<string, number>; compact?: boolean }) {
  const { p, lang } = useLang()
  const entries = Object.entries(data).filter(([cc]) => COUNTRY[cc] && cc !== 'AE').sort((a, b) => b[1] - a[1])
  const max = Math.max(1, ...entries.map((e) => e[1]))
  const hot = new Set(Object.keys(data).map((cc) => COUNTRY[cc]?.id).filter(Boolean))
  const [ux, uy] = pt('AE')
  // place labels greedily so neighbouring countries (e.g. NL and DE) never overlap
  const placed: { x: number; y: number; w: number; h: number }[] = [{ x: ux - 60, y: uy + 10, w: 120, h: 20 }]
  const labelAt: Record<string, { x: number; y: number }> = {}
  const LW = lang === 'ar' ? 66 : 74
  for (const [cc, n] of entries) {
    const [x, y] = pt(cc)
    const r = 6 + (n / max) * 6
    const options = [{ x: x + r + 4, y: y - 9 }, { x: x - r - 4 - LW, y: y - 9 }, { x: x - LW / 2, y: y - r - 22 }, { x: x - LW / 2, y: y + r + 4 }, { x: x + r + 4, y: y + 12 }, { x: x - r - 4 - LW, y: y - 30 }]
    const hit = (o: { x: number; y: number }) => placed.some((b) => o.x < b.x + b.w && o.x + LW > b.x && o.y < b.y + b.h && o.y + 18 > b.y)
    const pick = options.find((o) => !hit(o)) ?? options[0]
    placed.push({ x: pick.x, y: pick.y, w: LW, h: 18 })
    labelAt[cc] = pick
  }
  return (
    <div className="worldmap">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={p('Hosting indicators on a world map', 'مؤشرات الاستضافة على خريطة العالم')}>
        <defs>
          <linearGradient id="arcg" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2={W} y2="0"><stop offset="0" stopColor="#e5b85c" /><stop offset="1" stopColor="#fb4a6c" /></linearGradient>
          <radialGradient id="dotg"><stop offset="0" stopColor="#f8e6c2" /><stop offset="1" stopColor="#e5b85c" /></radialGradient>
          <pattern id="wmdots" width="5" height="5" patternUnits="userSpaceOnUse"><circle cx="1.5" cy="1.5" r="0.9" fill="#34333e" /></pattern>
        </defs>
        {SHAPES.map((s: { id: string; d: string }) => (
          <g key={s.id}>
            <path d={s.d} fill={s.id === '784' ? 'rgba(251,74,108,0.38)' : hot.has(s.id) ? 'rgba(229,184,92,0.26)' : '#1a1a22'} stroke={hot.has(s.id) || s.id === '784' ? 'rgba(229,184,92,0.55)' : '#2a2a34'} strokeWidth={0.6} />
            {!hot.has(s.id) && s.id !== '784' && <path d={s.d} fill="url(#wmdots)" stroke="none" />}
          </g>
        ))}
        {entries.map(([cc, n], i) => {
          const [x, y] = pt(cc)
          const mx = (x + ux) / 2, my = Math.min(y, uy) - Math.max(40, Math.abs(x - ux) * 0.22)
          const d = `M ${x} ${y} Q ${mx} ${my} ${ux} ${uy}`
          return (
            <g key={cc}>
              <motion.path d={d} fill="none" stroke="url(#arcg)" strokeWidth={1.2 + (n / max) * 1.8} strokeLinecap="round" initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 0.85 }} transition={{ duration: 1.2, delay: 0.3 + i * 0.15, ease: 'easeInOut' }} />
              <path d={d} fill="none" stroke="#fff" strokeWidth="1.3" className="flow" opacity="0.5" />
              <motion.circle cx={x} cy={y} fill="url(#dotg)" initial={{ r: 0 }} animate={{ r: 4 + (n / max) * 6 }} transition={{ type: 'spring', stiffness: 260, damping: 14, delay: 0.2 + i * 0.15 }} />
              <circle cx={x} cy={y} r={6 + (n / max) * 6} fill="none" stroke="#e5b85c" className="wm-pulse" style={{ animationDelay: `${i * 0.3}s` }} />
              {!compact && (
                <g>
                  <rect x={labelAt[cc].x} y={labelAt[cc].y} width={LW} height="18" rx="9" fill="rgba(12,12,16,0.92)" stroke="rgba(229,184,92,0.45)" />
                  <text x={labelAt[cc].x + LW / 2} y={labelAt[cc].y + 12.5} textAnchor="middle" fontSize="10.5" fontWeight="650" fill="#f2d39a">{cc} · {n} {p('sites', 'مواقع')}</text>
                </g>
              )}
            </g>
          )
        })}
        <g>
          <circle cx={ux} cy={uy} r="7" fill="#fb4a6c" />
          <circle cx={ux} cy={uy} r="7" fill="none" stroke="#fb4a6c" className="wm-ping" />
          <circle cx={ux} cy={uy} r="7" fill="none" stroke="#fb4a6c" className="wm-ping" style={{ animationDelay: '1s' }} />
          <text x={ux} y={uy + 24} textAnchor="middle" fontSize="11" fontWeight="700" fill="#ff9bb0">{p('Victims in the UAE', 'الضحايا في الإمارات')}</text>
        </g>
      </svg>
      <div className="wm-legend">
        <span><i className="g" /> {p('Server location (hosting)', 'موقع الخادم (الاستضافة)')}</span>
        <span><i className="r" /> {p('Targeted residents', 'السكان المستهدفون')}</span>
        <span className="faint">{p('Infrastructure indicator only, not where the scammers are.', 'مؤشر تقني فقط، ولا يدل على مكان المحتالين.')}</span>
      </div>
      {!compact && entries.length > 0 && (
        <div className="wm-list">
          {entries.map(([cc, n]) => (
            <span key={cc} className="chip"><b className="mono" style={{ color: '#f2d39a' }}>{cc}</b> {lang === 'ar' ? COUNTRY[cc].ar : COUNTRY[cc].en} · {n}</span>
          ))}
        </div>
      )}
    </div>
  )
}
