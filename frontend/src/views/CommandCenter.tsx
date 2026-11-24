import type React from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Map as MapIcon, Megaphone, MessageSquare, Play, Search, ShieldCheck, Square } from 'lucide-react'
import { api, stream } from '../api'
import { WorldMap } from '../components/WorldMap'
import { LiveHunt } from '../components/LiveHunt'
import { Num, Rise, soft } from '../components/fx'
import { Radar, type Dot } from '../components/Radar'
import { useLang } from '../i18n'
import { SCAM_TYPES, SOURCES, scoreColor, verdictOf } from '../meta'
import type { Candidate, Overview } from '../types'
import type { Nav } from './Investigation'

type Cand = Candidate & { verdict?: string | null; score?: number | null; kind?: string | null; blocked?: boolean }
const ICON: Record<string, React.ReactElement> = { shield: <ShieldCheck size={14} strokeWidth={1.5} />, search: <Search size={14} strokeWidth={1.5} />, megaphone: <Megaphone size={14} strokeWidth={1.5} />, map: <MapIcon size={14} strokeWidth={1.5} />, message: <MessageSquare size={14} strokeWidth={1.5} /> }

function Step({ label, sub, value, tone }: { label: string; sub?: string; value: number; tone?: string }) {
  return (
    <div>
      <div className="fig-label">{label}</div>
      <div className="fig" style={tone ? { color: tone } : undefined}><Num value={value} ms={420} /></div>
      {sub && <div className="fig-sub">{sub}</div>}
    </div>
  )
}

export function CommandCenter({ nav }: { nav: Nav }) {
  const { p, lang } = useLang()
  const [ov, setOv] = useState<Overview | null>(null)
  const [targets, setTargets] = useState<{ case_id: string; label: string; url: string; truth: string }[]>([])
  const [cands, setCands] = useState<Cand[]>([])
  const [dots, setDots] = useState<Dot[]>([])
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
    stop.current = stream('/api/hunt/stream?speed=1.6', (ev) => {
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
  const pct = (a: number, b: number) => (b > 0 ? Math.round((a / b) * 100) : 0)

  return (
    <div className="page">
      <div className="hero">
        <Rise>
          <div className="hero-main">
            <div className="eyebrow">{p('Proactive scam hunting', 'رصد استباقي للاحتيال')}</div>
            <h2>{p('Find scam sites before citizens click them', 'اكتشف مواقع الاحتيال قبل أن يضغط عليها المواطنون')}</h2>
            <p>{p(`Raqib watches newly registered domains, Google Search ads and Google Maps listings for look-alikes of ${ov?.entities ?? 36} protected UAE brands, then investigates the dangerous ones in an isolated browser and links them into campaigns.`, `يراقب رقيب النطاقات المسجلة حديثاً وإعلانات بحث جوجل ومواقع خرائط جوجل بحثاً عن مواقع تنتحل صفة ${ov?.entities ?? 36} جهة إماراتية محمية، ثم يحقق في الخطيرة منها داخل متصفح معزول ويربطها في حملات.`)}</p>
            <div className="row wrap" style={{ gap: 16 }}>
              {run?.on
                ? <button className="btn btn-lg" onClick={stopHunt}><Square size={14} strokeWidth={1.5} /> {p('Stop hunt', 'إيقاف الرصد')}</button>
                : <button className="btn btn-primary btn-lg" onClick={startHunt} disabled={!ov}><Play size={14} strokeWidth={1.5} className="flip-rtl" /> {p('Run hunt', 'ابدأ الرصد')}</button>}
              <span className="hero-note">{p('Demo dataset: recorded feeds and fictional domains', 'بيانات تجريبية: مصادر مسجّلة ونطاقات وهمية')}</span>
            </div>
            <div className="targets">
              <div className="eyebrow">{p('Or open a recorded demo target', 'أو افتح هدفاً تجريبياً مسجّلاً')}</div>
              <div className="targets-grid">
                {targets.map((t) => (
                  <button key={t.case_id} className="target" onClick={() => nav.investigate(t.url)}>
                    <span className={`dot ${t.truth === 'benign' ? 'ok' : 'danger'}`} style={{ width: 6, height: 6 }} />
                    <span className="ellipsis">{t.label}</span>
                    <ArrowRight size={14} className="go flip-rtl" />
                  </button>
                ))}
              </div>
            </div>
          </div>
        </Rise>
        <Rise i={1}>
          <div className="card radar-card">
            <div className="card-h">
              <h3>{p('Hunt radar', 'رادار الرصد')}</h3>
              <span className="row right" style={{ fontSize: 13 }}>{run?.on ? <><span className="dot live" /> {p('Hunting', 'يرصد')}</> : p('Last hunt', 'آخر رصد')}</span>
            </div>
            <Radar dots={radarDots} running={!!run?.on} confirmed={view?.confirmed ?? 0} onPick={(d) => d.case_id && nav.investigate('case:' + d.case_id)} />
            <div className={`radar-foot ${run?.on ? 'mono' : ''}`}>{run?.on ? run.line : p('Click a red point to open its investigation', 'اضغط على نقطة حمراء لفتح التحقيق')}</div>
          </div>
        </Rise>
      </div>

      {view && (
        <Rise i={2}>
          <div className="card funnel">
            <Step label={p('Candidates scanned', 'مرشّحون تم فحصهم')} sub={p('New domains, search, maps and reports', 'نطاقات جديدة وبحث وخرائط وبلاغات')} value={view.scanned} />
            <Step label={p('Flagged by triage', 'مشتبه بهم بعد الفرز')} sub={`${pct(view.flagged, view.scanned)}% ${p('of scanned', 'من المفحوصين')} · ${p('score', 'الدرجة')} ≥ ${ov?.threshold ?? 40}`} value={view.flagged} />
            <Step label={p('Investigated in sandbox', 'فُحصوا في البيئة المعزولة')} sub={`${pct(view.investigated, view.flagged)}% ${p('of flagged', 'من المشتبه بهم')}`} value={view.investigated} />
            <Step label={p('Confirmed scams', 'احتيال مؤكد')} sub={`${pct(view.confirmed, view.investigated)}% ${p('of investigated', 'ممن جرى التحقيق فيهم')}`} value={view.confirmed} />
            <Step label={p('Not on any blocklist', 'غير مدرجة في أي قائمة حجب')} sub={p('Still live, no public block', 'ما زالت تعمل دون حجب')} value={view.unblocked} tone={view.unblocked > 0 ? 'var(--red)' : undefined} />
          </div>
        </Rise>
      )}

      <Rise i={3}><LiveHunt onScan={(h) => nav.investigate(h)} /></Rise>

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)' }}>
        <div className="card">
          <div className="card-h"><h3>{p('Flagged candidates', 'المرشّحون المشتبه بهم')}</h3><span className="right mono num" style={{ fontSize: 12 }}><Num value={cands.length} ms={250} /></span></div>
          <div className="feed list">
            <AnimatePresence initial={false}>
              {cands.map((c) => {
                const src = SOURCES[c.source] ?? SOURCES.search
                const v = c.verdict ? verdictOf(c.verdict) : null
                return (
                  <motion.div key={c.id} className="cand list-row" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={soft}>
                    <div className="score-n" style={{ color: scoreColor(c.triage.score) }}>{c.triage.score}</div>
                    <div style={{ minWidth: 0 }}>
                      <h4 className="ellipsis">{c.title}</h4>
                      <div className="meta">
                        <span className="mono ellipsis">{c.host || c.detail}</span>
                        <span>{ICON[src.icon]} {lang === 'ar' ? src.ar : src.en}</span>
                        {v && <span><span className={`dot ${v.tone}`} style={{ width: 6, height: 6 }} /> {lang === 'ar' ? v.ar : v.en}</span>}
                      </div>
                      <div className="reasons ellipsis">{c.triage.reasons.slice(0, 2).map((r) => r.text).join(' · ')}</div>
                    </div>
                    <button className="btn btn-sm" onClick={() => nav.investigate(c.case_id ? 'case:' + c.case_id : c.host)}>{p('Investigate', 'تحقيق')}</button>
                  </motion.div>
                )
              })}
            </AnimatePresence>
            {!cands.length && <div className="empty">{run?.on ? p('Scanning. Flagged candidates appear here.', 'جارٍ الفحص. يظهر المشتبه بهم هنا.') : p('Run a hunt to discover candidates', 'ابدأ الرصد لاكتشاف المرشّحين')}</div>}
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>{p('Active campaigns', 'الحملات النشطة')}</h3><span className="right mono num" style={{ fontSize: 12 }}>{ov?.clusters.length ?? 0}</span></div>
          <div className="list">
            {ov?.clusters.map((c) => (
              <button key={c.cluster_id} className="list-row camp-row" onClick={() => nav.go('/campaigns')}>
                <span className="tag-id">{c.cluster_id}</span>
                <b>{SCAM_TYPES[c.headline] ? (lang === 'ar' ? SCAM_TYPES[c.headline].ar : SCAM_TYPES[c.headline].en) : c.headline}</b>
                <span className="counts">{c.size} {p('sites', 'موقعاً')}{c.unblocked > 0 && <> · <span style={{ color: 'var(--red)' }}>{c.unblocked} {p('not blocklisted', 'غير محجوب')}</span></>}</span>
                <span className="why">{c.shared_indicators.slice(0, 2).join(' · ') || p('shared contact details', 'بيانات اتصال مشتركة')}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-h"><h3>{p('Scam infrastructure worldwide', 'البنية التحتية للاحتيال حول العالم')}</h3><span className="sub">{p('Where the servers are, not where the operators are', 'مواقع الخوادم لا مواقع المحتالين')}</span></div>
        <div className="card-b"><WorldMap data={ov?.hosting_countries ?? {}} /></div>
      </div>
    </div>
  )
}
