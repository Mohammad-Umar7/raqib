import { useEffect, useRef, useState } from 'react'
import { Bot, Globe, Lock, ShieldCheck } from 'lucide-react'
import { useLang } from '../i18n'
import type { InvState } from '../hooks'
import type { El } from '../types'

interface Cur { x: number; y: number; vis: boolean; label: string }

function Element({ el, flag, reg }: { el: El; flag?: { tag: string; soft: boolean }; reg: (n: HTMLElement | null) => void }) {
  const cls = `el ${el.kind}${flag ? (flag.soft ? ' flag soft' : ' flag') : ''}`
  const tag = flag ? <span className={`tag${flag.soft ? ' soft' : ''}`}>{flag.tag}</span> : null
  if (el.kind === 'input' || el.kind === 'select') {
    return (
      <div className={cls} ref={reg}>
        {tag}
        <label>{el.field?.label || el.text}</label>
        <div className="box">{el.field?.type === 'password' ? '••••••••' : el.field?.placeholder || (el.kind === 'select' ? 'Select…' : '')}</div>
      </div>
    )
  }
  return (
    <div className={cls} ref={reg}>
      {tag}
      {el.text}
    </div>
  )
}

export function BrowserPanel({ s }: { s: InvState }) {
  const { p, lang } = useLang()
  const screenRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const refs = useRef(new Map<string, HTMLElement>())
  const [cur, setCur] = useState<Cur>({ x: 150, y: 120, vis: false, label: '' })
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([])
  const frame = s.frame
  const lastNote = s.notes[s.notes.length - 1]
  const running = !s.done && s.phase !== 'queued' && !s.error

  // reset scroll and cursor when a new page loads
  useEffect(() => {
    refs.current.clear()
    if (scrollRef.current) scrollRef.current.scrollTop = 0
    if (frame?.kind !== 'image') setCur((c) => ({ ...c, vis: false }))
  }, [frame?.page_id])

  // move the cursor when the agent acts
  useEffect(() => {
    const c = s.cursor
    if (!c || !frame || !screenRef.current || !scrollRef.current) return
    if (frame.kind === 'image') {
      if (c.x == null || c.y == null) return
      const b = screenRef.current.getBoundingClientRect()
      const x = (c.x / frame.viewport.w) * b.width, y = (c.y / frame.viewport.h) * b.height
      setCur({ x, y, vis: true, label: c.action === 'click' ? `${p('click', 'نقر')}: ${c.label}` : c.action === 'scroll' ? p('scroll', 'تمرير') : `${p('inspects', 'يفحص')}: ${c.label}` })
      if (c.action === 'click') window.setTimeout(() => setRipples((r0) => [...r0.slice(-3), { id: Date.now(), x, y }]), 650)
      return
    }
    const node = c.target ? refs.current.get(`${frame.page_id}:${c.target}`) : undefined
    if (!node) return
    const sc = scrollRef.current
    if (c.action === 'scroll') {
      sc.scrollTo({ top: Math.min(120, sc.scrollHeight - sc.clientHeight), behavior: 'smooth' })
      window.setTimeout(() => sc.scrollTo({ top: 0, behavior: 'smooth' }), 600)
      return
    }
    sc.scrollTo({ top: Math.max(0, node.offsetTop - 210), behavior: 'smooth' })
    const t = window.setTimeout(() => {
      const r = node.getBoundingClientRect()
      const b = screenRef.current!.getBoundingClientRect()
      const x = r.left - b.left + Math.min(r.width * 0.62, r.width - 14)
      const y = r.top - b.top + r.height / 2
      setCur({ x, y, vis: true, label: c.action === 'click' ? `${p('click', 'نقر')}: ${c.label}` : c.action === 'type' ? `${p('types test value', 'يكتب قيمة تجريبية')}: ${c.label}` : `${p('inspects', 'يفحص')}: ${c.label}` })
      if (c.action === 'click') window.setTimeout(() => setRipples((r0) => [...r0.slice(-3), { id: Date.now(), x, y }]), 700)
    }, 360)
    return () => window.clearTimeout(t)
  }, [s.cursor?.seq])

  return (
    <div className="card browser" dir="ltr">
      <div className="browser-chrome">
        <div className="lights"><i /><i /><i /></div>
        <div className="urlbar">
          <Lock size={12} />
          <span>{frame?.url ?? s.meta?.input_url ?? 'about:blank'}</span>
        </div>
        <div className="sandbox-tag"><ShieldCheck size={14} /> {p('ISOLATED SANDBOX', 'بيئة معزولة')}</div>
      </div>
      <div className="stage">
        <div className="phone">
          <div className="screen" ref={screenRef}>
            <div className="screen-scroll" ref={scrollRef} style={frame?.kind === 'image' ? { padding: 0 } : undefined}>
              {frame?.kind === 'image' ? (
                <img src={`data:image/jpeg;base64,${frame.image}`} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill' }} />
              ) : frame ? (
                <div className="wf wf-enter" key={frame.page_id}>
                  {frame.elements.map((el) => (
                    <Element key={el.id} el={el} flag={s.flagged[`${frame.page_id}:${el.id}`]} reg={(n) => { if (n) refs.current.set(`${frame.page_id}:${el.id}`, n) }} />
                  ))}
                </div>
              ) : (
                <div className="empty-stage" style={{ paddingTop: 140 }}>
                  <Globe size={34} />
                  <p>{s.phase === 'queued' ? p('Starting the isolated browser…', 'جارٍ تشغيل المتصفح المعزول…') : s.meta?.mode === 'listing' || s.meta?.mode === 'static' ? p('Nothing to open for this item.', 'لا يوجد شيء لفتحه.') : p('Opening the link…', 'جارٍ فتح الرابط…')}</p>
                </div>
              )}
            </div>
            {cur.vis && (
              <>
                <div className="cursor" style={{ transform: `translate(${cur.x - 4}px, ${cur.y - 3}px)` }}>
                  <svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2l14 7.5-6 1.8-2.2 6.2L3 2z" fill="#fff" stroke="#0b1224" strokeWidth="1.4" strokeLinejoin="round" /></svg>
                  <span style={{ position: 'absolute', insetInlineStart: 20, top: 16, whiteSpace: 'nowrap', fontSize: 10.5, fontWeight: 600, padding: '3px 8px', borderRadius: 8, background: '#6d5ae6', color: '#fff', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis' }}>{cur.label}</span>
                </div>
                {ripples.map((r) => <div key={r.id} className="ripple" style={{ left: r.x, top: r.y }} />)}
              </>
            )}
          </div>
        </div>
      </div>
      <div className="agent-box" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
        <div className="agent-note">
          <div className="avatar"><Bot size={15} /></div>
          <div key={s.notes.length} className="wf-enter">
            <div className="eyebrow" style={{ marginBottom: 2 }}>{p('Browser agent', 'وكيل المتصفح')}{running ? ' · ' + p('working', 'يعمل') : ''}</div>
            {lastNote ? (lang === 'ar' && lastNote.text_ar ? lastNote.text_ar : lastNote.text) : <span className="faint">{p('Waiting for the first action…', 'بانتظار أول إجراء…')}</span>}
          </div>
        </div>
      </div>
      <div className="reqs">
        {s.requests.slice(-8).map((r, i) => (
          <div key={s.requests.length - 8 + i} className={`req ${r.flag ?? ''}`}>
            <b>{r.method}</b>
            <span>{r.status}</span>
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.url}</span>
            {r.flag === 'kit' && <span>{p('· scam-kit file', '· ملف أدوات احتيال')}</span>}
          </div>
        ))}
        {!s.requests.length && <div className="req">{p('network log will appear here', 'سيظهر سجل الشبكة هنا')}</div>}
      </div>
    </div>
  )
}
