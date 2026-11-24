import type React from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Globe2, Layers, Map as MapIcon, Megaphone, MessageSquare, Play, Radar as RadarIcon, Search, ShieldCheck, Sparkles, Square } from 'lucide-react'
import { api, stream } from '../api'
import { UaeMap } from '../components/Maps'
import { WorldMap } from '../components/WorldMap'
import { LiveHunt } from '../components/LiveHunt'
import { Num, Rise, soft, spring } from '../components/fx'
import { Radar, type Dot } from '../components/Radar'
import { useLang } from '../i18n'
import { SCAM_TYPES, SOURCES, scoreColor, verdictOf } from '../meta'
import type { Candidate, Overview } from '../types'
import type { Nav } from './Investigation'

type Cand = Candidate & { verdict?: string | null; score?: number | null; kind?: string | null; blocked?: boolean }
const ICON: Record<string, React.ReactElement> = { shield: <ShieldCheck size={20} />, search: <Search size={20} />, megaphone: <Megaphone size={20} />, map: <MapIcon size={20} />, message: <MessageSquare size={20} /> }

function Ring({ value }: { value: number }) {
  const r = 20, len = 2 * Math.PI * r
  const c = scoreColor(value)
  return (
    <svg width="50" height="50" viewBox="0 0 50 50" style={{ flex: 'none' }}>
      <circle cx="25" cy="25" r={r} fill="none" stroke="#1d1d26" strokeWidth="4" />
      <motion.circle cx="25" cy="25" r={r} fill="none" stroke={c} strokeWidth="4" strokeLinecap="round" transform="rotate(-90 25 25)" strokeDasharray={len}
        initial={{ strokeDashoffset: len }} animate={{ strokeDashoffset: len * (1 - value / 100) }} transition={{ duration: 0.9, ease: 'easeOut' }} />
      <text x="25" y="29.5" textAnchor="middle" fontSize="13" fontWeight="750" fill={c}>{value}</text>
    </svg>
  )
}

function Step({ label, hint, value, of, color, i }: { label: string; hint?: string; value: number; of: number; color: string; i: number }) {
  const pct = of > 0 ? Math.round((value / of) * 100) : 0
  return (
    <motion.div className="fstep" style={{ ['--fc' as any]: color }} initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ ...soft, delay: i * 0.07 }}>
      <div className="fs-top"><span>{label}</span>{i > 0 && of > 0 && <em>{pct}%</em>}</div>
      <div className="fs-num"><Num value={value} ms={420} /></div>
      <div className="fs-bar"><motion.i animate={{ width: `${Math.max(value > 0 ? 6 : 0, Math.min(100, (value / Math.max(of, 1)) * 100))}%` }} transition={{ duration: 0.5 }} /></div>
      {hint && <div className="fs-hint">{hint}</div>}
    </motion.div>
  )
}

export function CommandCenter({ nav }: { nav: Nav }) {
  const { p, lang } = useLang()
  const [ov, setOv] = useState<Overview | null>(null)
  const [targets, setTargets] = useState<{ case_id: string; label: string; url: string; truth: string }[]>([])
  const [cands, setCands] = useState<Cand[]>([])
  const [dots, setDots] = useState<Dot[]>([])
  const [speed, setSpeed] = useState(1.6)
  const [run, setRun] = useState<{ on: boolean; scanned: number; flagged: number; investigated: number; confirmed: number; unblocked: number; total: number; line: string } | null>(null)
  const stop = useRef<(() => void) | null>(null)

  useEffect(() => {
    api.overview().then(setOv)
    api.targets().then((r) => setTargets(r.targets))
    api.candidates().then((r) => setCands(r.candidates as Cand[]))
    return () => stop.current?.()
  }, [])

  // idle radar: the last hunt, drawn from the overview and flagged list
  const idleDots = useMemo<Dot[]>(() => {
    if (!ov) return []
    const flagged: Dot[] = cands.map((c) => ({ id: c.id, source: c.source, flagged: true, verdict: c.verdict, host: c.host || c.title, case_id: c.case_id }))
    const srcs = ['ct', 'search', 'maps', 'report']
    const quiet: Dot[] = Array.from({ length: Math.min(160, Math.max(0, ov.funnel.scanned - ov.funnel.flagged)) }, (_, i) => ({ id: `q${i}`, source: srcs[i % 4], flagged: false, host: '' }))
    return [...quiet, ...flagged]
  }, [ov, cands])

  const startHunt = () => {
    stop.current?.()
    setCands([])
    setDots([])
    setRun({ on: true, scanned: 0, flagged: 0, investigated: 0, confirmed: 0, unblocked: 0, total: ov?.funnel.unique ?? 1, line: '' })
    stop.current = stream(`/api/hunt/stream?speed=${speed}`, (ev) => {
      if (ev.type === 'start') setRun((r) => r && { ...r, total: ev.total })
      if (ev.type === 'candidate') {
        const c: Cand = { ...ev.candidate, verdict: ev.verdict, kind: ev.kind, blocked: ev.blocked }
        setDots((d) => [...d.slice(-220), { id: c.id, source: c.source, flagged: ev.flagged, verdict: ev.verdict, host: c.host || c.title, case_id: c.case_id }])
        setRun((r) => {
          if (!r) return r
          const conf = ev.verdict === 'confirmed_scam' || ev.verdict === 'likely_scam'
          return { ...r, scanned: ev.n, line: c.host || c.title, flagged: r.flagged + (ev.flagged ? 1 : 0), investigated: r.investigated + (ev.flagged && c.case_id ? 1 : 0),
            confirmed: r.confirmed + (ev.flagged && conf ? 1 : 0), unblocked: r.unblocked + (ev.flagged && conf && ev.kind === 'site' && !ev.blocked ? 1 : 0) }
        })
        if (ev.flagged) setCands((cs) => [c, ...cs].slice(0, 60))
      }
      if (ev.type === 'done') setRun((r) => r && { ...r, on: false, line: '' })
    }, () => setRun((r) => r && { ...r, on: false }))
  }
  const stopHunt = () => { stop.current?.(); setRun((r) => r && { ...r, on: false, line: '' }) }

  const fn = ov?.funnel
  const view = run ?? (fn && { on: false, scanned: fn.unique, flagged: fn.flagged, investigated: fn.investigated, confirmed: fn.confirmed, unblocked: fn.unblocked, total: fn.unique, line: '' })
  const radarDots = run ? dots : idleDots

  return (
    <div className="page">
      <div className="hero">
        <Rise>
          <div className="card hero-main">
            <div className="eyebrow row"><RadarIcon size={14} /> {p('Proactive scam hunting', 'رصد استباقي للاحتيال')}</div>
            <h2>{p('Find scam sites before citizens click them.', 'اكتشف مواقع الاحتيال قبل أن يضغط عليها المواطنون.')}</h2>
            <p>{p(`Raqib watches Google Search, Google Maps and newly issued certificates for look-alikes of ${ov?.entities ?? 26} protected UAE brands, then investigates the dangerous ones in an isolated browser and links them into campaigns.`, `يراقب رقيب بحث جوجل وخرائط جوجل والشهادات الجديدة بحثاً عن مواقع تنتحل صفة ${ov?.entities ?? 26} جهة إماراتية محمية، ثم يحقق في الخطيرة منها داخل متصفح معزول ويربطها في حملات.`)}</p>
            <div className="row wrap">
              {run?.on
                ? <button className="btn btn-primary" onClick={stopHunt}><Square size={15} /> {p('Stop hunt', 'إيقاف الرصد')}</button>
                : <button className="btn btn-primary pulse-btn" onClick={startHunt} disabled={!ov}><Play size={15} /> {p('Run hunt', 'ابدأ الرصد')}</button>}
              <div className="seg" role="group" aria-label="speed">
                {[1.6, 4, 10].map((v) => <button key={v} className={speed === v ? 'on' : ''} onClick={() => setSpeed(v)}>{v === 1.6 ? '1×' : v === 4 ? '2.5×' : '6×'}</button>)}
              </div>
            </div>
            <div className="faint" style={{ fontSize: 12, marginTop: 10 }}>{p('Demo dataset: recorded feeds and fictional domains.', 'بيانات تجريبية: مصادر مسجّلة ونطاقات وهمية.')}</div>
            <div style={{ marginTop: 20 }}>
              <div className="eyebrow" style={{ marginBottom: 8 }}>{p('Or investigate a recorded demo target', 'أو حقّق في هدف تجريبي مسجّل')}</div>
              <div className="row wrap">
                {targets.map((t, i) => (
                  <motion.button key={t.case_id} className={`chip ${t.truth === 'benign' ? 'ok' : 'info'} chip-btn`} onClick={() => nav.investigate(t.url)} initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} transition={{ ...spring, delay: 0.3 + i * 0.05 }} whileHover={{ y: -2 }} whileTap={{ scale: 0.95 }}>
                    <Play size={11} /> {t.label}
                  </motion.button>
                ))}
              </div>
            </div>
          </div>
        </Rise>
        <Rise i={1}>
          <div className="card radar-card">
            <div className="row between" style={{ padding: '14px 18px 0' }}>
              <div className="eyebrow">{p('Hunt radar', 'رادار الرصد')}</div>
              <span className="chip">{run?.on ? <><span className="dot live" /> {p('hunting', 'يرصد')}</> : p('last hunt', 'آخر رصد')}</span>
            </div>
            <Radar dots={radarDots} running={!!run?.on} confirmed={view?.confirmed ?? 0} onPick={(d) => d.case_id && nav.investigate('case:' + d.case_id)} />
            <div className="scan-line mono">{run?.on ? `› ${run.line}` : p('Click a red blip to investigate it', 'اضغط على نقطة حمراء للتحقيق فيها')}</div>
          </div>
        </Rise>
      </div>

      {view && (
        <div className="funnel-row">
          <Step i={0} label={p('Candidates scanned', 'مرشّحون تم فحصهم')} hint={p('search · maps · certificates · reports', 'بحث · خرائط · شهادات · بلاغات')} value={view.scanned} of={view.total} color="#75737f" />
          <Step i={1} label={p('Flagged by triage', 'مشتبه بهم بعد الفرز')} hint={`${p('score', 'الدرجة')} ≥ ${ov?.threshold ?? 40}`} value={view.flagged} of={view.scanned} color="#ff8a3d" />
          <Step i={2} label={p('Investigated in sandbox', 'فُحصوا في البيئة المعزولة')} value={view.investigated} of={view.flagged} color="#e5b85c" />
          <Step i={3} label={p('Confirmed scams', 'احتيال مؤكد')} value={view.confirmed} of={view.investigated} color="#fb4a6c" />
          <Step i={4} label={p('Not on any blocklist', 'غير مدرجة في أي قائمة حجب')} hint={p('still live, no public block', 'ما زالت تعمل دون حجب')} value={view.unblocked} of={view.confirmed} color="#a78bfa" />
        </div>
      )}

      <Rise i={2}><div style={{ marginBottom: 18 }}><LiveHunt onScan={(h) => nav.investigate(h)} /></div></Rise>

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)', alignItems: 'start' }}>
        <div className="card">
          <div className="card-h"><Sparkles size={16} color="#ff8a3d" /><h3>{p('Flagged candidates', 'المرشّحون المشتبه بهم')}</h3><span className="chip right"><Num value={cands.length} ms={250} /></span></div>
          <div className="feed">
            <AnimatePresence initial={false}>
              {cands.map((c) => {
                const src = SOURCES[c.source] ?? SOURCES.search
                const v = c.verdict ? verdictOf(c.verdict) : null
                return (
                  <motion.div key={c.id} layout className="cand" initial={{ opacity: 0, y: -26, scale: 0.95 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0 }} transition={spring} whileHover={{ x: lang === 'ar' ? -3 : 3 }}>
                    <div className="ico">{ICON[src.icon]}</div>
                    <div style={{ minWidth: 0 }}>
                      <div className="row" style={{ gap: 8 }}><span className="chip">{lang === 'ar' ? src.ar : src.en}</span>{v && <span className={`chip ${v.tone}`}>{lang === 'ar' ? v.ar : v.en}</span>}</div>
                      <h4 className="ellipsis" style={{ marginTop: 6 }}>{c.title}</h4>
                      <div className="mono faint ellipsis" style={{ fontSize: 11.5 }}>{c.host || c.detail}</div>
                      <div className="reasons">{c.triage.reasons.slice(0, 2).map((r) => r.text).join(' · ')}</div>
                    </div>
                    <div className="col" style={{ alignItems: 'center', gap: 6 }}>
                      <Ring value={c.triage.score} />
                      <button className="btn btn-sm" onClick={() => nav.investigate(c.case_id ? 'case:' + c.case_id : c.host)}>{p('Investigate', 'تحقيق')} <ArrowRight size={13} /></button>
                    </div>
                  </motion.div>
                )
              })}
            </AnimatePresence>
            {!cands.length && <div className="muted" style={{ padding: 20, textAlign: 'center' }}>{run?.on ? p('Scanning… flagged candidates appear here.', 'جارٍ الفحص… يظهر المشتبه بهم هنا.') : p('Run a hunt to discover candidates.', 'ابدأ الرصد لاكتشاف المرشّحين.')}</div>}
          </div>
        </div>

        <div className="col" style={{ gap: 18 }}>
          <Rise i={2}>
            <div className="card">
              <div className="card-h"><Layers size={16} color="#a78bfa" /><h3>{p('Active campaigns', 'الحملات النشطة')}</h3></div>
              <div className="card-b col" style={{ gap: 10 }}>
                {ov?.clusters.map((c, i) => (
                  <motion.button key={c.cluster_id} className="camp-item" style={{ textAlign: 'start', cursor: 'pointer' }} onClick={() => nav.go('/campaigns')} initial={{ opacity: 0, x: 18 }} animate={{ opacity: 1, x: 0 }} transition={{ ...spring, delay: 0.2 + i * 0.07 }} whileHover={{ y: -2 }}>
                    <div className="row"><span className="chip violet">{c.cluster_id}</span><b>{SCAM_TYPES[c.headline] ? (lang === 'ar' ? SCAM_TYPES[c.headline].ar : SCAM_TYPES[c.headline].en) : c.headline}</b></div>
                    <div className="row"><span className="chip">{c.size} {p('sites', 'موقعاً')}</span>{c.unblocked > 0 && <span className="chip warn">{c.unblocked} {p('unblocked', 'غير محجوب')}</span>}</div>
                    <div className="why mono">{c.shared_indicators.slice(0, 2).join(' · ') || p('shared contact details', 'بيانات اتصال مشتركة')}</div>
                  </motion.button>
                ))}
              </div>
            </div>
          </Rise>
        </div>
      </div>

      <div className="grid-2 map-row" style={{ gridTemplateColumns: 'minmax(0,1fr) minmax(0,1.9fr)', marginTop: 18, alignItems: 'stretch' }}>
        <Rise i={3}>
          <div className="card" style={{ height: '100%' }}>
            <div className="card-h"><MapIcon size={16} color="#fb4a6c" /><h3>{p('Emirates targeted', 'الإمارات المستهدفة')}</h3><span className="sub">{p('confirmed scams by emirate', 'الاحتيال المؤكد حسب الإمارة')}</span></div>
            <div className="card-b"><UaeMap counts={ov?.emirates ?? {}} /></div>
          </div>
        </Rise>
        <Rise i={4}>
          <div className="card" style={{ height: '100%' }}>
            <div className="card-h"><Globe2 size={16} color="#e5b85c" /><h3>{p('Scam infrastructure worldwide', 'البنية التحتية للاحتيال حول العالم')}</h3><span className="sub">{p('where the servers are, pointed at who they target', 'مواقع الخوادم ومن تستهدف')}</span></div>
            <div className="card-b"><WorldMap data={ov?.hosting_countries ?? {}} /></div>
          </div>
        </Rise>
      </div>
    </div>
  )
}
