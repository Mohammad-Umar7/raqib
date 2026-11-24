import { useCallback, useEffect, useState } from 'react'
import { ArrowRight, Check, Inbox as InboxIcon, Pause, Play, X } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import { ACTION_KIND, ACTION_STATUS, RADAR_STATE, SCAM_TYPES, SOURCES, ago, scoreColor } from '../meta'
import type { RadarItem, RadarSnap } from '../types'
import type { Nav } from './Investigation'

type View = 'approval' | 'auto' | 'confirmed' | 'watching' | 'activity'

export function RadarRow({ r, nav, onDecide, compact }: { r: RadarItem; nav: Nav; onDecide?: (d: string, ok: boolean) => void; compact?: boolean }) {
  const { p, lang } = useLang()
  const st = RADAR_STATE[r.state] ?? RADAR_STATE.queued
  const src = SOURCES[r.sources[0]] ?? SOURCES.ct
  const score = r.score ?? r.triage
  const pending = r.actions.some((a) => a.status === 'pending')
  const type = r.scam_type && r.state === 'confirmed' ? SCAM_TYPES[r.scam_type] : null
  return (
    <div className={`list-row rx-row ${compact ? 'compact' : ''}`}>
      <span className="score-n" style={{ color: r.score != null ? scoreColor(score) : 'var(--text-3)' }} title={r.score != null ? p('Sandbox score', 'درجة الفحص') : p('Triage score (not opened yet)', 'درجة الفرز (لم يُفتح بعد)')}>{score}</span>
      <div style={{ minWidth: 0 }}>
        <div className="row" style={{ gap: 8, minWidth: 0 }}>
          <span className="mono ellipsis rx-dom">{r.domain}</span>
          <span className="rx-state"><span className={`dot ${st.tone}`} style={{ width: 6, height: 6 }} />{lang === 'ar' ? st.ar : st.en}</span>
        </div>
        <div className="rx-sub ellipsis">
          {lang === 'ar' ? src.ar : src.en}{r.brand ? ` · ${p('imitates', 'ينتحل')} ${r.brand}` : ''}{type ? ` · ${lang === 'ar' ? type.ar : type.en}` : ''}
          {r.why ? ` · ${r.why}` : ''}{r.state === 'watching' && r.next_check ? ` · ${p('next check', 'الفحص التالي')} ${ago(r.next_check, p)}` : ''} · {ago(r.first_seen, p)}
        </div>
        {!compact && r.actions.length > 0 && (
          <div className="rx-acts">
            {r.actions.map((a) => {
              const s = ACTION_STATUS[a.status]
              return <span key={a.id} className={`chip ${s.tone}`} title={a.draft?.subject ?? ''}>{lang === 'ar' ? ACTION_KIND[a.kind]?.ar : ACTION_KIND[a.kind]?.en}: {lang === 'ar' ? s.ar : s.en}</span>
            })}
          </div>
        )}
      </div>
      <div className="row" style={{ gap: 6 }}>
        {onDecide && pending && <button className="btn btn-sm" onClick={() => onDecide(r.domain, true)}><Check size={13} /> {p('Approve', 'موافقة')}</button>}
        {onDecide && r.state === 'confirmed' && <button className="btn btn-sm btn-ghost" onClick={() => onDecide(r.domain, false)}><X size={13} /> {p('Not a scam', 'ليس احتيالاً')}</button>}
        {r.run_id && <button className="btn btn-sm" onClick={() => nav.go(`/case/${r.run_id}`)}>{p('Case', 'القضية')} <ArrowRight size={13} className="flip-rtl" /></button>}
      </div>
    </div>
  )
}

export function Inbox({ nav }: { nav: Nav }) {
  const { p, lang } = useLang()
  const [snap, setSnap] = useState<RadarSnap | null>(null)
  const [items, setItems] = useState<RadarItem[] | null>(null)
  const [view, setView] = useState<View>('approval')

  const load = useCallback(() => {
    api.radar().then(setSnap).catch(() => {})
    if (view !== 'activity') api.radarItems(view).then((r) => setItems(r.items)).catch(() => setItems([]))
  }, [view])
  useEffect(() => { setItems(null); load(); const id = window.setInterval(load, 4000); return () => window.clearInterval(id) }, [load])

  const decide = async (d: string, ok: boolean) => { await api.radarDecide(d, ok); load() }
  const control = async (body: { paused?: boolean; auto_actions?: boolean }) => setSnap(await api.radarControl(body))

  const t = snap?.today ?? {}
  const s = snap?.states ?? {}
  const tabs: [View, string, number | null][] = [
    ['approval', p('Waiting for you', 'بانتظارك'), snap?.pending ?? 0],
    ['auto', p('Auto-actioned', 'إجراء تلقائي'), null],
    ['confirmed', p('Confirmed', 'مؤكد'), (s.confirmed ?? 0) + (s.down ?? 0)],
    ['watching', p('Watching', 'تحت المراقبة'), (s.queued ?? 0) + (s.checking ?? 0) + (s.watching ?? 0)],
    ['activity', p('Audit log', 'سجل التدقيق'), null],
  ]
  const figs: [string, number][] = [
    [p('Names checked today', 'أسماء فُحصت اليوم'), (t.names ?? 0) + (t.nrd ?? 0)],
    [p('Flagged', 'مشتبه بها'), t.flagged ?? 0],
    [p('Opened in sandbox', 'فُتحت في البيئة المعزولة'), t.scanned ?? 0],
    [p('Confirmed scams', 'احتيال مؤكد'), t.confirmed ?? 0],
    [p('Auto-actioned', 'إجراء تلقائي'), t.auto ?? 0],
    [p('Gone offline', 'توقفت'), t.down ?? 0],
  ]

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <div className="eyebrow">{p('Radar inbox', 'صندوق الرادار')}</div>
          <h1>{p('Inbox', 'الوارد')}</h1>
          <p>{p('What the radar found on its own. Only hard evidence is actioned automatically; everything else, and every takedown, waits for you. Nothing leaves Raqib: reports are drafts.',
            'ما وجده الرادار بنفسه. الأدلة القاطعة فقط تُعالج تلقائياً، وكل ما عداها وكل طلبات الإيقاف تنتظرك. لا يخرج شيء من رقيب: البلاغات مسودات.')}</p>
        </div>
        <div className="seg" role="group" aria-label={p('Automatic actions', 'الإجراءات التلقائية')}>
          <button className={snap?.auto_actions ? 'on' : ''} onClick={() => control({ auto_actions: true })}>{p('Auto-actions on', 'الإجراء التلقائي مفعّل')}</button>
          <button className={snap && !snap.auto_actions ? 'on' : ''} onClick={() => control({ auto_actions: false })}>{p('Everything to me', 'كل شيء لي')}</button>
        </div>
        {snap?.paused
          ? <button className="btn btn-primary" onClick={() => control({ paused: false })}><Play size={14} className="flip-rtl" /> {p('Resume radar', 'استئناف الرادار')}</button>
          : <button className="btn" onClick={() => control({ paused: true })}><Pause size={14} /> {p('Pause radar', 'إيقاف الرادار')}</button>}
      </div>

      <div className="card rx-figs">
        {figs.map(([label, v]) => <div key={label}><div className="fig-label">{label}</div><div className="fig">{v.toLocaleString(lang === 'ar' ? 'ar-AE' : 'en-US')}</div></div>)}
      </div>

      <div className="seg" role="tablist">
        {tabs.map(([k, label, n]) => <button key={k} role="tab" aria-selected={view === k} className={view === k ? 'on' : ''} onClick={() => setView(k)}>{label}{n != null && <span className="faint num">{n}</span>}</button>)}
      </div>

      {view === 'activity' ? (
        <div className="card list">
          {(snap?.events ?? []).map((e) => (
            <div key={e.id} className="list-row rx-ev"><span className="faint num">{new Date(e.ts * 1000).toLocaleTimeString(lang === 'ar' ? 'ar-AE' : 'en-GB', { hour: '2-digit', minute: '2-digit' })}</span><span>{e.text}</span></div>
          ))}
          {!snap?.events.length && <div className="empty">{p('Nothing logged yet', 'لا يوجد سجل بعد')}</div>}
        </div>
      ) : items === null ? (
        <div className="card card-p col" style={{ gap: 12 }}>{Array.from({ length: 4 }, (_, i) => <div key={i} className="skeleton" style={{ height: 48 }} />)}</div>
      ) : items.length ? (
        <div className="card list">{items.map((r) => <RadarRow key={r.domain} r={r} nav={nav} onDecide={decide} />)}</div>
      ) : (
        <div className="card empty-big">
          <InboxIcon size={32} strokeWidth={1.5} />
          <h3>{view === 'approval' ? p('Nothing waits for you', 'لا شيء بانتظارك') : p('Nothing here yet', 'لا شيء هنا بعد')}</h3>
          <p className="muted" style={{ margin: 0 }}>{p('The radar keeps watching. New finds appear here without anyone pasting a link.', 'يواصل الرادار المراقبة. تظهر الاكتشافات الجديدة هنا دون أن يلصق أحد رابطاً.')}</p>
        </div>
      )}
    </div>
  )
}
