import { useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Bot, Globe, Lock, ShieldCheck } from 'lucide-react'
import { useLang } from '../i18n'
import type { InvState } from '../hooks'
import { scoreColor } from '../meta'
import type { El } from '../types'
import { Typewriter } from './fx'

interface Cur { x: number; y: number; vis: boolean; label: string }
interface Chip { id: number; x: number; y: number; text: string; tone: 'danger' | 'warn' | 'info' }

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
  return <div className={cls} ref={reg}>{tag}{el.text}</div>
}

export function BrowserPanel({ s }: { s: InvState }) {
  const { p, lang } = useLang()
  const screenRef = useRef<HTMLDivElement>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const refs = useRef(new Map<string, HTMLElement>())
  const [cur, setCur] = useState<Cur>({ x: 150, y: 120, vis: false, label: '' })
  const [ripples, setRipples] = useState<{ id: number; x: number; y: number }[]>([])
  const [chips, setChips] = useState<Chip[]>([])
  const seenSignals = useRef(0)
  const frame = s.frame
  const lastNote = s.notes[s.notes.length - 1]
  const running = !s.done && s.phase !== 'queued' && !s.error
  const risk = scoreColor(s.score)
  const noteText = lastNote ? (lang === 'ar' && lastNote.text_ar ? lastNote.text_ar : lastNote.text) : ''

  useEffect(() => {
    refs.current.clear()
    if (scrollRef.current) scrollRef.current.scrollTop = 0
    if (frame?.kind !== 'image') setCur((c) => ({ ...c, vis: false }))
  }, [frame?.page_id])

  // agent cursor
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
      const t = window.setTimeout(() => sc.scrollTo({ top: 0, behavior: 'smooth' }), 700)
      return () => window.clearTimeout(t)
    }
    sc.scrollTo({ top: Math.max(0, node.offsetTop - 210), behavior: 'smooth' })
    const t = window.setTimeout(() => {
      const r = node.getBoundingClientRect()
      const b = screenRef.current!.getBoundingClientRect()
      const x = r.left - b.left + Math.min(r.width * 0.62, r.width - 14)
      const y = r.top - b.top + r.height / 2
      setCur({ x, y, vis: true, label: c.action === 'click' ? `${p('click', 'نقر')}: ${c.label}` : c.action === 'type' ? `${p('types test value', 'يكتب قيمة تجريبية')}: ${c.label}` : `${p('inspects', 'يفحص')}: ${c.label}` })
      if (c.action === 'click') window.setTimeout(() => setRipples((r0) => [...r0.slice(-3), { id: Date.now(), x, y }]), 700)
    }, 380)
    return () => window.clearTimeout(t)
  }, [s.cursor?.seq])

  // floating "+score" chips when a signal is found
  useEffect(() => {
    if (s.signals.length < seenSignals.current) seenSignals.current = 0
    if (s.signals.length === seenSignals.current) return
    const fresh = s.signals.slice(seenSignals.current)
    seenSignals.current = s.signals.length
    const b = screenRef.current?.getBoundingClientRect()
    fresh.forEach((sig, k) => {
      const ev = sig.evidence.find((e) => e.page && e.element)
      const node = ev ? refs.current.get(`${ev.page}:${ev.element}`) : undefined
      let x = (b?.width ?? 300) - 70, y = 62 + k * 4
      if (node && b) {
        const r = node.getBoundingClientRect()
        x = r.left - b.left + r.width - 40
        y = r.top - b.top + 4
      }
      const id = Date.now() + k
      const short = ev ? s.flagged[`${ev.page}:${ev.element}`]?.tag : ''
      const tone = sig.severity === 'critical' ? 'danger' : sig.severity === 'high' ? 'warn' : 'info'
      setChips((c) => [...c.slice(-5), { id, x, y, text: `+${Math.round(sig.weight * 100)}${short ? ' ' + short : ''}`, tone }])
      window.setTimeout(() => setChips((c) => c.filter((q) => q.id !== id)), 1900)
    })
  }, [s.signals.length])

  return (
    <div className="card browser" dir="ltr">
      <div className="browser-chrome">
        <div className="lights"><i /><i /><i /></div>
        <div className="urlbar">
          <Lock size={12} />
          <AnimatePresence mode="wait" initial={false}>
            <motion.span key={frame?.url ?? 'none'} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -6 }} transition={{ duration: 0.18 }}>
              {frame?.url ?? s.meta?.input_url ?? 'about:blank'}
            </motion.span>
          </AnimatePresence>
        </div>
        <div className="sandbox-tag"><ShieldCheck size={14} /> {p('ISOLATED SANDBOX', 'بيئة معزولة')}</div>
      </div>
      <div className="stage">
        <div className={`phone ${running ? 'running' : ''}`} style={{ ['--risk' as any]: risk }}>
          <div className="screen" ref={screenRef}>
            <div className="screen-scroll" ref={scrollRef} style={frame?.kind === 'image' ? { padding: 0 } : undefined}>
              <AnimatePresence mode="popLayout" initial={false}>
                {frame?.kind === 'image' ? (
                  <img key={frame.page_id} src={`data:image/jpeg;base64,${frame.image}`} alt="" style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill' }} />
                ) : frame ? (
                  <motion.div key={frame.page_id} className="wf" initial={{ opacity: 0, x: 36, filter: 'blur(6px)' }} animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }} exit={{ opacity: 0, x: -36, filter: 'blur(6px)' }} transition={{ duration: 0.32 }}>
                    {frame.elements.map((el, i) => (
                      <motion.div key={el.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 + i * 0.035, duration: 0.3 }}>
                        <Element el={el} flag={s.flagged[`${frame.page_id}:${el.id}`]} reg={(n) => { if (n) refs.current.set(`${frame.page_id}:${el.id}`, n) }} />
                      </motion.div>
                    ))}
                  </motion.div>
                ) : (
                  <div className="empty-stage" style={{ paddingTop: 140 }}>
                    <Globe size={34} className={s.phase === 'queued' ? 'pulse-soft' : ''} />
                    <p>{s.phase === 'queued' ? p('Starting the isolated browser…', 'جارٍ تشغيل المتصفح المعزول…') : s.meta?.mode === 'listing' || s.meta?.mode === 'static' ? p('Nothing to open for this item.', 'لا يوجد شيء لفتحه.') : p('Opening the link…', 'جارٍ فتح الرابط…')}</p>
                  </div>
                )}
              </AnimatePresence>
            </div>
            {frame && <div key={frame.page_id} className="scan-sweep" />}
            <AnimatePresence>
              {chips.map((c) => (
                <motion.div key={c.id} className={`chip-float ${c.tone}`} style={{ left: c.x, top: c.y }} initial={{ opacity: 0, y: 6, scale: 0.7 }} animate={{ opacity: [0, 1, 1, 0], y: -34, scale: 1 }} transition={{ duration: 1.8, times: [0, 0.12, 0.7, 1] }}>
                  {c.text}
                </motion.div>
              ))}
            </AnimatePresence>
            {cur.vis && (
              <>
                <div className="cursor" style={{ transform: `translate(${cur.x - 4}px, ${cur.y - 3}px)` }}>
                  <svg width="22" height="22" viewBox="0 0 22 22"><path d="M3 2l14 7.5-6 1.8-2.2 6.2L3 2z" fill="#fff" stroke="#0b1224" strokeWidth="1.4" strokeLinejoin="round" /></svg>
                  <span className="cursor-label">{cur.label}</span>
                </div>
                {ripples.map((r) => <div key={r.id} className="ripple" style={{ left: r.x, top: r.y }} />)}
              </>
            )}
          </div>
        </div>
      </div>
      <div className="agent-box" dir={lang === 'ar' ? 'rtl' : 'ltr'}>
        <div className="agent-note">
          <div className={`avatar ${running ? 'busy' : ''}`}><Bot size={15} /></div>
          <div style={{ minWidth: 0 }}>
            <div className="eyebrow" style={{ marginBottom: 2 }}>{p('Browser agent', 'وكيل المتصفح')}{running ? ' · ' + p('working', 'يعمل') : ''}</div>
            {noteText ? <Typewriter key={s.notes.length} text={noteText} /> : <span className="faint">{p('Waiting for the first action…', 'بانتظار أول إجراء…')}</span>}
          </div>
        </div>
      </div>
      <div className="reqs">
        <AnimatePresence initial={false}>
          {s.requests.slice(-8).map((r, i) => (
            <motion.div key={`${s.requests.length - 8 + i}:${r.url}`} layout initial={{ opacity: 0, x: -14 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} className={`req ${r.flag ?? ''}`}>
              <b>{r.method}</b>
              <span>{r.status}</span>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{r.url}</span>
              {r.flag === 'kit' && <span className="kit-badge">{p('scam-kit file', 'ملف أدوات احتيال')}</span>}
            </motion.div>
          ))}
        </AnimatePresence>
        {!s.requests.length && <div className="req">{p('network log will appear here', 'سيظهر سجل الشبكة هنا')}</div>}
      </div>
    </div>
  )
}
