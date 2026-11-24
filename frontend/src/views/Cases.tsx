import { useEffect, useMemo, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, FolderOpen, Network, Search, Sparkles } from 'lucide-react'
import { api } from '../api'
import { spring } from '../components/fx'
import { useLang } from '../i18n'
import { SCAM_TYPES, scoreColor, verdictOf } from '../meta'
import type { Nav } from './Investigation'

export interface CaseRow {
  id: string; started: number; finished: boolean; input_url: string; host: string; label: string; score: number | null; verdict: string | null
  scam_type: string | null; brand: string | null; cluster_id: string | null; related: number; mode: string; source: string | null
}

function ago(ts: number, p: (en: string, ar: string) => string): string {
  const s = Math.max(0, Date.now() / 1000 - ts)
  if (s < 60) return p('just now', 'الآن')
  if (s < 3600) return `${Math.round(s / 60)} ${p('min ago', 'دقيقة')}`
  if (s < 86400) return `${Math.round(s / 3600)} ${p('h ago', 'ساعة')}`
  return `${Math.round(s / 86400)} ${p('d ago', 'يوم')}`
}

function Score({ v }: { v: number | null }) {
  const r = 19, len = 2 * Math.PI * r
  const c = v == null ? '#6c6a76' : scoreColor(v)
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" style={{ flex: 'none' }}>
      <circle cx="24" cy="24" r={r} fill="none" stroke="#1e1e27" strokeWidth="4" />
      {v != null && <motion.circle cx="24" cy="24" r={r} fill="none" stroke={c} strokeWidth="4" strokeLinecap="round" transform="rotate(-90 24 24)" strokeDasharray={len}
        initial={{ strokeDashoffset: len }} animate={{ strokeDashoffset: len * (1 - v / 100) }} transition={{ duration: 0.9, ease: 'easeOut' }} />}
      <text x="24" y="28.5" textAnchor="middle" fontSize="13" fontWeight="750" fill={c}>{v ?? '…'}</text>
    </svg>
  )
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
            <button key={k} className={filter === k ? 'on' : ''} onClick={() => setFilter(k)}>{label} <span className="faint">{n}</span></button>
          ))}
        </div>
        <div className="search-box"><Search size={14} /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder={p('Search cases…', 'ابحث في القضايا…')} /></div>
      </div>

      {rows === null ? (
        <div className="case-grid">{Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton" style={{ height: 150, borderRadius: 18 }} />)}</div>
      ) : shown.length ? (
        <div className="case-grid">
          <AnimatePresence initial={false}>
            {shown.map((r, i) => {
              const v = r.verdict ? verdictOf(r.verdict) : null
              const st = r.scam_type ? SCAM_TYPES[r.scam_type] : null
              return (
                <motion.button key={r.id} layout className={`case-card ${v?.tone ?? ''}`} onClick={() => nav.go(`/case/${r.id}`)}
                  initial={{ opacity: 0, y: 18, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0 }} transition={{ ...spring, delay: Math.min(i, 10) * 0.04 }} whileHover={{ y: -4 }}>
                  <div className="row" style={{ alignItems: 'flex-start', gap: 12 }}>
                    <Score v={r.finished ? r.score : null} />
                    <div className="grow" style={{ minWidth: 0 }}>
                      <div className="mono ellipsis cc-host">{r.host || r.input_url}</div>
                      <div className="faint ellipsis" style={{ fontSize: 12 }}>{r.input_url}</div>
                      <div className="row wrap" style={{ gap: 6, marginTop: 8 }}>
                        {v && <span className={`chip ${v.tone}`}>{lang === 'ar' ? v.ar : v.en}</span>}
                        {!r.finished && <span className="chip info"><span className="dot live" /> {p('running', 'قيد التشغيل')}</span>}
                        {st && r.verdict !== 'no_indicators' && <span className="chip">{lang === 'ar' ? st.ar : st.en}</span>}
                      </div>
                    </div>
                  </div>
                  <div className="cc-foot">
                    {r.brand && r.verdict !== 'no_indicators' && <span>{p('Imitates', 'ينتحل')} <b>{r.brand}</b></span>}
                    {r.cluster_id && <span className="row" style={{ gap: 5 }}><Network size={12} /> {r.cluster_id} · {r.related}</span>}
                    {r.source === 'claude' && <span className="row" style={{ gap: 5, color: '#c4b5fd' }}><Sparkles size={12} /> Claude</span>}
                    <span className="right faint">{ago(r.started, p)}</span>
                    <ArrowRight size={14} className="cc-go" />
                  </div>
                </motion.button>
              )
            })}
          </AnimatePresence>
        </div>
      ) : (
        <div className="empty-big">
          <FolderOpen size={38} />
          <h3>{rows.length ? p('No case matches', 'لا توجد قضية مطابقة') : p('No investigations yet', 'لا توجد تحقيقات بعد')}</h3>
          <p className="muted">{p('Paste a suspicious link in the bar above, or start one from the command centre.', 'الصق رابطاً مشبوهاً في الشريط أعلاه، أو ابدأ من مركز القيادة.')}</p>
          <button className="btn btn-primary" onClick={() => nav.go('/command')}>{p('Go to command centre', 'إلى مركز القيادة')} <ArrowRight size={14} /></button>
        </div>
      )}
    </div>
  )
}
