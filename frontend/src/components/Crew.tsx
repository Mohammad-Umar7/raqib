import { useEffect, useRef, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Bot, Check, CheckCircle2, CornerDownRight, Eye, FileCode2, Fingerprint, Globe, Keyboard, Link2, MousePointerClick, Network, Play, Radar, ScrollText, Sparkles } from 'lucide-react'
import type { InvState, TL } from '../hooks'
import { useLang } from '../i18n'
import { Num, spring } from './fx'

type AgentState = 'idle' | 'working' | 'done'

interface Agent { key: TL['agent']; name: string; name_ar: string; icon: ReactNode; state: AgentState; task: string; metric?: ReactNode }

function agentsOf(s: InvState, p: (en: string, ar: string) => string): Agent[] {
  const ph = s.done ? 'done' : s.phase
  const browsing = ph === 'browsing' || ph === 'triage' || ph === 'analyzing'
  const after = (phases: string[]) => s.done || phases.includes(ph)
  const writerName = s.source === 'claude' ? (s.model || 'Claude') : p('Case writer', 'كاتب القضية')
  return [
    {
      key: 'browser', name: p('Browser agent', 'وكيل المتصفح'), name_ar: '', icon: <Bot size={18} />,
      state: ph === 'queued' ? 'idle' : browsing ? 'working' : 'done',
      task: browsing ? p('following the victim’s path', 'يتتبع مسار الضحية') : ph === 'queued' ? p('waiting', 'بانتظار البدء') : p('pages captured', 'تم التقاط الصفحات'),
      metric: <><Num value={s.timeline.filter((l) => l.kind === 'page').length} ms={300} /> {p('pages', 'صفحات')}</>,
    },
    {
      key: 'detector', name: p('Detectors', 'أدوات الرصد'), name_ar: '', icon: <Radar size={18} />,
      state: !s.frame && !s.signals.length ? (after(['fingerprinting', 'linking', 'reporting']) ? 'done' : 'idle') : browsing ? 'working' : 'done',
      task: browsing ? p('reading forms, scripts and text', 'يقرأ النماذج والسكربتات والنص') : p('evidence scored', 'تم تقييم الأدلة'),
      metric: <><Num value={s.signals.length} ms={300} /> {p('signals', 'مؤشرات')}</>,
    },
    {
      key: 'linker', name: p('Campaign linker', 'رابط الحملات'), name_ar: '', icon: <Network size={18} />,
      state: ph === 'fingerprinting' || ph === 'linking' ? 'working' : after(['reporting']) ? 'done' : 'idle',
      task: ph === 'fingerprinting' ? p('building the fingerprint', 'يبني البصمة') : ph === 'linking' ? p('comparing with known scams', 'يقارن بالاحتيالات المعروفة') : after(['reporting']) ? p('campaign mapped', 'تم رسم الحملة') : p('waiting for evidence', 'بانتظار الأدلة'),
      metric: <><Num value={Math.max(0, s.nodes.length - 1)} ms={300} /> {p('linked', 'مرتبط')}</>,
    },
    {
      key: 'writer', name: writerName, name_ar: '', icon: <Sparkles size={18} />,
      state: ph === 'reporting' ? 'working' : s.blocks ? 'done' : 'idle',
      task: ph === 'reporting' ? p('composing the case file', 'يركّب ملف القضية') : s.blocks ? p('case file ready', 'ملف القضية جاهز') : p('waiting for the campaign', 'بانتظار الحملة'),
      metric: s.blocks ? <><Num value={s.blocks.length} ms={300} /> {p('blocks', 'كتل')}</> : undefined,
    },
  ]
}

export function CrewStrip({ s }: { s: InvState }) {
  const { p } = useLang()
  const agents = agentsOf(s, p)
  return (
    <div className="crew">
      {agents.map((a, i) => (
        <div key={a.key} className="row" style={{ gap: 0, minWidth: 0 }}>
          <motion.div className={`agent ${a.state} ag-${a.key}`} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ ...spring, delay: i * 0.06 }}>
            <div className="ag-ico">
              {a.icon}
              {a.state === 'working' && <span className="ag-ring" />}
              <AnimatePresence>{a.state === 'done' && <motion.span className="ag-done" initial={{ scale: 0 }} animate={{ scale: 1 }} transition={spring}><Check size={10} strokeWidth={3.5} /></motion.span>}</AnimatePresence>
            </div>
            <div style={{ minWidth: 0 }}>
              <div className="ag-name">{a.name}</div>
              <div className="ag-task">
                <AnimatePresence mode="wait" initial={false}>
                  <motion.span key={a.task} initial={{ opacity: 0, y: 5 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -5 }} transition={{ duration: 0.18 }}>{a.task}</motion.span>
                </AnimatePresence>
              </div>
            </div>
            {a.metric && <div className="ag-metric">{a.metric}</div>}
            {a.state === 'working' && <span className="ag-bar" />}
          </motion.div>
          {i < agents.length - 1 && <div className={`ag-link ${agents[i + 1].state !== 'idle' ? 'on' : ''}`}><i /></div>}
        </div>
      ))}
    </div>
  )
}

const KIND_ICON: Record<string, ReactNode> = {
  start: <Play size={13} />, think: <Bot size={13} />, page: <Globe size={13} />, click: <MousePointerClick size={13} />, type: <Keyboard size={13} />,
  inspect: <Eye size={13} />, scroll: <ScrollText size={13} />, redirect: <CornerDownRight size={13} />, kit: <FileCode2 size={13} />, signal: <AlertTriangle size={13} />,
  fingerprint: <Fingerprint size={13} />, link: <Link2 size={13} />, compose: <Sparkles size={13} />, done: <CheckCircle2 size={13} />, error: <AlertTriangle size={13} />,
}
const AGENT_LABEL: Record<string, [string, string]> = {
  browser: ['Browser', 'المتصفح'], detector: ['Detector', 'الرصد'], linker: ['Linker', 'الربط'], writer: ['Writer', 'الكاتب'], system: ['System', 'النظام'],
}

export function ActivityLog({ s, height = 330 }: { s: InvState; height?: number }) {
  const { p, lang } = useLang()
  const box = useRef<HTMLDivElement>(null)
  const lines = [...s.timeline].reverse()
  useEffect(() => { box.current?.scrollTo({ top: 0, behavior: 'smooth' }) }, [s.timeline.length])
  return (
    <div className="card">
      <div className="card-h">
        <Bot size={16} color="#a78bfa" />
        <h3>{p('Agent activity', 'نشاط الوكلاء')}</h3>
        <span className="sub">{p('every action the agents take, live', 'كل إجراء يتخذه الوكلاء مباشرةً')}</span>
        <span className="chip right"><Num value={s.timeline.length} ms={250} /></span>
      </div>
      <div className="activity" ref={box} style={{ maxHeight: height }}>
        <AnimatePresence initial={false}>
          {lines.map((l, i) => (
            <motion.div key={l.id} className={`act-line k-${l.kind} ${l.tone ?? ''} ${i === 0 && !s.done ? 'now' : ''}`}
              initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.25 }}>
              <span className="al-t mono">{l.t.toFixed(1)}s</span>
              <span className={`al-ico ag-${l.agent}`}>{KIND_ICON[l.kind] ?? <Bot size={13} />}</span>
              <div className="al-body">
                <div className="al-text"><span className={`al-who ag-${l.agent}`}>{lang === 'ar' ? AGENT_LABEL[l.agent][1] : AGENT_LABEL[l.agent][0]}</span>{lang === 'ar' && l.text_ar ? l.text_ar : l.text}</div>
                {l.sub && <div className="al-sub mono">{l.sub}</div>}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {!lines.length && <div className="muted" style={{ padding: 14 }}>{p('The agents’ actions appear here as they happen.', 'تظهر إجراءات الوكلاء هنا فور حدوثها.')}</div>}
      </div>
    </div>
  )
}
