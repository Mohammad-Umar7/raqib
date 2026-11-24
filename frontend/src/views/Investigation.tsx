import type React from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, ArrowRight, CheckCircle2, FileText, LayoutDashboard, Network, Radar, Search, Send, Server, UserRoundX, Wallet } from 'lucide-react'
import { AskPanel } from '../components/AskPanel'
import { ActivityLog, CrewStrip } from '../components/Crew'
import { BlockRenderer, LayoutStrip, type BlockActions } from '../components/Blocks'
import { BrowserPanel } from '../components/BrowserPanel'
import { Num, Rise, ease, soft } from '../components/fx'
import { Gauge } from '../components/Gauge'
import { Graph } from '../components/Graph'
import { ReportPack } from '../components/ReportPack'
import { useInvestigation, type InvState } from '../hooks'
import { useLang } from '../i18n'
import { STRENGTH, cap, scoreColor, verdictOf } from '../meta'
import type { GEdge } from '../types'

export interface Nav { go: (route: string) => void; investigate: (url: string, opts?: { mode?: string; speed?: number }) => void }

const I = { size: 16, strokeWidth: 1.5 }
export const CAT_ICON: Record<string, React.ReactElement> = {
  impersonation: <UserRoundX {...I} />, payment: <Wallet {...I} />, exfiltration: <Send {...I} />, fraud: <AlertTriangle {...I} />, infrastructure: <Server {...I} />,
}

function RiskCard({ s }: { s: InvState }) {
  const { p, lang } = useLang()
  const v = verdictOf(s.verdict)
  const brand = s.indicators?.brand
  return (
    <div className="card">
      <div className="gauge-wrap">
        <Gauge score={s.score} />
        <div className="col" style={{ gap: 8 }}>
          <div className="eyebrow">{p('Explainable risk score', 'درجة الخطورة القابلة للتفسير')}</div>
          <AnimatePresence mode="wait">
            <motion.div key={s.signals.length || s.done ? s.verdict : 'wait'} className="verdict-line" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.16, ease }}>
              {s.signals.length || s.done ? (lang === 'ar' ? v.ar : v.en) : p('Investigating…', 'جارٍ التحقيق…')}
            </motion.div>
          </AnimatePresence>
          <div className="row wrap">
            {brand && <span className={`chip ${s.verdict === 'official' ? 'ok' : 'danger'}`}>{s.verdict === 'official' ? p('Official', 'رسمي') : p('Imitates', 'ينتحل')} {lang === 'ar' ? brand.name_ar : brand.name}</span>}
            {s.indicators?.brand_confidence ? <span className="chip">{p('Confidence', 'الثقة')} <span className="num">{Math.round(s.indicators.brand_confidence * 100)}%</span></span> : null}
            {s.mode && <span className="chip">{s.mode === 'replay' ? p('Replay of recorded evidence', 'إعادة أدلة مسجّلة') : s.mode === 'scan' ? p('Real scan, isolated browser', 'فحص حقيقي في متصفح معزول') : s.mode === 'live' ? p('Claude agent, live browser', 'وكيل Claude في متصفح مباشر') : s.mode === 'listing' ? p('Maps listing', 'موقع خرائط') : p('Triage only', 'فحص النطاق فقط')}</span>}
          </div>
        </div>
      </div>
    </div>
  )
}

function SignalFeed({ s }: { s: InvState }) {
  const { p, f } = useLang()
  return (
    <div className="card">
      <div className="card-h"><h3>{p('Detected signals', 'المؤشرات المكتشفة')}</h3><span className="right mono num" style={{ fontSize: 12 }}>{s.signals.length}</span></div>
      <div className="list" style={{ maxHeight: 432, overflow: 'auto' }}>
        <AnimatePresence initial={false}>
          {[...s.signals].reverse().map((g) => (
            <motion.div key={g.id} className={`sig ${g.severity}`} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={soft}>
              <div className="si">{CAT_ICON[g.category] ?? <Search {...I} />}</div>
              <div>
                <p>{f(g, 'label')}</p>
                <small>{cap(g.category)}</small>
              </div>
              <span className="w">+{Math.round(g.weight * 100)}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {!s.signals.length && <div className="empty">{s.done ? p('No scam signals found', 'لم يتم العثور على مؤشرات احتيال') : p('Signals appear here as the browser finds them', 'تظهر المؤشرات هنا فور اكتشافها')}</div>}
      </div>
    </div>
  )
}

function CampaignPanel({ s, big, onEdge, sel }: { s: InvState; big?: boolean; onEdge?: (e: GEdge) => void; sel?: string | null }) {
  const { p } = useLang()
  const strongN = s.edges.filter((e) => e.strength === 'strong' && s.nodes.some((n) => n.center && (n.case_id === e.source || n.case_id === e.target))).length
  return (
    <div className="card">
      <div className="card-h">
        <h3>{p('Campaign graph', 'رسم الحملة')}</h3>
        <span className="sub">{s.nodes.length > 1 ? <><Num value={s.nodes.length - 1} ms={400} /> {p('connected', 'مرتبط')} · <Num value={strongN} ms={400} /> {p('strong', 'قوي')}</> : p('Searching for related sites…', 'جارٍ البحث عن مواقع مرتبطة…')}</span>
      </div>
      {s.nodes.length ? <Graph nodes={s.nodes} edges={s.edges} width={big ? 1000 : 760} height={big ? 620 : 470} onEdge={onEdge} selectedEdge={sel} /> : <div className="graph-box scanning" style={{ height: 300 }}>{p('Comparing the fingerprint with known scams…', 'جارٍ مقارنة البصمة بالاحتيالات المعروفة…')}</div>}
    </div>
  )
}

function RelatedFeed({ s, act }: { s: InvState; act: BlockActions }) {
  const { p, lang } = useLang()
  return (
    <div className="card">
      <div className="card-h"><h3>{p('Related sites, investigated automatically', 'مواقع مرتبطة جرى التحقيق فيها تلقائياً')}</h3></div>
      <div className="list" style={{ maxHeight: 440, overflow: 'auto' }}>
        <AnimatePresence initial={false}>
          {s.related.map((r) => (
            <motion.div key={r.case_id} className="related-row list-row" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={soft}>
              <div style={{ minWidth: 0 }}>
                <div className="mono ellipsis" style={{ fontSize: 13 }}>{r.host}</div>
                <div className="faint" style={{ fontSize: 12 }}>{r.reason}</div>
                <div className="row" style={{ marginTop: 4, fontSize: 12, color: 'var(--text-2)', gap: 12 }}>
                  <span>{lang === 'ar' ? STRENGTH[r.strength as 'strong'].ar : STRENGTH[r.strength as 'strong'].en}</span>
                  {!r.on_blocklist && r.score >= 60 && <span className="row" style={{ gap: 6 }}><span className="dot warn" style={{ width: 6, height: 6 }} />{p('Not on a blocklist', 'غير محجوب')}</span>}
                </div>
              </div>
              <span className="score-n" style={{ color: scoreColor(r.score) }}><Num value={r.score} ms={700} /></span>
              <button className="btn btn-sm btn-ghost" onClick={() => act.investigate(r.case_id)} aria-label={p('Open', 'فتح')}><ArrowRight size={14} className="flip-rtl" /></button>
            </motion.div>
          ))}
        </AnimatePresence>
        {!s.related.length && <div className="empty">{s.nodes.length > 1 ? p('Only weak links, so nothing is investigated automatically', 'روابط ضعيفة فقط، لا تحقيق تلقائي') : p('Strongly linked sites are investigated here as they are found', 'تظهر هنا المواقع المرتبطة بقوة فور اكتشافها والتحقيق فيها')}</div>}
      </div>
    </div>
  )
}

export function Investigation({ runId, nav, initialTab }: { runId: string; nav: Nav; initialTab?: string }) {
  const { p, lang } = useLang()
  const s = useInvestigation(runId)
  const [tab, setTab] = useState<'live' | 'case' | 'campaign' | 'report'>((initialTab as any) || 'live')
  const [topic, setTopic] = useState<string | undefined>()
  const [edge, setEdge] = useState<GEdge | null>(null)
  const graphRef = useRef<HTMLDivElement>(null)
  const scrolled = useRef(false)

  useEffect(() => { setTab((initialTab as any) || 'live'); scrolled.current = false }, [runId])
  useEffect(() => {
    if (tab === 'live' && s.nodes.length > 0 && !scrolled.current && !s.done) {
      scrolled.current = true
      setTimeout(() => graphRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 300)
    }
  }, [s.nodes.length, tab, s.done])

  const act: BlockActions = useMemo(() => ({
    openReport: (t) => { setTopic(t); setTab('report') },
    openCampaign: () => setTab('campaign'),
    investigate: (id) => nav.investigate('case:' + id),
  }), [nav])

  const title = s.meta?.input_url ?? '…'
  const tabs = [
    ['live', p('Live investigation', 'التحقيق المباشر'), <Radar {...I} key="a" />],
    ['case', p('Case file', 'ملف القضية'), <LayoutDashboard {...I} key="b" />],
    ['campaign', p('Campaign', 'الحملة'), <Network {...I} key="c" />],
    ['report', p('Report pack', 'حزمة التقرير'), <FileText {...I} key="d" />],
  ] as const

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <div className="row eyebrow"><span className="tag-id">{runId.toUpperCase()}</span>{p('Investigation', 'تحقيق')}</div>
          <h1 className="mono" style={{ fontSize: 20, wordBreak: 'break-all' }}>{title}</h1>
        </div>
        <div className="tabs" role="tablist">
          {tabs.map(([k, label, icon]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)} disabled={k !== 'live' && !s.done && k !== 'campaign'}>
              {tab === k && <motion.span layoutId="tab-ind" className="tab-ind" transition={{ duration: 0.2, ease }} />}
              <span className="row" style={{ gap: 8, position: 'relative' }}>{icon}{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="card"><CrewStrip s={s} /></div>
      {s.error && <div className="card callout danger"><AlertTriangle size={16} strokeWidth={1.5} className="ci" /><div><h4>{p('The investigation failed', 'فشل التحقيق')}</h4><p>{s.error}</p></div></div>}

      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={tab} className="col" style={{ gap: 16 }} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={soft}>
          {tab === 'live' && (
            <>
              <div className="live-grid">
                <BrowserPanel s={s} />
                <div className="col" style={{ gap: 16 }}>
                  <Rise i={0}><RiskCard s={s} /></Rise>
                  <Rise i={1}><ActivityLog s={s} /></Rise>
                  <Rise i={2}><SignalFeed s={s} /></Rise>
                </div>
              </div>
              {(s.nodes.length > 0 || s.phase === 'linking') && (
                <motion.div ref={graphRef} style={{ scrollMarginTop: 80 }} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={soft}>
                  <CampaignPanel s={s} big />
                </motion.div>
              )}
              <AnimatePresence>
                {s.done && !s.error && (
                  <motion.div className="card banner-done" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={soft}>
                    <CheckCircle2 size={20} strokeWidth={1.5} color="var(--green)" />
                    <div className="grow"><b>{p('Case file ready', 'ملف القضية جاهز')}</b><div className="muted" style={{ fontSize: 13 }}>{s.headline ? (lang === 'ar' ? s.headline.ar : s.headline.en) : ''}</div></div>
                    <button className="btn" onClick={() => setTab('report')}>{p('Report pack', 'حزمة التقرير')}</button>
                    <button className="btn btn-primary" onClick={() => setTab('case')}>{p('Open case file', 'فتح ملف القضية')} <ArrowRight size={14} className="flip-rtl" /></button>
                  </motion.div>
                )}
              </AnimatePresence>
            </>
          )}

          {tab === 'case' && (s.blocks ? (
            <>
              <LayoutStrip blocks={s.blocks} source={s.source} />
              <BlockRenderer blocks={s.blocks} act={act} />
              <AskPanel runId={runId} act={act} followUps={s.followUps} />
            </>
          ) : <div className="card card-p"><div className="skeleton" style={{ height: 180 }} /></div>)}

          {tab === 'campaign' && (
            <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.7fr) minmax(0,1fr)' }}>
              <CampaignPanel s={s} big onEdge={setEdge} sel={edge ? `${edge.source}|${edge.target}` : null} />
              <div className="col" style={{ gap: 16 }}>
                <div className="card">
                  <div className="card-h"><h3>{edge ? p('Why these two are linked', 'سبب الربط بين الموقعين') : p('Select a link', 'اختر رابطاً')}</h3></div>
                  <AnimatePresence mode="wait">
                    {edge ? (
                      <motion.div key={`${edge.source}|${edge.target}`} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.16, ease }}>
                        <div className="card-b col" style={{ gap: 8, paddingBottom: 12 }}>
                          <div className="mono" style={{ fontSize: 12 }}>{s.nodes.find((n) => n.case_id === edge.source)?.host} <span className="faint">↔</span> {s.nodes.find((n) => n.case_id === edge.target)?.host}</div>
                          <div className="faint" style={{ fontSize: 13 }}>{lang === 'ar' ? STRENGTH[edge.strength].ar : STRENGTH[edge.strength].en}</div>
                        </div>
                        <div className="list" style={{ borderTop: '1px solid var(--line)' }}>
                          {edge.reasons.map((r, i) => (
                            <div key={i} className="sig" style={{ gridTemplateColumns: '8px minmax(0,1fr)' }}>
                              <span className="dot" style={{ background: STRENGTH[r.strength].color, marginTop: 6 }} />
                              <div><p>{lang === 'ar' ? r.text_ar : r.text}</p><small>{cap(r.kind)}</small></div>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    ) : <motion.div key="none" className="card-b muted" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{p('Click any line in the graph to see the evidence behind the connection', 'اضغط على أي خط في الرسم لرؤية الدليل وراء الارتباط')}</motion.div>}
                  </AnimatePresence>
                </div>
                <RelatedFeed s={s} act={act} />
              </div>
            </div>
          )}

          {tab === 'report' && <ReportPack runId={runId} focus={topic} />}
        </motion.div>
      </AnimatePresence>
    </div>
  )
}
