import { useEffect, useRef, type ReactNode } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, Bot, Check, CheckCircle2, CornerDownRight, Eye, FileCode2, FilePen, Fingerprint, Globe, Keyboard, Link2, MousePointerClick, Network, Play, Radar, ScrollText } from 'lucide-react'
import type { InvState, TL } from '../hooks'
import { useLang } from '../i18n'
import { Num, ease } from './fx'

type AgentState = 'idle' | 'working' | 'done'

interface Agent { key: TL['agent']; name: string; icon: ReactNode; state: AgentState; task: string; metric?: ReactNode }

const I = { size: 16, strokeWidth: 1.5 }

function agentsOf(s: InvState, p: (en: string, ar: string) => string): Agent[] {
  const ph = s.done ? 'done' : s.phase
  const browsing = ph === 'browsing' || ph === 'triage' || ph === 'analyzing'
  const after = (phases: string[]) => s.done || phases.includes(ph)
  const writerName = s.source === 'claude' ? (s.model || 'Claude') : p('Case writer', 'كاتب القضية')
  return [
    {
      key: 'browser', name: p('Browser agent', 'وكيل المتصفح'), icon: <Bot {...I} />,
      state: ph === 'queued' ? 'idle' : browsing ? 'working' : 'done',
      task: browsing ? p('Following the victim’s path', 'يتتبع مسار الضحية') : ph === 'queued' ? p('Waiting', 'بانتظار البدء') : p('Pages captured', 'تم التقاط الصفحات'),
      metric: <><Num value={s.timeline.filter((l) => l.kind === 'page').length} ms={300} /> {p('pages', 'صفحات')}</>,
    },
    {
      key: 'detector', name: p('Detectors', 'أدوات الرصد'), icon: <Radar {...I} />,
      state: !s.frame && !s.signals.length ? (after(['fingerprinting', 'linking', 'reporting']) ? 'done' : 'idle') : browsing ? 'working' : 'done',
      task: browsing ? p('Reading forms, scripts and text', 'يقرأ النماذج والسكربتات والنص') : p('Evidence scored', 'تم تقييم الأدلة'),
      metric: <><Num value={s.signals.length} ms={300} /> {p('signals', 'مؤشرات')}</>,
    },
    {
      key: 'linker', name: p('Campaign linker', 'رابط الحملات'), icon: <Network {...I} />,
      state: ph === 'fingerprinting' || ph === 'linking' ? 'working' : after(['reporting']) ? 'done' : 'idle',
      task: ph === 'fingerprinting' ? p('Building the fingerprint', 'يبني البصمة') : ph === 'linking' ? p('Comparing with known scams', 'يقارن بالاحتيالات المعروفة') : after(['reporting']) ? p('Campaign mapped', 'تم رسم الحملة') : p('Waiting for evidence', 'بانتظار الأدلة'),
      metric: <><Num value={Math.max(0, s.nodes.length - 1)} ms={300} /> {p('linked', 'مرتبط')}</>,
    },
    {
      key: 'writer', name: writerName, icon: <FilePen {...I} />,
      state: ph === 'reporting' ? 'working' : s.blocks ? 'done' : 'idle',
      task: ph === 'reporting' ? p('Composing the case file', 'يركّب ملف القضية') : s.blocks ? p('Case file ready', 'ملف القضية جاهز') : p('Waiting for the campaign', 'بانتظار الحملة'),
      metric: s.blocks ? <><Num value={s.blocks.length} ms={300} /> {p('blocks', 'كتل')}</> : undefined,
    },
  ]
}

export function CrewStrip({ s }: { s: InvState }) {
  const { p } = useLang()
  const agents = agentsOf(s, p)
  return (
    <div className="crew">
      {agents.map((a) => (
        <div key={a.key} className={`agent ${a.state}`}>
          <div className="ag-ico">
            {a.icon}
            {a.state === 'done' && <span className="ag-done"><Check size={10} strokeWidth={3} /></span>}
          </div>
          <div style={{ minWidth: 0 }}>
            <div className="ag-name row" style={{ gap: 8 }}>{a.name}{a.state === 'working' && <span className="dot live" style={{ width: 6, height: 6 }} />}</div>
            <div className="ag-task">
              <AnimatePresence mode="wait" initial={false}>
                <motion.span key={a.task} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.16, ease }}>{a.task}</motion.span>
              </AnimatePresence>
            </div>
          </div>
          {a.metric && <div className="ag-metric">{a.metric}</div>}
        </div>
      ))}
    </div>
  )
}

const J = { size: 14, strokeWidth: 1.5 }
const KIND_ICON: Record<string, ReactNode> = {
  start: <Play {...J} />, think: <Bot {...J} />, page: <Globe {...J} />, click: <MousePointerClick {...J} />, type: <Keyboard {...J} />,
  inspect: <Eye {...J} />, scroll: <ScrollText {...J} />, redirect: <CornerDownRight {...J} />, kit: <FileCode2 {...J} />, signal: <AlertTriangle {...J} />,
  fingerprint: <Fingerprint {...J} />, link: <Link2 {...J} />, compose: <FilePen {...J} />, done: <CheckCircle2 {...J} />, error: <AlertTriangle {...J} />,
}
const AGENT_LABEL: Record<string, [string, string]> = {
  browser: ['Browser', 'المتصفح'], detector: ['Detector', 'الرصد'], linker: ['Linker', 'الربط'], writer: ['Writer', 'الكاتب'], system: ['System', 'النظام'],
}

export function ActivityLog({ s, height = 332 }: { s: InvState; height?: number }) {
  const { p, lang } = useLang()
  const box = useRef<HTMLDivElement>(null)
  const lines = [...s.timeline].reverse()
  useEffect(() => { box.current?.scrollTo({ top: 0, behavior: 'smooth' }) }, [s.timeline.length])
  return (
    <div className="card">
      <div className="card-h">
        <h3>{p('Agent activity', 'نشاط الوكلاء')}</h3>
        <span className="sub">{p('Every action, as it happens', 'كل إجراء لحظة حدوثه')}</span>
        <span className="right mono num" style={{ fontSize: 12 }}>{s.timeline.length}</span>
      </div>
      <div className="activity" ref={box} style={{ maxHeight: height }}>
        <AnimatePresence initial={false}>
          {lines.map((l, i) => (
            <motion.div key={l.id} className={`act-line k-${l.kind} ${l.tone ?? ''} ${i === 0 && !s.done ? 'now' : ''}`}
              initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.2, ease }}>
              <span className="al-t">{l.t.toFixed(1)}s</span>
              <span className="al-ico">{KIND_ICON[l.kind] ?? <Bot {...J} />}</span>
              <div style={{ minWidth: 0 }}>
                <div className="al-text"><span className="al-who">{lang === 'ar' ? AGENT_LABEL[l.agent][1] : AGENT_LABEL[l.agent][0]}</span>{lang === 'ar' && l.text_ar ? l.text_ar : l.text}</div>
                {l.sub && <div className="al-sub">{l.sub}</div>}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>
        {!lines.length && <div className="empty">{p('The agents’ actions appear here as they happen', 'تظهر إجراءات الوكلاء هنا فور حدوثها')}</div>}
      </div>
    </div>
  )
}
