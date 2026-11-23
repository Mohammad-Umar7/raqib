import { useCallback, useEffect, useMemo, useState } from 'react'
import { Building2, Languages, LayoutDashboard, Network, Radar, Search, Settings, ShieldCheck, Sparkles, X } from 'lucide-react'
import { api } from './api'
import { useLang } from './i18n'
import type { Status } from './types'
import { Campaigns } from './views/Campaigns'
import { CommandCenter } from './views/CommandCenter'
import { Investigation, type Nav } from './views/Investigation'
import { Registry } from './views/Registry'

function parseRoute(): { name: string; id?: string; tab?: string } {
  const [path, query] = (location.hash.replace(/^#/, '') || '/command').split('?')
  const parts = path.split('/').filter(Boolean)
  const tab = new URLSearchParams(query).get('tab') ?? undefined
  if (parts[0] === 'case' && parts[1]) return { name: 'case', id: parts[1], tab }
  return { name: parts[0] || 'command' }
}

function SettingsModal({ status, onClose, onChange }: { status: Status | null; onClose: () => void; onChange: () => void }) {
  const { p } = useLang()
  const [key, setKey] = useState('')
  const [msg, setMsg] = useState<string | null>(null)
  const save = async () => {
    try { await api.setKey(key); setKey(''); setMsg(p('Key saved on this computer. Claude is now writing the case files.', 'تم حفظ المفتاح على هذا الجهاز. يكتب Claude ملفات القضايا الآن.')); onChange() } catch (e: any) { setMsg(e.message) }
  }
  const clear = async () => { await api.clearKey(); setMsg(p('Key removed.', 'تمت إزالة المفتاح.')); onChange() }
  return (
    <div className="modal-back" onClick={onClose}>
      <div className="card modal" onClick={(e) => e.stopPropagation()}>
        <div className="row between"><h2 style={{ margin: 0, fontSize: 18 }}>{p('Settings', 'الإعدادات')}</h2><button className="btn btn-sm btn-ghost" onClick={onClose}><X size={15} /></button></div>
        <div className="field">
          <label>{p('Claude connection', 'الاتصال بـ Claude')}</label>
          <div className="row"><span className={`chip ${status?.claude.enabled ? 'ok' : 'warn'}`}>{status?.claude.enabled ? p('Connected', 'متصل') : p('Offline writer in use', 'الكاتب غير المتصل قيد الاستخدام')}</span>{status?.claude.enabled && <span className="chip mono">{status.claude.model}</span>}</div>
          {status?.claude.last_error && <div className="callout danger" style={{ padding: 10, fontSize: 12 }}>{status.claude.last_error}</div>}
        </div>
        <div className="field">
          <label>{p('Anthropic API key', 'مفتاح Anthropic API')}</label>
          <input className="input mono" type="password" value={key} onChange={(e) => setKey(e.target.value)} placeholder="sk-ant-…" dir="ltr" autoComplete="off" />
          <div className="faint" style={{ fontSize: 12 }}>{p('Stored only in a local .env file that git ignores. It is used for case summaries, the layout of the case view and the live browser agent.', 'يُحفظ فقط في ملف .env محلي يتجاهله git. يُستخدم لملخصات القضايا وتخطيط ملف القضية ووكيل المتصفح المباشر.')}</div>
        </div>
        <div className="row"><button className="btn btn-primary" disabled={key.length < 20} onClick={save}>{p('Save key', 'حفظ المفتاح')}</button>{status?.claude.enabled && <button className="btn" onClick={clear}>{p('Remove key', 'إزالة المفتاح')}</button>}</div>
        {msg && <div className="muted" style={{ marginTop: 12, fontSize: 12.5 }}>{msg}</div>}
        <hr className="hr" />
        <div className="faint" style={{ fontSize: 12 }}>
          {p('Mode', 'الوضع')}: <b>{status?.requested_mode}</b> · Playwright: <b>{status?.playwright ? 'yes' : 'no'}</b> · {p('live browsing', 'التصفح المباشر')}: <b>{status?.live_ready ? p('ready', 'جاهز') : p('off (replay mode)', 'متوقف (وضع الإعادة)')}</b>
        </div>
      </div>
    </div>
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
  const investigate = useCallback(async (target: string, opts: { mode?: string; speed?: number } = {}) => {
    try {
      const r = await api.start(target, opts)
      go(`/case/${r.id}`)
    } catch (e: any) { setToast(e.message); setTimeout(() => setToast(null), 4000) }
  }, [go])
  const nav: Nav = useMemo(() => ({ go, investigate }), [go, investigate])

  const nameOf = (n: string) => ({ command: p('Command', 'القيادة'), case: p('Cases', 'القضايا'), campaigns: p('Campaigns', 'الحملات'), registry: p('Brands', 'الجهات') }[n] ?? n)

  return (
    <div className="shell">
      <aside className="rail">
        <div className="logo" title="Raqib">
          <svg width="26" height="26" viewBox="0 0 64 64"><defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#38bdf8" /><stop offset="1" stopColor="#818cf8" /></linearGradient></defs>
            <path d="M32 8 12 16v15c0 12 8.500 20.500 20 25 11.500-4.500 20-13 20-25V16L32 8Z" fill="none" stroke="url(#lg)" strokeWidth="4" strokeLinejoin="round" /><circle cx="32" cy="30" r="8" fill="none" stroke="url(#lg)" strokeWidth="4" /><circle cx="32" cy="30" r="3" fill="#38bdf8" /></svg>
        </div>
        <button className={`rail-btn ${route.name === 'command' ? 'active' : ''}`} onClick={() => go('/command')}><LayoutDashboard size={20} />{nameOf('command')}</button>
        <button className={`rail-btn ${route.name === 'case' ? 'active' : ''}`} onClick={() => url ? investigate(url) : document.getElementById('analyze-input')?.focus()}><Radar size={20} />{nameOf('case')}</button>
        <button className={`rail-btn ${route.name === 'campaigns' ? 'active' : ''}`} onClick={() => go('/campaigns')}><Network size={20} />{nameOf('campaigns')}</button>
        <button className={`rail-btn ${route.name === 'registry' ? 'active' : ''}`} onClick={() => go('/registry')}><Building2 size={20} />{nameOf('registry')}</button>
        <div className="rail-sp" />
        <button className="rail-btn" onClick={() => setLang(lang === 'en' ? 'ar' : 'en')} title="Language"><Languages size={20} />{lang === 'en' ? 'عربي' : 'EN'}</button>
        <button className="rail-btn" onClick={() => setShowSettings(true)}><Settings size={20} />{p('Settings', 'الإعدادات')}</button>
      </aside>
      <div className="main">
        <header className="topbar">
          <div className="brand"><b>{p('Raqib', 'رقيب')}</b><span>{p('Scam hunting for police', 'رصد الاحتيال للشرطة')}</span></div>
          <form className="analyze" onSubmit={(e) => { e.preventDefault(); if (url.trim()) investigate(url.trim()) }}>
            <Search size={16} color="#5f6f94" />
            <input id="analyze-input" value={url} onChange={(e) => setUrl(e.target.value)} placeholder={p('Paste a suspicious URL to investigate…', 'الصق رابطاً مشبوهاً للتحقيق…')} dir="ltr" spellCheck={false} />
            <button className="btn btn-primary btn-sm" type="submit"><Sparkles size={14} /> {p('Analyze', 'تحليل')}</button>
          </form>
          <div className="row right wrap" style={{ gap: 8 }}>
            <span className="chip"><ShieldCheck size={13} /> {p('Isolated sandbox', 'بيئة معزولة')}</span>
            <button className={`chip ${status?.claude.enabled ? 'violet' : 'warn'}`} style={{ cursor: 'pointer' }} onClick={() => setShowSettings(true)}>
              <span className={`dot ${status?.claude.enabled ? 'live' : 'warn'}`} /> {status?.claude.enabled ? p('Claude connected', 'Claude متصل') : p('Claude offline', 'Claude غير متصل')}
            </button>
            <span className="chip info">{status?.live_ready ? p('Live mode', 'الوضع المباشر') : p('Replay mode', 'وضع الإعادة')}</span>
          </div>
        </header>
        {route.name === 'command' && <CommandCenter nav={nav} />}
        {route.name === 'case' && route.id && <Investigation key={route.id} runId={route.id} nav={nav} initialTab={route.tab} />}
        {route.name === 'campaigns' && <Campaigns nav={nav} />}
        {route.name === 'registry' && <Registry />}
      </div>
      {showSettings && <SettingsModal status={status} onClose={() => setShowSettings(false)} onChange={refresh} />}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}
