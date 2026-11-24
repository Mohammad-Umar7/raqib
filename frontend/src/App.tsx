import { useCallback, useEffect, useMemo, useState } from 'react'
import { AnimatePresence, MotionConfig, motion } from 'framer-motion'
import { ArrowRight, Building2, FlaskConical, FolderSearch, Languages, LayoutDashboard, Network, Search, Settings, X } from 'lucide-react'
import { api } from './api'
import { useLang } from './i18n'
import type { Status } from './types'
import { Campaigns } from './views/Campaigns'
import { CommandCenter } from './views/CommandCenter'
import { Investigation, type Nav } from './views/Investigation'
import { Registry } from './views/Registry'
import { Cases } from './views/Cases'
import { Batch } from './views/Batch'
import { ease, soft } from './components/fx'

function parseRoute(): { name: string; id?: string; tab?: string } {
  const [path, query] = (location.hash.replace(/^#/, '') || '/command').split('?')
  const parts = path.split('/').filter(Boolean)
  const tab = new URLSearchParams(query).get('tab') ?? undefined
  if (parts[0] === 'case' && parts[1]) return { name: 'case', id: parts[1], tab }
  return { name: parts[0] || 'command' }
}

/** Raqib's mark: a shield with a watching eye, drawn flat in brass. */
export function Mark({ size = 20 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true">
      <path d="M32 8 12 16v15c0 12 8.5 20.5 20 25 11.5-4.5 20-13 20-25V16L32 8Z" fill="none" stroke="#c9a35b" strokeWidth="4.5" strokeLinejoin="round" />
      <circle cx="32" cy="30" r="7" fill="none" stroke="#c9a35b" strokeWidth="4.5" />
      <circle cx="32" cy="30" r="2.5" fill="#c9a35b" />
    </svg>
  )
}

function SettingsModal({ status, onClose, onChange }: { status: Status | null; onClose: () => void; onChange: () => void }) {
  const { p } = useLang()
  const [key, setKey] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const save = async () => {
    try { await api.setKey(key); setKey(''); setMsg(p('Key saved on this computer. Claude now writes the case files.', 'تم حفظ المفتاح على هذا الجهاز. يكتب Claude ملفات القضايا الآن.')); onChange() } catch (e: any) { setMsg(e.message) }
  }
  const clear = async () => { await api.clearKey(); setMsg(p('Key removed', 'تمت إزالة المفتاح')); onChange() }
  return (
    <motion.div className="modal-back" onClick={onClose} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.16, ease }}>
      <motion.div className="card modal" onClick={(e) => e.stopPropagation()} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 4 }} transition={{ duration: 0.2, ease }}>
        <div className="row between"><h2>{p('Settings', 'الإعدادات')}</h2><button className="btn btn-sm btn-ghost" onClick={onClose} aria-label={p('Close', 'إغلاق')}><X size={16} /></button></div>
        <div className="field">
          <label>{p('Claude connection', 'الاتصال بـ Claude')}</label>
          <div className="row"><span className={`chip ${status?.claude.enabled ? 'ok' : 'warn'}`}>{status?.claude.enabled ? p('Connected', 'متصل') : p('Offline writer in use', 'الكاتب غير المتصل قيد الاستخدام')}</span>{status?.claude.enabled && <span className="chip mono">{status.claude.model}</span>}</div>
          {status?.claude.last_error && <div className="callout card danger" style={{ padding: 12, fontSize: 12 }}>{status.claude.last_error}</div>}
        </div>
        <div className="field">
          <label htmlFor="api-key">{p('Anthropic API key', 'مفتاح Anthropic API')}</label>
          <input id="api-key" className="input mono" type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-ant-…" dir="ltr" autoComplete="off" />
          <div className="faint" style={{ fontSize: 12 }}>{p('Stored only in a local .env file that git ignores. It is used for case summaries, the layout of the case view and the live browser agent.', 'يُحفظ فقط في ملف .env محلي يتجاهله git. يُستخدم لملخصات القضايا وتخطيط ملف القضية ووكيل المتصفح المباشر.')}</div>
        </div>
        <div className="row"><button className="btn btn-primary" disabled={key.length < 20} onClick={save}>{p('Save key', 'حفظ المفتاح')}</button>{status?.claude.enabled && <button className="btn" onClick={clear}>{p('Remove key', 'إزالة المفتاح')}</button>}</div>
        {msg && <div className="muted" style={{ marginTop: 12, fontSize: 13 }}>{msg}</div>}
        <hr className="hr" />
        <div className="faint" style={{ fontSize: 12 }}>
          {p('Mode', 'الوضع')}: <span className="mono">{status?.requested_mode}</span> · Playwright: <span className="mono">{status?.playwright ? 'yes' : 'no'}</span> · {p('Claude browser agent', 'وكيل متصفح Claude')}: {status?.live_ready ? p('on', 'مفعّل') : p('off, the real scanner is used', 'متوقف، يُستخدم الفاحص الحقيقي')}
        </div>
      </motion.div>
    </motion.div>
  )
}

export default function App() {
  const { lang, setLang, p } = useLang()
  const [route, setRoute] = useState(parseRoute())
  const [status, setStatus] = useState<Status | null>(null)
  const [url, setUrl] = useState('')
  const [showSettings, setShowSettings] = useState(false)
  const [toast, setToast] = useState<string | null>(null)

  const refresh = useCallback(() => { api.status().then(setStatus).catch(() => {}) }, [])
  useEffect(() => { refresh() }, [refresh])
  useEffect(() => {
    const on = () => { setRoute(parseRoute()); window.scrollTo({ top: 0 }) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])

  const go = useCallback((r: string) => { location.hash = '#' + r }, [])
  const [busy, setBusy] = useState(false)
  const investigate = useCallback(async (target: string, opts: { mode?: string; speed?: number } = {}) => {
    setBusy(true)
    try {
      const r = await api.start(target, opts)
      go(`/case/${r.id}`)
    } catch (e: any) { setToast(e.message); setTimeout(() => setToast(null), 4000) } finally { setBusy(false) }
  }, [go])
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === '/' && !(e.target instanceof HTMLInputElement) && !(e.target instanceof HTMLTextAreaElement)) { e.preventDefault(); document.getElementById('analyze-input')?.focus() }
    }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [])
  const nav: Nav = useMemo(() => ({ go, investigate }), [go, investigate])

  const items = [
    { k: 'command', icon: <LayoutDashboard size={16} strokeWidth={1.5} />, label: p('Command', 'القيادة'), to: '/command' },
    { k: 'cases', icon: <FolderSearch size={16} strokeWidth={1.5} />, label: p('Cases', 'القضايا'), to: '/cases' },
    { k: 'campaigns', icon: <Network size={16} strokeWidth={1.5} />, label: p('Campaigns', 'الحملات'), to: '/campaigns' },
    { k: 'batch', icon: <FlaskConical size={16} strokeWidth={1.5} />, label: p('Evaluate', 'التقييم'), to: '/batch' },
    { k: 'registry', icon: <Building2 size={16} strokeWidth={1.5} />, label: p('Brands', 'الجهات'), to: '/registry' },
  ]
  const isActive = (k: string) => route.name === k || (k === 'cases' && route.name === 'case')

  return (
    <MotionConfig reducedMotion="user">
    <div className="shell">
      <aside className="side">
        <div className="side-brand" title={p('Raqib · Scam hunting for police', 'رقيب · رصد الاحتيال للشرطة')}><Mark /><b>{p('Raqib', 'رقيب')}</b><span>{p('رقيب', 'Raqib')}</span></div>
        {items.map((it) => (
          <button key={it.k} className={`nav ${isActive(it.k) ? 'active' : ''}`} onClick={() => go(it.to)} title={it.label} aria-current={isActive(it.k) ? 'page' : undefined}>
            {isActive(it.k) && <motion.span layoutId="nav-ind" className="nav-ind" transition={{ duration: 0.2, ease }} />}
            <span>{it.icon}<em>{it.label}</em></span>
          </button>
        ))}
        <div className="side-sp" />
        <button className="nav" onClick={() => setShowSettings(true)} title={p('Claude connection', 'الاتصال بـ Claude')}>
          <span><span className={`dot ${status?.claude.enabled ? 'ok' : 'warn'}`} style={{ margin: '0 4px' }} /><em>{status?.claude.enabled ? p('Claude connected', 'Claude متصل') : p('Claude offline', 'Claude غير متصل')}</em></span>
        </button>
        <button className="nav" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')} title={p('Language', 'اللغة')}><span><Languages size={16} strokeWidth={1.5} /><em>{lang === 'en' ? 'العربية' : 'English'}</em></span></button>
        <button className="nav" onClick={() => setShowSettings(true)} title={p('Settings', 'الإعدادات')}><span><Settings size={16} strokeWidth={1.5} /><em>{p('Settings', 'الإعدادات')}</em></span></button>
      </aside>
      <div className="main">
        <header className="topbar">
          <form className="analyze" onSubmit={(e) => { e.preventDefault(); if (url.trim()) investigate(url.trim()) }}>
            <Search size={16} strokeWidth={1.5} />
            <input id="analyze-input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder={p('Paste a suspicious URL', 'الصق رابطاً مشبوهاً')} dir="ltr" spellCheck={false} aria-label={p('Suspicious URL', 'رابط مشبوه')} />
            {!url && <span className="kbd" aria-hidden="true">/</span>}
            <button className="btn btn-primary btn-sm" type="submit" disabled={busy || !url.trim()}>{p('Investigate', 'تحقيق')} <ArrowRight size={14} className="flip-rtl" /></button>
          </form>
        </header>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div key={route.name + (route.id ?? '')} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={soft}>
            {route.name === 'command' && <CommandCenter nav={nav} />}
            {route.name === 'case' && route.id && <Investigation key={route.id} runId={route.id} nav={nav} initialTab={route.tab} />}
            {route.name === 'cases' && <Cases nav={nav} />}
            {route.name === 'batch' && <Batch nav={nav} />}
            {route.name === 'campaigns' && <Campaigns nav={nav} />}
            {route.name === 'registry' && <Registry />}
          </motion.div>
        </AnimatePresence>
      </div>
      <AnimatePresence>{showSettings && <SettingsModal status={status} onClose={() => setShowSettings(false)} onChange={refresh} />}</AnimatePresence>
      <AnimatePresence>{toast && <motion.div className="toast" role="status" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={soft}>{toast}</motion.div>}</AnimatePresence>
    </div>
    </MotionConfig>
  )
}
