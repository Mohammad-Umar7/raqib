import type React from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AlertTriangle, ArrowRight, Check, FileText, Fingerprint, LayoutDashboard, Network, Radar, Search, Server, Sparkles, Send, UserRoundX, Wallet, Loader2 } from 'lucide-react'
import { AskPanel } from '../components/AskPanel'
import { BlockRenderer, type BlockActions } from '../components/Blocks'
import { BrowserPanel } from '../components/BrowserPanel'
import { Gauge } from '../components/Gauge'
import { Graph } from '../components/Graph'
import { ReportPack } from '../components/ReportPack'
import { useInvestigation, type InvState } from '../hooks'
import { useLang } from '../i18n'
import { PHASE_LABEL, PHASES, STRENGTH, scoreColor, verdictOf } from '../meta'
import type { GEdge } from '../types'

export interface Nav { go: (route: string) => void; investigate: (url: string, opts?: { mode?: string; speed?: number }) => void }

const CAT_ICON: Record<string, React.ReactElement> = {
  impersonation: <UserRoundX size={17} />, payment: <Wallet size={17} />, exfiltration: <Send size={17} />, fraud: <AlertTriangle size={17} />, infrastructure: <Server size={17} />,
}

function phaseIndex(s: InvState): number {
  if (s.done) return 5
  switch (s.phase) {
    case 'queued': return -1
    case 'browsing': case 'triage': return s.signals.length ? 1 : 0
    case 'fingerprinting': return 2
    case 'linking': return 3
    case 'reporting': return 4
    default: return 0
  }
}

function Stepper({ s }: { s: InvState }) {
  const { lang, p } = useLang()
  const idx = phaseIndex(s)
  return (
    <div className="stepper">
      {PHASES.map((ph, i) => (
        <div key={ph} className="row" style={{ gap: 8 }}>
          {i > 0 && <span className="step-sep" />}
          <span className={`step ${i < idx ? 'done' : i === idx ? 'on' : ''}`}>
            {i < idx ? <Check size={14} /> : i === idx ? <Loader2 size={14} className="spin" /> : <span className="dot" />}
            {lang === 'ar' ? PHASE_LABEL[ph].ar : PHASE_LABEL[ph].en}
          </span>
        </div>
      ))}
      {s.phaseLabel && !s.done && <span className="muted" style={{ marginInlineStart: 8, fontSize: 12.5 }}>{s.phaseLabel}</span>}
      {s.done && !s.error && <span className="chip ok"><Check size={13} /> {p('Investigation complete', 'اكتمل التحقيق')}</span>}
    </div>
  )
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
          <div className="verdict-line" style={{ color: scoreColor(s.score) }}>{s.signals.length || s.done ? (lang === 'ar' ? v.ar : v.en) : p('Investigating…', 'جارٍ التحقيق…')}</div>
          <div className="row wrap">
            {brand && <span className="chip danger">{p('Imitates', 'ينتحل')} {lang === 'ar' ? brand.name_ar : brand.name}</span>}
            {s.indicators?.brand_confidence ? <span className="chip">{p('confidence', 'الثقة')} {Math.round(s.indicators.brand_confidence * 100)}%</span> : null}
            {s.mode && <span className="chip info">{s.mode === 'replay' ? p('Replay · recorded evidence', 'إعادة · أدلة مسجّلة') : s.mode === 'live' ? p('Live browser', 'متصفح مباشر') : s.mode === 'listing' ? p('Maps listing', 'موقع خرائط') : p('Triage only', 'فحص النطاق فقط')}</span>}
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
      <div className="card-h"><Radar size={16} color="#38bdf8" /><h3>{p('Detected signals', 'المؤشرات المكتشفة')}</h3><span className="sub right">{s.signals.length}</span></div>
      <div className="card-b col" style={{ gap: 8, maxHeight: 420, overflow: 'auto' }}>
        {[...s.signals].reverse().map((g) => (
          <div key={g.id} className={`sig ${g.severity} wf-enter`}>
            <div className="si">{CAT_ICON[g.category] ?? <Search size={17} />}</div>
            <div><p>{f(g, 'label')}</p><small>{g.category}</small></div>
            <span className="w">+{Math.round(g.weight * 100)}</span>
          </div>
        ))}
        {!s.signals.length && <div className="muted" style={{ padding: '10px 2px' }}>{s.done ? p('No scam signals found.', 'لم يتم العثور على مؤشرات احتيال.') : p('Signals appear here as the browser finds them.', 'تظهر المؤشرات هنا فور اكتشافها.')}</div>}
      </div>
    </div>
  )
}

function IndicatorsCard({ s }: { s: InvState }) {
  const { p } = useLang()
  const i = s.indicators
  const rows: [string, string, string?][] = []
  if (i) {
    i.iocs.telegram_bot_ids.forEach((v) => rows.push([p('Telegram bot ID', 'معرّف بوت تيليجرام'), v, 'danger']))
    i.iocs.discord_webhook_ids.forEach((v) => rows.push([p('Discord webhook ID', 'معرّف ويب هوك ديسكورد'), v, 'danger']))
    i.iocs.wallets.forEach((v) => rows.push([p('Crypto wallet', 'محفظة رقمية'), v, 'danger']))
    i.contacts.whatsapp.forEach((v) => rows.push(['WhatsApp', v, 'warn']))
    i.contacts.phones.forEach((v) => rows.push([p('Phone', 'هاتف'), v]))
    i.contacts.emails.forEach((v) => rows.push([p('E-mail', 'بريد'), v]))
  }
  const fp = s.fingerprint
  return (
    <div className="card">
      <div className="card-h"><Fingerprint size={16} color="#a78bfa" /><h3>{p('Scam fingerprint', 'بصمة الاحتيال')}</h3></div>
      <div className="card-b">
        {rows.length ? (
          <dl className="kv" style={{ margin: 0 }}>
            {rows.map(([k, v, tone], n) => <div key={n} style={{ display: 'contents' }}><dt>{k}</dt><dd className={`mono ${tone ?? ''}`} style={{ fontSize: 12 }}>{v}</dd></div>)}
            {fp && <><dt>{p('Kit files', 'ملفات الأدوات')}</dt><dd className="mono" style={{ fontSize: 12 }}>{fp.kit_files}</dd><dt>{p('Layout shingles', 'عناصر التخطيط')}</dt><dd className="mono" style={{ fontSize: 12 }}>{fp.layout_shingles}</dd></>}
          </dl>
        ) : <div className="muted">{s.done ? p('No shareable indicators found.', 'لا مؤشرات يمكن مشاركتها.') : p('Phones, bot IDs, wallets and kit files are collected here.', 'تُجمع هنا أرقام الهواتف ومعرّفات البوتات والمحافظ وملفات الأدوات.')}</div>}
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
        <Network size={16} color="#6366f1" />
        <h3>{p('Campaign graph', 'رسم الحملة')}</h3>
        <span className="sub">{s.nodes.length > 1 ? `${s.nodes.length - 1} ${p('connected', 'مرتبط')} · ${strongN} ${p('strong', 'قوي')}` : p('searching for related sites…', 'جارٍ البحث عن مواقع مرتبطة…')}</span>
      </div>
      {s.nodes.length ? <Graph nodes={s.nodes} edges={s.edges} width={big ? 1000 : 760} height={big ? 620 : 470} onEdge={onEdge} selectedEdge={sel} /> : <div className="graph-box" style={{ height: 300 }} />}
    </div>
  )
}

function RelatedFeed({ s, act }: { s: InvState; act: BlockActions }) {
  const { p, lang } = useLang()
  return (
    <div className="card">
      <div className="card-h"><Search size={16} color="#38bdf8" /><h3>{p('Related sites, investigated automatically', 'مواقع مرتبطة جرى التحقيق فيها تلقائياً')}</h3></div>
      <div className="card-b col" style={{ gap: 8, maxHeight: 440, overflow: 'auto' }}>
        {s.related.map((r) => (
          <div key={r.case_id} className="related-row wf-enter">
            <div style={{ minWidth: 0 }}>
              <div className="mono ellipsis" style={{ fontSize: 12.5, fontWeight: 600 }}>{r.host}</div>
              <div className="faint" style={{ fontSize: 11.5 }}>{r.reason}</div>
              <div className="row" style={{ marginTop: 4 }}>
                <span className="chip" style={{ color: STRENGTH[r.strength as 'strong'].color, borderColor: STRENGTH[r.strength as 'strong'].color + '66' }}>{lang === 'ar' ? STRENGTH[r.strength as 'strong'].ar : STRENGTH[r.strength as 'strong'].en}</span>
                {!r.on_blocklist && r.score >= 60 && <span className="chip warn">{p('not on a blocklist', 'غير محجوب')}</span>}
              </div>
            </div>
            <b style={{ fontSize: 20, color: scoreColor(r.score) }}>{r.score}</b>
            <button className="btn btn-sm" onClick={() => act.investigate(r.case_id)}><ArrowRight size={14} /></button>
          </div>
        ))}
        {!s.related.length && <div className="muted">{s.nodes.length > 1 ? p('Only weak links: nothing is investigated automatically.', 'روابط ضعيفة فقط: لا تحقيق تلقائي.') : p('Strongly linked sites are investigated here as they are found.', 'تظهر هنا المواقع المرتبطة بقوة فور اكتشافها والتحقيق فيها.')}</div>}
      </div>
    </div>
  )
}

function EvidenceCard({ s }: { s: InvState }) {
  const { p } = useLang()
  return (
    <div className="card">
      <div className="card-h"><FileText size={16} color="#34d399" /><h3>{p('Evidence log', 'سجل الأدلة')}</h3><span className="sub">{p('every item is SHA-256 hashed when recorded', 'كل عنصر يُحسب له SHA-256 عند تسجيله')}</span><span className="sub right">{s.evidence.length}</span></div>
      <div className="card-b" style={{ maxHeight: 300, overflow: 'auto' }}>
        {[...s.evidence].reverse().map((e) => (
          <div className="ev wf-enter" key={e.id}><span className="id">{e.id}</span><div><div>{e.label}</div><div className="hash">{e.sha256}</div></div></div>
        ))}
        {!s.evidence.length && <div className="muted">{p('Screenshots, DOM, network logs and scripts are stored here.', 'تُحفظ هنا لقطات الشاشة وبنية الصفحة وسجلات الشبكة والسكربتات.')}</div>}
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
  // bring the graph into view the moment campaign linking starts
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

  const title = s.meta?.input_url ?? s.blocks?.[0]?.headline ?? '…'
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
          {tabs.map(([k, label, icon]) => <button key={k} className={`tab ${tab === k ? 'active' : ''}`} onClick={() => setTab(k)} disabled={k !== 'live' && !s.done && k !== 'campaign'}><span className="row" style={{ gap: 6 }}>{icon}{label}</span></button>)}
        </div>
      </div>

      <Stepper s={s} />
      {s.error && <div className="callout danger" style={{ marginBottom: 16 }}><AlertTriangle /> <div><h4>{p('The investigation failed', 'فشل التحقيق')}</h4><p>{s.error}</p></div></div>}

      {tab === 'live' && (
        <>
          <div className="live-grid">
            <BrowserPanel s={s} />
            <div className="col" style={{ gap: 18 }}>
              <RiskCard s={s} />
              <SignalFeed s={s} />
              <IndicatorsCard s={s} />
            </div>
          </div>
          {(s.nodes.length > 0 || s.phase === 'linking') && (
            <div ref={graphRef} className="grid-2" style={{ marginTop: 18, gridTemplateColumns: 'minmax(0,1.5fr) minmax(0,1fr)', scrollMarginTop: 90 }}>
              <CampaignPanel s={s} />
              <RelatedFeed s={s} act={act} />
            </div>
          )}
          <div style={{ marginTop: 18 }}><EvidenceCard s={s} /></div>
          {s.done && !s.error && (
            <div className="banner-done" style={{ marginTop: 18 }}>
              <Sparkles size={22} color="#6ee7b7" />
              <div className="grow"><b>{p('Case file is ready.', 'ملف القضية جاهز.')}</b><div className="muted" style={{ fontSize: 12.5 }}>{s.headline ? (lang === 'ar' ? s.headline.ar : s.headline.en) : ''} · {s.source === 'claude' ? p('written by Claude', 'كتبه Claude') : p('written by the offline writer', 'كتبه الكاتب غير المتصل')}</div></div>
              <button className="btn" onClick={() => setTab('report')}>{p('Report pack', 'حزمة التقرير')}</button>
              <button className="btn btn-primary" onClick={() => setTab('case')}>{p('Open case file', 'فتح ملف القضية')} <ArrowRight size={15} /></button>
            </div>
          )}
        </>
      )}

      {tab === 'case' && (s.blocks ? (
        <>
          <BlockRenderer blocks={s.blocks} act={act} />
          <AskPanel runId={runId} act={act} />
        </>
      ) : <div className="card card-p"><div className="skeleton" style={{ height: 180 }} /></div>)}

      {tab === 'campaign' && (
        <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.7fr) minmax(0,1fr)' }}>
          <CampaignPanel s={s} big onEdge={setEdge} sel={edge ? `${edge.source}|${edge.target}` : null} />
          <div className="col" style={{ gap: 18 }}>
            <div className="card">
              <div className="card-h"><h3>{edge ? p('Why these two are linked', 'سبب الربط بين الموقعين') : p('Select a link', 'اختر رابطاً')}</h3></div>
              <div className="card-b col" style={{ gap: 10 }}>
                {edge ? (
                  <>
                    <div className="mono" style={{ fontSize: 12 }}>{s.nodes.find((n) => n.case_id === edge.source)?.host} <span className="faint">↔</span> {s.nodes.find((n) => n.case_id === edge.target)?.host}</div>
                    <span className="chip" style={{ width: 'fit-content', color: STRENGTH[edge.strength].color, borderColor: STRENGTH[edge.strength].color + '77' }}>{lang === 'ar' ? STRENGTH[edge.strength].ar : STRENGTH[edge.strength].en}</span>
                    {edge.reasons.map((r, i) => (
                      <div key={i} className="sig" style={{ gridTemplateColumns: '10px 1fr' }}>
                        <span className="dot" style={{ background: STRENGTH[r.strength].color, marginTop: 6 }} />
                        <div><p>{lang === 'ar' ? r.text_ar : r.text}</p><small>{r.kind}</small></div>
                      </div>
                    ))}
                  </>
                ) : <div className="muted">{p('Click any line in the graph to see the evidence behind the connection.', 'اضغط على أي خط في الرسم لرؤية الدليل وراء الارتباط.')}</div>}
              </div>
            </div>
            <RelatedFeed s={s} act={act} />
          </div>
        </div>
      )}

      {tab === 'report' && <ReportPack runId={runId} focus={topic} />}
    </div>
  )
}
