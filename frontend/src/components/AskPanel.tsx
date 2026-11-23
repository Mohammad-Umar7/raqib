import { useRef, useState } from 'react'
import { Send, Sparkles } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import type { Block } from '../types'
import { BlockRenderer, type BlockActions } from './Blocks'

interface Msg { role: 'q' | 'a'; text: string; blocks?: Block[]; source?: string }

export function AskPanel({ runId, act }: { runId: string; act: BlockActions }) {
  const { p, lang } = useLang()
  const [msgs, setMsgs] = useState<Msg[]>([])
  const [q, setQ] = useState('')
  const [busy, setBusy] = useState(false)
  const end = useRef<HTMLDivElement>(null)

  const suggestions = [
    [p('Why this score?', 'لماذا هذه النتيجة؟'), 'Why this score?'],
    [p('What else is linked?', 'ما المرتبط بها أيضاً؟'), 'What else is linked to this campaign?'],
    [p('Who is being targeted?', 'من المستهدف؟'), 'Who is being targeted?'],
    [p('What should we do next?', 'ماذا نفعل الآن؟'), 'What actions should we take next?'],
    [p('Where is it hosted?', 'أين هي الاستضافة؟'), 'Where is it hosted?'],
  ]

  const ask = async (label: string, question: string) => {
    if (busy || !question.trim()) return
    setBusy(true)
    setQ('')
    setMsgs((m) => [...m, { role: 'q', text: label }])
    setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 50)
    try {
      const r = await api.ask(runId, question)
      setMsgs((m) => [...m, { role: 'a', text: lang === 'ar' ? r.answer_ar || r.answer : r.answer, blocks: r.blocks, source: r.source }])
    } catch (e: any) {
      setMsgs((m) => [...m, { role: 'a', text: e.message }])
    } finally {
      setBusy(false)
      setTimeout(() => end.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }), 80)
    }
  }

  return (
    <div>
      <div className="chat">
        {msgs.map((m, i) => (
          <div key={i} className={`bubble ${m.role} wf-enter`}>
            {m.role === 'a' && <div className="eyebrow row" style={{ marginBottom: 6, color: '#c4b5fd' }}><Sparkles size={12} /> {m.source === 'claude' ? p('Claude', 'Claude') : p('Raqib (offline writer)', 'رقيب (الكاتب غير المتصل)')}</div>}
            <div>{m.text}</div>
            {!!m.blocks?.length && <div style={{ marginTop: 12 }}><BlockRenderer blocks={m.blocks} act={act} /></div>}
          </div>
        ))}
        {busy && <div className="bubble a"><span className="typing"><span /><span /><span /></span></div>}
        <div ref={end} />
      </div>
      <div className="card ask">
        <div className="suggest">{suggestions.map(([l, qq]) => <button key={l} onClick={() => ask(l, qq)} disabled={busy}>{l}</button>)}</div>
        <form className="row" onSubmit={(e) => { e.preventDefault(); ask(q, q) }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={p('Ask Raqib about this case…', 'اسأل رقيب عن هذه القضية…')} />
          <button className="btn btn-primary" disabled={busy || !q.trim()}><Send size={15} /> {p('Ask', 'اسأل')}</button>
        </form>
      </div>
    </div>
  )
}
