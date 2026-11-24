import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, FolderOpen, Search } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import { SCAM_TYPES, scoreColor, verdictOf } from '../meta'
import type { Nav } from './Investigation'

export interface CaseRow {
  id: string; started: number; finished: boolean; input_url: string; host: string; label: string; score: number | null; verdict: string | null
  scam_type: string | null; brand: string | null; cluster_id: string | null; related: number; mode: string; source: string | null
}

function ago(ts: number, p: (en: string, ar: string) => string): string {
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 60) return p('Just now', 'الآن')
  if (s < 3600) return `${Math.round(s / 60)} ${p('min ago', 'دقيقة')}`
  if (s < 86400) return `${Math.round(s / 3600)} ${p('h ago', 'ساعة')}`
  return `${Math.round(s / 86400)} ${p('d ago', 'يوم')}`
}

export function Cases({ nav }: { nav: Nav }) {
  const { p, lang } = useLang()
  const [rows, setRows] = useState<CaseRow[] | null>(null)
  const [q, setQ] = useState('')
  const [filter, setFilter] = useState<'all' | 'scam' | 'clean'>('all')

  useEffect(() => {
    const load = () => api.cases().then((r) => setRows(r.investigations)).catch(() => setRows([]))
    load()
    const id = window.setInterval(load, 5000)
    return () => window.clearInterval(id)
  }, [])

  const shown = useMemo(() => (rows ?? []).filter((r) => {
    const scam = r.verdict === 'confirmed_scam' || r.verdict === 'likely_scam'
    if (filter === 'scam' && !scam) return false
    if (filter === 'clean' && scam) return false
    return (r.input_url + r.host + (r.brand ?? '') + (r.label ?? '')).toLowerCase().includes(q.toLowerCase())
  }), [rows, q, filter])
  const scams = (rows ?? []).filter((r) => r.verdict === 'confirmed_scam' || r.verdict === 'likely_scam').length

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <div className="eyebrow">{p('Case files', 'ملفات القضايا')}</div>
          <h1>{p('Investigations', 'التحقيقات')}</h1>
          <p>{p('Every link Raqib has investigated, newest first. Open one to replay the investigation and its case file.', 'كل الروابط التي حقق فيها رقيب، الأحدث أولاً. افتح أياً منها لإعادة عرض التحقيق وملف القضية.')}</p>
        </div>
        <div className="seg">
          {([['all', p('All', 'الكل'), rows?.length ?? 0], ['scam', p('Scams', 'احتيال'), scams], ['clean', p('Clean', 'سليم'), (rows?.length ?? 0) - scams]] as const).map(([k, label, n]) => (
            <button key={k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)}>{label} <span className="faint num">{n}</span></button>
          ))}
        </div>
        <div className="search-box"><Search size={14} strokeWidth={1.5} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={p('Search cases', 'ابحث في القضايا')} aria-label={p('Search cases', 'ابحث في القضايا')} /></div>
      </div>

      {rows === null ? (
        <div className="card card-p col" style={{ gap: 12 }}>{Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton" style={{ height: 40 }} />)}</div>
      ) : shown.length ? (
        <div className="card">
          <div className="cases-grid cases-head">
            <span>{p('Score', 'الدرجة')}</span><span>{p('Site', 'الموقع')}</span><span>{p('Verdict', 'الحكم')}</span>
            <span className="c-type">{p('Scam type', 'نوع الاحتيال')}</span><span className="c-brand">{p('Imitates', 'ينتحل')}</span><span className="c-camp">{p('Campaign', 'الحملة')}</span>
            <span>{p('Started', 'البدء')}</span><span />
          </div>
          <div className="list">
            {shown.map((r) => {
              const v = r.verdict ? verdictOf(r.verdict) : null
              const st = r.scam_type ? SCAM_TYPES[r.scam_type] : null
              const flaggedType = st && r.verdict !== 'no_indicators'
              return (
                <button key={r.id} className="list-row case-row cases-grid" onClick={() => nav.go(`/case/${r.id}`)}>
                  <span className="score-n" style={{ color: r.finished && r.score != null ? scoreColor(r.score) : 'var(--text-3)', fontSize: 15 }}>{r.finished ? r.score ?? '–' : '…'}</span>
                  <span style={{ minWidth: 0 }}>
                    <div className="host ellipsis">{r.host || r.input_url}</div>
                    <div className="sub ellipsis">{r.input_url}</div>
                  </span>
                  <span className="cell row" style={{ gap: 8 }}>
                    {!r.finished ? <><span className="dot live" style={{ width: 6, height: 6 }} />{p('Running', 'قيد التشغيل')}</> : v ? <><span className={`dot ${v.tone}`} style={{ width: 6, height: 6 }} />{lang === 'ar' ? v.ar : v.en}</> : '–'}
                  </span>
                  <span className="cell c-type">{flaggedType ? (lang === 'ar' ? st.ar : st.en) : '–'}</span>
                  <span className="cell c-brand">{r.brand && r.verdict !== 'no_indicators' ? r.brand : '–'}</span>
                  <span className="cell c-camp">{r.cluster_id ? <span className="row" style={{ gap: 8 }}><span className="tag-id">{r.cluster_id}</span><span className="num">{r.related}</span></span> : '–'}</span>
                  <span className="cell faint">{ago(r.started, p)}</span>
                  <ArrowRight size={14} className="go flip-rtl" />
                </button>
              )
            })}
          </div>
        </div>
      ) : (
        <div className="card empty-big">
          <FolderOpen size={32} strokeWidth={1.5} />
          <h3>{rows.length ? p('No case matches', 'لا توجد قضية مطابقة') : p('No investigations yet', 'لا توجد تحقيقات بعد')}</h3>
          <p className="muted" style={{ margin: '0 0 8px' }}>{p('Paste a suspicious link in the bar above, or start one from Command', 'الصق رابطاً مشبوهاً في الشريط أعلاه، أو ابدأ من صفحة القيادة')}</p>
          <button className="btn btn-primary" onClick={() => nav.go('/command')}>{p('Go to Command', 'إلى القيادة')} <ArrowRight size={14} className="flip-rtl" /></button>
        </div>
      )}
    </div>
  )
}
