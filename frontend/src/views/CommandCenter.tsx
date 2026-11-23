import type React from 'react'
import { useEffect, useRef, useState } from 'react'
import { ArrowRight, Globe2, Map as MapIcon, Megaphone, MessageSquare, Play, Radar, Search, ShieldCheck, Sparkles, Square, Layers } from 'lucide-react'
import { api, stream } from '../api'
import { HostingBars, UaeMap } from '../components/Maps'
import { useCountUp } from '../hooks'
import { useLang } from '../i18n'
import { SCAM_TYPES, SOURCES, scoreColor, verdictOf } from '../meta'
import type { Candidate, Overview } from '../types'
import type { Nav } from './Investigation'

type Cand = Candidate & { verdict?: string | null; score?: number | null; kind?: string | null; blocked?: boolean }
const ICON: Record<string, React.ReactElement> = { shield: <ShieldCheck size={20} />, search: <Search size={20} />, megaphone: <Megaphone size={20} />, map: <MapIcon size={20} />, message: <MessageSquare size={20} /> }

function FunnelRow({ label, value, total, color, hint }: { label: string; value: number; total: number; color: string; hint?: string }) {
  const v = useCountUp(value, 500)
  const w = value === 0 ? 0 : 5 + 95 * Math.sqrt(value / Math.max(total, 1))
  return (
    <div className="f-row">
      <div className="f-label">{label}{hint && <div className="faint" style={{ fontSize: 11 }}>{hint}</div>}</div>
      <div className="f-bar"><i style={{ width: `${w}%`, background: color }} /></div>
      <div className="f-num" style={{ color }}>{Math.round(v)}</div>
    </div>
  )
}

export function CommandCenter({ nav }: { nav: Nav }) {
  const { p, lang } = useLang()
  const [ov, setOv] = useState<Overview | null>(null)
  const [targets, setTargets] = useState<{ case_id: string; label: string; url: string; truth: string }[]>([])
  const [cands, setCands] = useState<Cand[]>([])
  const [run, setRun] = useState<{ on: boolean; scanned: number; flagged: number; investigated: number; confirmed: number; unblocked: number; total: number; line: string } | null>(null)
  const stop = useRef<(() => void) | null>(null)

  useEffect(() => {
    api.overview().then(setOv)
    api.targets().then((r) => setTargets(r.targets))
    api.candidates().then((r) => setCands(r.candidates as Cand[]))
    return () => stop.current?.()
  }, [])

  const startHunt = () => {
    stop.current?.()
    setCands([])
    setRun({ on: true, scanned: 0, flagged: 0, investigated: 0, confirmed: 0, unblocked: 0, total: ov?.funnel.unique ?? 1, line: '' })
    stop.current = stream('/api/hunt/stream?speed=1.6', (ev) => {
      if (ev.type === 'start') setRun((r) => r && { ...r, total: ev.total })
      if (ev.type === 'candidate') {
        const c: Cand = { ...ev.candidate, verdict: ev.verdict, kind: ev.kind, blocked: ev.blocked }
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

  return (
    <div className="page">
      <div className="hero">
        <div className="card hero-main">
          <div className="eyebrow row"><Radar size={14} /> {p('Proactive scam hunting', 'رصد استباقي للاحتيال')}</div>
          <h2>{p('Find scam sites before citizens click them.', 'اكتشف مواقع الاحتيال قبل أن يضغط عليها المواطنون.')}</h2>
          <p>{p(`Raqib watches Google Search, Google Maps and newly issued certificates for look-alikes of ${ov?.entities ?? 26} protected UAE brands, then investigates the dangerous ones in an isolated browser and links them into campaigns.`, `يراقب رقيب بحث جوجل وخرائط جوجل والشهادات الجديدة بحثاً عن مواقع تنتحل صفة ${ov?.entities ?? 26} جهة إماراتية محمية، ثم يحقق في الخطيرة منها داخل متصفح معزول ويربطها في حملات.`)}</p>
          <div className="row wrap">
            {run?.on
              ? <button className="btn btn-primary" onClick={stopHunt}><Square size={15} /> {p('Stop hunt', 'إيقاف الرصد')}</button>
              : <button className="btn btn-primary" onClick={startHunt} disabled={!ov}><Play size={15} /> {p('Run hunt', 'ابدأ الرصد')}</button>}
            <span className="faint" style={{ fontSize: 12 }}>{p('Demo dataset: recorded feeds and fictional domains.', 'بيانات تجريبية: مصادر مسجّلة ونطاقات وهمية.')}</span>
          </div>
          <div style={{ marginTop: 18 }}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>{p('Or investigate a recorded demo target', 'أو حقّق في هدف تجريبي مسجّل')}</div>
            <div className="row wrap">
              {targets.map((t) => (
                <button key={t.case_id} className={`chip ${t.truth === 'benign' ? 'ok' : 'info'}`} style={{ cursor: 'pointer', padding: '5px 12px' }} onClick={() => nav.investigate(t.url)}>
                  <Play size={11} /> {t.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="card funnel">
          <div className="row between">
            <div className="eyebrow">{p('Detection funnel', 'قمع الاكتشاف')}</div>
            <span className="chip">{run?.on ? <><span className="dot live" /> {p('hunting', 'يرصد')}</> : p('last hunt', 'آخر رصد')}</span>
          </div>
          {view && (
            <>
              <FunnelRow label={p('Candidates scanned', 'مرشّحون تم فحصهم')} hint={p('search · maps · certificates · reports', 'بحث · خرائط · شهادات · بلاغات')} value={view.scanned} total={view.total} color="#6b7aa0" />
              <FunnelRow label={p('Flagged by triage', 'مشتبه بهم بعد الفرز')} hint={`${p('score', 'الدرجة')} ≥ ${ov?.threshold ?? 40}`} value={view.flagged} total={view.total} color="#f5a524" />
              <FunnelRow label={p('Investigated in sandbox', 'فُحصوا في البيئة المعزولة')} value={view.investigated} total={view.total} color="#38bdf8" />
              <FunnelRow label={p('Confirmed scams', 'احتيال مؤكد')} value={view.confirmed} total={view.total} color="#fb4a6c" />
              <FunnelRow label={p('Not on any blocklist', 'غير مدرجة في أي قائمة حجب')} value={view.unblocked} total={view.total} color="#a78bfa" />
            </>
          )}
          <div className="scan-line mono">{run?.on ? `› ${run.line}` : ''}</div>
        </div>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.6fr) minmax(0,1fr)', alignItems: 'start' }}>
        <div className="card">
          <div className="card-h"><Sparkles size={16} color="#f5a524" /><h3>{p('Flagged candidates', 'المرشّحون المشتبه بهم')}</h3><span className="sub right">{cands.length}</span></div>
          <div className="feed">
            {cands.map((c) => {
              const src = SOURCES[c.source] ?? SOURCES.search
              const v = c.verdict ? verdictOf(c.verdict) : null
              const sc = c.triage.score
              return (
                <div key={c.id} className="cand wf-enter">
                  <div className="ico">{ICON[src.icon]}</div>
                  <div style={{ minWidth: 0 }}>
                    <div className="row" style={{ gap: 8 }}><span className="chip">{lang === 'ar' ? src.ar : src.en}</span>{v && <span className={`chip ${v.tone}`}>{lang === 'ar' ? v.ar : v.en}</span>}</div>
                    <h4 className="ellipsis" style={{ marginTop: 6 }}>{c.title}</h4>
                    <div className="mono faint ellipsis" style={{ fontSize: 11.5 }}>{c.host || c.detail}</div>
                    <div className="reasons">{c.triage.reasons.slice(0, 2).map((r) => r.text).join(' · ')}</div>
                  </div>
                  <div className="col" style={{ alignItems: 'center', gap: 6 }}>
                    <div className="score" style={{ color: scoreColor(sc), borderColor: scoreColor(sc) }}>{sc}</div>
                    <button className="btn btn-sm" onClick={() => nav.investigate(c.case_id ? 'case:' + c.case_id : c.host)}>{p('Investigate', 'تحقيق')} <ArrowRight size={13} /></button>
                  </div>
                </div>
              )
            })}
            {!cands.length && <div className="muted" style={{ padding: 20, textAlign: 'center' }}>{run?.on ? p('Scanning… flagged candidates appear here.', 'جارٍ الفحص… يظهر المشتبه بهم هنا.') : p('Run a hunt to discover candidates.', 'ابدأ الرصد لاكتشاف المرشّحين.')}</div>}
          </div>
        </div>

        <div className="col" style={{ gap: 18 }}>
          <div className="card">
            <div className="card-h"><Layers size={16} color="#a78bfa" /><h3>{p('Active campaigns', 'الحملات النشطة')}</h3></div>
            <div className="card-b col" style={{ gap: 10 }}>
              {ov?.clusters.map((c) => (
                <button key={c.cluster_id} className="camp-item" style={{ textAlign: 'start', cursor: 'pointer' }} onClick={() => nav.go('/campaigns')}>
                  <div className="row"><span className="chip violet">{c.cluster_id}</span><b>{SCAM_TYPES[c.headline] ? (lang === 'ar' ? SCAM_TYPES[c.headline].ar : SCAM_TYPES[c.headline].en) : c.headline}</b></div>
                  <div className="row"><span className="chip">{c.size} {p('sites', 'موقعاً')}</span>{c.unblocked > 0 && <span className="chip warn">{c.unblocked} {p('unblocked', 'غير محجوب')}</span>}</div>
                  <div className="why mono">{c.shared_indicators.slice(0, 2).join(' · ') || p('shared contact details', 'بيانات اتصال مشتركة')}</div>
                </button>
              ))}
            </div>
          </div>
          <div className="card">
            <div className="card-h"><MapIcon size={16} color="#fb4a6c" /><h3>{p('Emirates targeted', 'الإمارات المستهدفة')}</h3></div>
            <div className="card-b"><UaeMap counts={ov?.emirates ?? {}} /></div>
          </div>
          <div className="card">
            <div className="card-h"><Globe2 size={16} color="#38bdf8" /><h3>{p('Hosting indicators', 'مؤشرات الاستضافة')}</h3></div>
            <div className="card-b"><HostingBars data={ov?.hosting_countries ?? {}} /></div>
          </div>
        </div>
      </div>
    </div>
  )
}
