import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Send, Sparkles } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import type { Block } from '../types'
import { BlockRenderer, type BlockActions } from './Blocks'
import { Typewriter, spring } from './fx'

interface Msg { role: 'q' | 'a'; text: string; blocks?: Block[]; source?: string; typed?: boolean }

export function AskPanel({ runId, act, followUps }: { runId: string; act: BlockActions; followUps: { q: string; q_ar: string }[] }) {
  const { p, lang } = useLang()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const [showBlocks, setShowBlocks] = useState<Record<number, boolean>>({})
  const end = useRef<HTMLDivElement>(null)
  const used = useRef(new Set<string>())

  const fallback = [
    { q: 'Why this score?', q_ar: 'لماذا هذه النتيجة؟' }, { q: 'Where is it hosted?', q_ar: 'أين هي الاستضافة؟' }, { q: 'Who is being targeted?', q_ar: 'من المستهدف؟' },
  ]
  const suggestions = (followUps.length ? followUps : fallback).filter((f) => !used.current.has(f.q))

  const scroll = () => window.setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 60)

  const ask = async (label: string, question: string) => {
    if (busy || !question.trim()) return
    used.current.add(question)
    setBusy(true)
    setQ('')
    setMsgs((m) => [...m, { role: 'q', text: label }])
    scroll()
    try {
      const r = await api.ask(runId, question)
      setMsgs((m) => [...m, { role: 'a', text: lang === 'ar' ? r.answer_ar || r.answer : r.answer, blocks: r.blocks, source: r.source, typed: true }])
    } catch (e: any) {
      setMsgs((m) => [...m, { role: 'a', text: e.message }])
    } finally {
      setBusy(false)
      scroll()
    }
  }

  return (
    <div>
      <div className="chat">
        <AnimatePresence initial={false}>
          {msgs.map((m, i) => (
            <motion.div key={i} className={`bubble ${m.role}`} initial={{ opacity: 0, y: 18, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={spring}>
              {m.role === 'a' && <div className="eyebrow row" style={{ marginBottom: 6, color: '#c4b5fd' }}><Sparkles size={12} /> {m.source === 'claude' ? 'Claude' : p('Raqib (offline writer)', 'رقيب (الكاتب غير المتصل)')}</div>}
              <div>{m.typed ? <Typewriter text={m.text} onDone={() => { setShowBlocks((s) => ({ ...s, [i]: true })); scroll() }} /> : m.text}</div>
              {!!m.blocks?.length && showBlocks[i] && <motion.div style={{ marginTop: 12 }} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><BlockRenderer blocks={m.blocks} act={act} /></motion.div>}
            </motion.div>
          ))}
        </AnimatePresence>
        {busy && <div className="bubble a"><span className="typing"><span /><span /><span /></span></div>}
        <div ref={end} />
      </div>
      <div className="card ask">
        <div className="suggest">
          <span className="suggest-label"><Sparkles size={12} /> {p('Suggested', 'مقترح')}</span>
          <AnimatePresence initial={false}>
            {suggestions.map((s) => (
              <motion.button key={s.q} layout initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.8 }} transition={spring} onClick={() => ask(lang === 'ar' ? s.q_ar : s.q, s.q)} disabled={busy}>
                {lang === 'ar' ? s.q_ar : s.q}
              </motion.button>
            ))}
          </AnimatePresence>
        </div>
        <form className="row" onSubmit={(e) => { e.preventDefault(); ask(q, q) }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={p('Ask Raqib about this case…', 'اسأل رقيب عن هذه القضية…')} />
          <button className="btn btn-primary" disabled={busy || !q.trim()}><Send size={15} /> {p('Ask', 'اسأل')}</button>
        </form>
      </div>
    </div>
  )
}
