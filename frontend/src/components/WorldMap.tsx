import { motion } from 'framer-motion'
import { geoNaturalEarth1, geoPath } from 'd3-geo'
import { feature } from 'topojson-client'
import world from 'world-atlas/countries-110m.json'
import { useLang } from '../i18n'
import { RISK } from '../meta'

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
  const LW = lang === 'ar' ? 68 : 76
  for (const [cc, n] of entries) {
    const [x, y] = pt(cc)
    const r = 4 + (n / max) * 4
    const options = [{ x: x + r + 4, y: y - 10 }, { x: x - r - 4 - LW, y: y - 10 }, { x: x - LW / 2, y: y - r - 24 }, { x: x - LW / 2, y: y + r + 4 }, { x: x + r + 4, y: y + 12 }, { x: x - r - 4 - LW, y: y - 32 }]
    const hit = (o: { x: number; y: number }) => placed.some((b) => o.x < b.x + b.w && o.x + LW > b.x && o.y < b.y + b.h && o.y + 20 > b.y)
    const pick = options.find((o) => !hit(o)) ?? options[0]
    placed.push({ x: pick.x, y: pick.y, w: LW, h: 20 })
    labelAt[cc] = pick
  }
  return (
    <div className="worldmap">
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={p('Hosting indicators on a world map', 'مؤشرات الاستضافة على خريطة العالم')}>
        {SHAPES.map((s: { id: string; d: string }) => (
          <path key={s.id} d={s.d} fill={s.id === '784' ? 'rgba(229,72,77,0.35)' : hot.has(s.id) ? '#2b2b2e' : '#1e1e20'} stroke={hot.has(s.id) ? 'rgba(237,237,237,0.2)' : 'rgba(237,237,237,0.06)'} strokeWidth={0.6} />
        ))}
        {entries.map(([cc, n], i) => {
          const [x, y] = pt(cc)
          const mx = (x + ux) / 2, my = Math.min(y, uy) - Math.max(40, Math.abs(x - ux) * 0.22)
          const d = `M ${x} ${y} Q ${mx} ${my} ${ux} ${uy}`
          return (
            <g key={cc}>
              <motion.path d={d} fill="none" stroke={RISK.high} strokeOpacity={0.45} strokeWidth={1 + (n / max) * 1.5} strokeLinecap="round" initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 0.9, delay: 0.2 + i * 0.08, ease: [0.22, 1, 0.36, 1] }} />
              <circle cx={x} cy={y} r={3 + (n / max) * 4} fill="#a1a1a6" stroke="#19191b" strokeWidth="1.5" />
              {!compact && (
                <g>
                  <rect x={labelAt[cc].x} y={labelAt[cc].y} width={LW} height="20" rx="4" fill="#19191b" stroke="rgba(237,237,237,0.14)" />
                  <text x={labelAt[cc].x + LW / 2} y={labelAt[cc].y + 14} textAnchor="middle" fontSize="11" fill="#a1a1a6" style={{ fontVariantNumeric: 'tabular-nums' }}>{cc} · {n} {p('sites', 'مواقع')}</text>
                </g>
              )}
            </g>
          )
        })}
        <g>
          <circle cx={ux} cy={uy} r="6" fill={RISK.high} stroke="#19191b" strokeWidth="2" />
          <text x={ux} y={uy + 24} textAnchor="middle" fontSize="12" fill="#ededed">{p('Victims in the UAE', 'الضحايا في الإمارات')}</text>
        </g>
      </svg>
      <div className="wm-legend">
        <span><i className="g" /> {p('Server location (hosting)', 'موقع الخادم (الاستضافة)')}</span>
        <span><i className="r" /> {p('Targeted residents', 'السكان المستهدفون')}</span>
        <span className="faint">{p('Infrastructure indicator only, not where the scammers are', 'مؤشر تقني فقط، ولا يدل على مكان المحتالين')}</span>
      </div>
      {!compact && entries.length > 0 && (
        <div className="wm-list">
          {entries.map(([cc, n]) => (
            <span key={cc} className="chip"><span className="mono">{cc}</span> {lang === 'ar' ? COUNTRY[cc].ar : COUNTRY[cc].en} · <span className="num">{n}</span></span>
          ))}
        </div>
      )}
    </div>
  )
}
