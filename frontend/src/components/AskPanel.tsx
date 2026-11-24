import { useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Send } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import type { Block } from '../types'
import { BlockRenderer, type BlockActions } from './Blocks'
import { Typewriter, soft } from './fx'

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
    <div className="col" style={{ gap: 16 }}>
      {(msgs.length > 0 || busy) && (
        <div className="chat">
          <AnimatePresence initial={false}>
            {msgs.map((m, i) => (
              <motion.div key={i} className={`bubble ${m.role}`} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={soft}>
                {m.role === 'a' && <div className="who">{m.source === 'claude' ? 'Claude' : p('Raqib, offline writer', 'رقيب، الكاتب غير المتصل')}</div>}
                <div>{m.typed ? <Typewriter text={m.text} onDone={() => { setShowBlocks((s) => ({ ...s, [i]: true })); scroll() }} /> : m.text}</div>
                {!!m.blocks?.length && showBlocks[i] && <motion.div style={{ marginTop: 12 }} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={soft}><BlockRenderer blocks={m.blocks} act={act} /></motion.div>}
              </motion.div>
            ))}
          </AnimatePresence>
          {busy && <div className="bubble a"><span className="typing" aria-label={p('Writing', 'يكتب')}><span /><span /><span /></span></div>}
          <div ref={end} />
        </div>
      )}
      <div className="card ask">
        {suggestions.length > 0 && (
          <div className="suggest">
            <span className="suggest-label">{p('Suggested questions', 'أسئلة مقترحة')}</span>
            {suggestions.map((s) => (
              <button key={s.q} className="btn btn-sm btn-ghost" onClick={() => ask(lang === 'ar' ? s.q_ar : s.q, s.q)} disabled={busy}>{lang === 'ar' ? s.q_ar : s.q}</button>
            ))}
          </div>
        )}
        <form className="row" onSubmit={(e) => { e.preventDefault(); ask(q, q) }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={p('Ask about this case', 'اسأل عن هذه القضية')} aria-label={p('Question about this case', 'سؤال عن هذه القضية')} />
          <button className="btn btn-primary" style={{ height: 36 }} disabled={busy || !q.trim()}><Send size={14} strokeWidth={1.5} className="flip-rtl" /> {p('Ask', 'اسأل')}</button>
        </form>
      </div>
    </div>
  )
}
