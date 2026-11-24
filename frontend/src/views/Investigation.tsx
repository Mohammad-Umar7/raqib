import type React from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, ArrowRight, FileText, LayoutDashboard, Network, Radar, Search, Send, Server, Sparkles, UserRoundX, Wallet } from 'lucide-react'
import { AskPanel } from '../components/AskPanel'
import { ActivityLog, CrewStrip } from '../components/Crew'
import { BlockRenderer, LayoutStrip, type BlockActions } from '../components/Blocks'
import { BrowserPanel } from '../components/BrowserPanel'
import { Num, Rise, Typewriter, soft, spring } from '../components/fx'
import { Gauge } from '../components/Gauge'
import { Graph } from '../components/Graph'
import { ReportPack } from '../components/ReportPack'
import { useInvestigation, type InvState } from '../hooks'
import { useLang } from '../i18n'
import { STRENGTH, scoreColor, verdictOf } from '../meta'
import type { GEdge } from '../types'

export interface Nav { go: (route: string) => void; investigate: (url: string, opts?: { mode?: string; speed?: number }) => void }

const CAT_ICON: Record<string, React.ReactElement> = {
  impersonation: <UserRoundX size={17} />, payment: <Wallet size={17} />, exfiltration: <Send size={17} />, fraud: <AlertTriangle size={17} />, infrastructure: <Server size={17} />,
}

function RiskCard({ s }: { s: InvState }) {
  const { p, lang } = useLang()
  const v = verdictOf(s.verdict)
  const brand = s.indicators?.brand
  return (
    <div className="card risk-card" style={{ ['--rc' as any]: scoreColor(s.score) }}>
      <div className="gauge-wrap">
        <Gauge score={s.score} final={s.done} />
        <div className="col" style={{ gap: 8 }}>
          <div className="eyebrow">{p('Explainable risk score', 'درجة الخطورة القابلة للتفسير')}</div>
          <AnimatePresence mode="wait">
            <motion.div key={s.signals.length || s.done ? s.verdict : 'wait'} className="verdict-line" style={{ color: scoreColor(s.score) }} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.2 }}>
              {s.signals.length || s.done ? (lang === 'ar' ? v.ar : v.en) : p('Investigating…', 'جارٍ التحقيق…')}
            </motion.div>
          </AnimatePresence>
          <div className="row wrap">
            <AnimatePresence>
              {brand && <motion.span key="b" className={`chip ${s.verdict === 'official' ? 'ok' : 'danger'}`} initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} transition={spring}>{s.verdict === 'official' ? p('Official', 'رسمي') : p('Imitates', 'ينتحل')} {lang === 'ar' ? brand.name_ar : brand.name}</motion.span>}
            </AnimatePresence>
            {s.indicators?.brand_confidence ? <span className="chip">{p('confidence', 'الثقة')} {Math.round(s.indicators.brand_confidence * 100)}%</span> : null}
            {s.mode && <span className="chip info">{s.mode === 'replay' ? p('Replay · recorded evidence', 'إعادة · أدلة مسجّلة') : s.mode === 'scan' ? p('Real scan · isolated browser', 'فحص حقيقي · متصفح معزول') : s.mode === 'live' ? p('Claude agent · live browser', 'وكيل Claude · متصفح مباشر') : s.mode === 'listing' ? p('Maps listing', 'موقع خرائط') : p('Triage only', 'فحص النطاق فقط')}</span>}
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
      <div className="card-h"><Radar size={16} color="#e5b85c" /><h3>{p('Detected signals', 'المؤشرات المكتشفة')}</h3><motion.span key={s.signals.length} className="chip info right" initial={{ scale: 1.4 }} animate={{ scale: 1 }} transition={spring}>{s.signals.length}</motion.span></div>
      <div className="card-b col" style={{ gap: 8, maxHeight: 430, overflow: 'auto' }}>
        <AnimatePresence initial={false}>
          {[...s.signals].reverse().map((g, i) => (
            <motion.div key={g.id} layout className={`sig ${g.severity} ${i === 0 && !s.done ? 'fresh' : ''}`} initial={{ opacity: 0, x: -40, scale: 0.92 }} animate={{ opacity: 1, x: 0, scale: 1 }} transition={spring}>
              <div className="si">{CAT_ICON[g.category] ?? <Search size={17} />}</div>
              <div>
                <p>{f(g, 'label')}</p>
                <small>{g.category}</small>
                <div className="meter"><motion.i initial={{ width: 0 }} animate={{ width: `${Math.round(g.weight * 100)}%` }} transition={{ duration: 0.7, delay: 0.15 }} /></div>
              </div>
              <span className="w">+{Math.round(g.weight * 100)}</span>
            </motion.div>
          ))}
        </AnimatePresence>
        {!s.signals.length && <div className="muted" style={{ padding: '10px 2px' }}>{s.done ? p('No scam signals found.', 'لم يتم العثور على مؤشرات احتيال.') : p('Signals appear here as the browser finds them.', 'تظهر المؤشرات هنا فور اكتشافها.')}</div>}
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
        <Network size={16} color="#9a8cff" />
        <h3>{p('Campaign graph', 'رسم الحملة')}</h3>
        <span className="sub">{s.nodes.length > 1 ? <><Num value={s.nodes.length - 1} ms={400} /> {p('connected', 'مرتبط')} · <Num value={strongN} ms={400} /> {p('strong', 'قوي')}</> : p('searching for related sites…', 'جارٍ البحث عن مواقع مرتبطة…')}</span>
      </div>
      {s.nodes.length ? <Graph nodes={s.nodes} edges={s.edges} width={big ? 1000 : 760} height={big ? 620 : 470} onEdge={onEdge} selectedEdge={sel} /> : <div className="graph-box scanning" style={{ height: 300 }}><div className="radar-ping" /></div>}
    </div>
  )
}

function RelatedFeed({ s, act }: { s: InvState; act: BlockActions }) {
  const { p, lang } = useLang()
  return (
    <div className="card">
      <div className="card-h"><Search size={16} color="#e5b85c" /><h3>{p('Related sites, investigated automatically', 'مواقع مرتبطة جرى التحقيق فيها تلقائياً')}</h3></div>
      <div className="card-b col" style={{ gap: 8, maxHeight: 440, overflow: 'auto' }}>
        <AnimatePresence initial={false}>
          {s.related.map((r) => (
            <motion.div key={r.case_id} layout className="related-row" initial={{ opacity: 0, x: 40 }} animate={{ opacity: 1, x: 0 }} transition={spring} whileHover={{ x: -3 }}>
              <div style={{ minWidth: 0 }}>
                <div className="mono ellipsis" style={{ fontSize: 12.5, fontWeight: 600 }}>{r.host}</div>
                <div className="faint" style={{ fontSize: 11.5 }}>{r.reason}</div>
                <div className="row" style={{ marginTop: 4 }}>
                  <span className="chip" style={{ color: STRENGTH[r.strength as 'strong'].color, borderColor: STRENGTH[r.strength as 'strong'].color + '66' }}>{lang === 'ar' ? STRENGTH[r.strength as 'strong'].ar : STRENGTH[r.strength as 'strong'].en}</span>
                  {!r.on_blocklist && r.score >= 60 && <span className="chip warn">{p('not on a blocklist', 'غير محجوب')}</span>}
                </div>
              </div>
              <b style={{ fontSize: 20, color: scoreColor(r.score) }}><Num value={r.score} ms={700} /></b>
              <button className="btn btn-sm" onClick={() => act.investigate(r.case_id)}><ArrowRight size={14} /></button>
            </motion.div>
          ))}
        </AnimatePresence>
        {!s.related.length && <div className="muted">{s.nodes.length > 1 ? p('Only weak links: nothing is investigated automatically.', 'روابط ضعيفة فقط: لا تحقيق تلقائي.') : p('Strongly linked sites are investigated here as they are found.', 'تظهر هنا المواقع المرتبطة بقوة فور اكتشافها والتحقيق فيها.')}</div>}
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
    ['live', p('Live investigation', 'التحقيق المباشر'), <Radar size={14} key="a" />],
    ['case', p('Case file', 'ملف القضية'), <LayoutDashboard size={14} key="b" />],
    ['campaign', p('Campaign', 'الحملة'), <Network size={14} key="c" />],
    ['report', p('Report pack', 'حزمة التقرير'), <FileText size={14} key="d" />],
  ] as const

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <div className="eyebrow">{p('Investigation', 'تحقيق')} · {runId.toUpperCase()}</div>
          <h1 className="mono" style={{ fontSize: 20, wordBreak: 'break-all' }}>{title}</h1>
        </div>
        <div className="tabs">
          {tabs.map(([k, label, icon]) => (
            <button key={k} className={`tab ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)} disabled={k !== 'live' && !s.done && k !== 'campaign'}>
              {tab === k && <motion.span layoutId="tab-ind" className="tab-ind" transition={spring} />}
              <span className="row" style={{ gap: 6, position: 'relative' }}>{icon}{label}</span>
            </button>
          ))}
        </div>
      </div>

      <div className="crew-wrap"><CrewStrip s={s} /></div>
      {s.error && <div className="callout danger" style={{ marginBottom: 16 }}><AlertTriangle /> <div><h4>{p('The investigation failed', 'فشل التحقيق')}</h4><p>{s.error}</p></div></div>}

      <AnimatePresence mode="wait" initial={false}>
        <motion.div key={tab} initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -10 }} transition={{ duration: 0.22 }}>
          {tab === 'live' && (
            <>
              <div className="live-grid">
                <BrowserPanel s={s} />
                <div className="col" style={{ gap: 18 }}>
                  <Rise i={0}><RiskCard s={s} /></Rise>
                  <Rise i={1}><ActivityLog s={s} /></Rise>
                  <Rise i={2}><SignalFeed s={s} /></Rise>
                </div>
              </div>
              {(s.nodes.length > 0 || s.phase === 'linking') && (
                <motion.div ref={graphRef} style={{ marginTop: 18, scrollMarginTop: 90 }} initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={soft}>
                  <CampaignPanel s={s} big />
                </motion.div>
              )}
              <AnimatePresence>
                {s.done && !s.error && (
                  <motion.div className="banner-done" style={{ marginTop: 18 }} initial={{ opacity: 0, y: 26, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} transition={spring}>
                    <Sparkles size={22} color="#6ee7b7" />
                    <div className="grow"><b>{p('Case file is ready.', 'ملف القضية جاهز.')}</b><div className="muted" style={{ fontSize: 12.5 }}>{s.headline ? <Typewriter text={lang === 'ar' ? s.headline.ar : s.headline.en} caret={false} /> : ''}</div></div>
                    <button className="btn" onClick={() => setTab('report')}>{p('Report pack', 'حزمة التقرير')}</button>
                    <button className="btn btn-primary" onClick={() => setTab('case')}>{p('Open case file', 'فتح ملف القضية')} <ArrowRight size={15} /></button>
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
              <div className="col" style={{ gap: 18 }}>
                <div className="card">
                  <div className="card-h"><h3>{edge ? p('Why these two are linked', 'سبب الربط بين الموقعين') : p('Select a link', 'اختر رابطاً')}</h3></div>
                  <div className="card-b col" style={{ gap: 10 }}>
                    <AnimatePresence mode="wait">
                      {edge ? (
                        <motion.div key={`${edge.source}|${edge.target}`} className="col" style={{ gap: 10 }} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                          <div className="mono" style={{ fontSize: 12 }}>{s.nodes.find((n) => n.case_id === edge.source)?.host} <span className="faint">↔</span> {s.nodes.find((n) => n.case_id === edge.target)?.host}</div>
                          <span className="chip" style={{ width: 'fit-content', color: STRENGTH[edge.strength].color, borderColor: STRENGTH[edge.strength].color + '77' }}>{lang === 'ar' ? STRENGTH[edge.strength].ar : STRENGTH[edge.strength].en}</span>
                          {edge.reasons.map((r, i) => (
                            <motion.div key={i} className="sig" style={{ gridTemplateColumns: '10px 1fr' }} initial={{ opacity: 0, x: 14 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: i * 0.06 }}>
                              <span className="dot" style={{ background: STRENGTH[r.strength].color, marginTop: 6 }} />
                              <div><p>{lang === 'ar' ? r.text_ar : r.text}</p><small>{r.kind}</small></div>
                            </motion.div>
                          ))}
                        </motion.div>
                      ) : <motion.div key="none" className="muted" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>{p('Click any line in the graph to see the evidence behind the connection.', 'اضغط على أي خط في الرسم لرؤية الدليل وراء الارتباط.')}</motion.div>}
                    </AnimatePresence>
                  </div>
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
