import { Fragment, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle, ArrowUpRight, Bot, Calendar, Check, CheckCircle2, CreditCard, Download, FileCheck2, FileText, Flame, Gauge as GaugeIcon, Globe2, IdCard, Info, KeyRound, Landmark,
  LayoutGrid, Link2, LogIn, MapPin, Megaphone, MessageSquare, MessageSquareText, Network, Phone, Radar, Copy, Search, Send, Server, ShieldAlert, ShieldCheck, Sparkles, TextCursorInput, UserRoundX, Wallet,
} from 'lucide-react'
import { useLang } from '../i18n'
import { STRENGTH, scoreColor, verdictOf } from '../meta'
import type { Block } from '../types'
import { Gauge } from './Gauge'
import { Num, Reveal, Scramble, Typewriter, spring } from './fx'
import { UaeMap } from './Maps'
import { WorldMap } from './WorldMap'

export interface BlockActions {
  openReport: (topic?: string) => void
  openCampaign: () => void
  investigate: (caseId: string) => void
}

const CAT_ICON: Record<string, ReactNode> = {
  impersonation: <UserRoundX size={17} />, payment: <Wallet size={17} />, exfiltration: <Send size={17} />, fraud: <AlertTriangle size={17} />, infrastructure: <Server size={17} />,
}
const TONE_ICON: Record<string, ReactNode> = { danger: <ShieldAlert size={20} />, warn: <AlertTriangle size={20} />, info: <Info size={20} />, ok: <CheckCircle2 size={20} /> }
const STEP_ICON: Record<string, ReactNode> = {
  sms: <MessageSquareText size={20} />, search: <Search size={20} />, map: <MapPin size={20} />, globe: <Globe2 size={20} />, message: <MessageSquare size={20} />, link: <Link2 size={20} />,
  page: <FileText size={20} />, form: <TextCursorInput size={20} />, card: <CreditCard size={20} />, otp: <KeyRound size={20} />, id: <IdCard size={20} />, login: <LogIn size={20} />,
  bot: <Bot size={20} />, wallet: <Wallet size={20} />, phone: <Phone size={20} />,
}
const STAT_ICON: Record<string, ReactNode> = {
  gauge: <GaugeIcon size={17} />, radar: <Radar size={17} />, network: <Network size={17} />, shield: <ShieldCheck size={17} />, calendar: <Calendar size={17} />, file: <FileCheck2 size={17} />,
}

/** What each block type is called and drawn as, shown in the layout strip. */
export const BLOCK_META: Record<string, { en: string; ar: string; icon: ReactNode }> = {
  verdict_hero: { en: 'Verdict', ar: 'الحكم', icon: <Sparkles size={13} /> },
  screenshot: { en: 'Screenshot', ar: 'لقطة الشاشة', icon: <Globe2 size={13} /> },
  stat_row: { en: 'Key figures', ar: 'أرقام رئيسية', icon: <GaugeIcon size={13} /> },
  callout: { en: 'Alert', ar: 'تنبيه', icon: <ShieldAlert size={13} /> },
  markdown: { en: 'Narrative', ar: 'سرد', icon: <FileText size={13} /> },
  journey: { en: 'Victim journey', ar: 'رحلة الضحية', icon: <Link2 size={13} /> },
  signal_list: { en: 'Signals', ar: 'المؤشرات', icon: <Radar size={13} /> },
  score_breakdown: { en: 'Score maths', ar: 'حساب الدرجة', icon: <LayoutGrid size={13} /> },
  campaign_card: { en: 'Campaign', ar: 'الحملة', icon: <Network size={13} /> },
  indicators: { en: 'Indicators', ar: 'المؤشرات التقنية', icon: <Bot size={13} /> },
  kv_table: { en: 'Infrastructure', ar: 'البنية التحتية', icon: <Server size={13} /> },
  emirate_map: { en: 'Targets', ar: 'المستهدفون', icon: <MapPin size={13} /> },
  evidence_list: { en: 'Evidence', ar: 'الأدلة', icon: <Landmark size={13} /> },
  action_list: { en: 'Actions', ar: 'الإجراءات', icon: <Flame size={13} /> },
}

const typedOnce = new Set<string>()

function Title({ b, icon }: { b: Block; icon?: ReactNode }) {
  const { f } = useLang()
  return b.title ? <div className="card-h">{icon}<h3>{f(b, 'title')}</h3></div> : null
}

// ------------------------------------------------------------------ blocks

function Verdict({ b }: { b: Block }) {
  const { p, f, lang } = useLang()
  const v = verdictOf(b.verdict)
  const headline = f(b, 'headline')
  const key = `${b.headline}|${lang}`
  const first = !typedOnce.has(key)
  const [done, setDone] = useState(!first)
  return (
    <div className={`card hero-verdict ${b.tone}`}>
      <div className="col" style={{ alignItems: 'center', gap: 4 }}>
        <Gauge score={b.score} size={170} final />
        <motion.span className={`chip ${v.tone}`} initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} transition={{ ...spring, delay: 0.9 }}>{lang === 'ar' ? v.ar : v.en}</motion.span>
      </div>
      <div>
        <div className="eyebrow row"><Sparkles size={13} /> {p('Case summary', 'ملخص القضية')}</div>
        <h2>{first ? <Typewriter text={headline} caret onDone={() => { typedOnce.add(key); setDone(true) }} /> : headline}</h2>
        <motion.p initial={{ opacity: 0, y: 8 }} animate={done ? { opacity: 1, y: 0 } : {}} transition={{ duration: 0.45 }}>{f(b, 'summary')}</motion.p>
        <div className="row wrap">
          {(b.chips ?? []).map((c: any, i: number) => (
            <motion.span key={i} className={`chip ${c.tone}`} initial={{ opacity: 0, y: 8 }} animate={done ? { opacity: 1, y: 0 } : {}} transition={{ delay: 0.12 * i, ...spring }}>{f(c, 'label')}</motion.span>
          ))}
        </div>
      </div>
    </div>
  )
}

function Screenshot({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<Globe2 size={16} color="#e5b85c" />} />
      <div className="card-b shot-block">
        <a className="shot-frame" href={b.src} target="_blank" rel="noreferrer"><img src={b.src} alt="" /></a>
        <div className="col" style={{ gap: 10, minWidth: 0 }}>
          <div><div className="eyebrow">{p('Landing page', 'صفحة الهبوط')}</div><div className="mono" style={{ fontSize: 12, wordBreak: 'break-all' }}>{b.final_url}</div></div>
          {b.chain?.length > 1 && (
            <div><div className="eyebrow">{p('Redirect chain', 'سلسلة التحويل')}</div>
              {b.chain.map((h: any, i: number) => <div key={i} className="mono chain-hop"><span className={`st s${String(h.status)[0]}`}>{h.status}</span>{h.url}</div>)}
            </div>
          )}
          <div className="row wrap" style={{ gap: 6 }}>
            {b.engine && <span className="chip">{b.engine === 'browser' ? p('Rendered in isolated Chrome', 'عُرض في Chrome معزول') : p('HTTP fetch', 'جلب HTTP')}</span>}
            {b.cloaking && <span className="chip danger">{p('Cloaking', 'إخفاء')}: {b.cloaking}</span>}
            {b.trusted && <span className="chip ok">{b.trusted}</span>}
            {b.ai && b.ai.impersonates && b.ai.impersonates !== 'none' && <span className="chip violet"><Sparkles size={11} /> Claude: {b.ai.impersonates} ({Math.round((b.ai.confidence ?? 0) * 100)}%)</span>}
          </div>
          {b.ai?.reason && <div className="faint" style={{ fontSize: 12 }}>{b.ai.reason}</div>}
          <div className="faint" style={{ fontSize: 11.5 }}>{p('Captured', 'التُقطت')} {b.captured} · {p('mobile profile, UAE locale · SHA-256 in the evidence list', 'ملف جوال بإعدادات الإمارات · بصمة SHA-256 في قائمة الأدلة')}</div>
          {f(b, 'note')}
        </div>
      </div>
    </div>
  )
}

function Stats({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className="stat-tiles" style={{ gridTemplateColumns: `repeat(${b.items.length}, minmax(0, 1fr))` }}>
      {b.items.map((it: any, i: number) => (
        <motion.div key={i} className={`tile-stat ${it.tone}`} initial={{ opacity: 0, y: 22, scale: 0.94 }} whileInView={{ opacity: 1, y: 0, scale: 1 }} viewport={{ once: true }} transition={{ ...spring, delay: i * 0.07 }} whileHover={{ y: -4 }}>
          <div className="ts-ico">{STAT_ICON[it.icon] ?? <Info size={17} />}</div>
          <div className="ts-num"><Num value={Number(it.value)} suffix="" ms={1100} /><small>{it.suffix}</small></div>
          <div className="ts-label">{f(it, 'label')}</div>
          {(it.hint || it.hint_ar) && <div className="ts-hint">{f(it, 'hint')}</div>}
        </motion.div>
      ))}
    </div>
  )
}

function Callout({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className={`callout ${b.tone}`}>
      <div style={{ color: b.tone === 'danger' ? '#ff8da4' : b.tone === 'warn' ? '#ffb37d' : b.tone === 'ok' ? '#6ee7b7' : '#f2d39a' }}>{TONE_ICON[b.tone] ?? TONE_ICON.info}</div>
      <div>
        {b.title && <h4>{f(b, 'title')}</h4>}
        <p>{f(b, 'text')}</p>
      </div>
    </div>
  )
}

function Markdown({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className="card card-p">
      {b.title && <h4 style={{ margin: '0 0 6px' }}>{f(b, 'title')}</h4>}
      {f(b, 'text').split(/\n\n+/).map((t: string, i: number) => <p key={i} style={{ margin: '0 0 8px', color: '#cfcbd6' }}>{t}</p>)}
    </div>
  )
}

function Journey({ b }: { b: Block }) {
  const { f, lang } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<Link2 size={16} color="#fb4a6c" />} />
      <div className="card-b">
        <div className="journey">
          {b.steps.map((st: any, i: number) => (
            <Fragment key={i}>
              <motion.div className={`j-step ${st.tone}`} initial={{ opacity: 0, y: 22, scale: 0.9 }} whileInView={{ opacity: 1, y: 0, scale: 1 }} viewport={{ once: true }} transition={{ ...spring, delay: i * 0.2 }}>
                <div className="j-ico">{STEP_ICON[st.icon] ?? <FileText size={20} />}<span className="j-n">{i + 1}</span></div>
                <b>{f(st, 'title')}</b>
                {(st.detail || st.detail_ar) && <small>{f(st, 'detail')}</small>}
              </motion.div>
              {i < b.steps.length - 1 && (
                <motion.div className="j-link" style={{ transformOrigin: lang === 'ar' ? 'right' : 'left' }} initial={{ scaleX: 0, opacity: 0 }} whileInView={{ scaleX: 1, opacity: 1 }} viewport={{ once: true }} transition={{ duration: 0.4, delay: i * 0.2 + 0.18 }}>
                  <i />
                </motion.div>
              )}
            </Fragment>
          ))}
        </div>
        <p className="muted" style={{ margin: '14px 2px 0', fontSize: 13 }}>{f(b, 'summary')}</p>
      </div>
    </div>
  )
}

function Signals({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<Radar size={16} color="#e5b85c" />} />
      <div className="card-b col" style={{ gap: 8 }}>
        {b.items.map((s: any, i: number) => (
          <motion.div key={s.id} className={`sig ${s.severity}`} initial={{ opacity: 0, x: -18 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ ...spring, delay: Math.min(i, 8) * 0.05 }}>
            <div className="si">{CAT_ICON[s.category] ?? <Info size={17} />}</div>
            <div>
              <p>{f(s, 'label')}</p>
              <small>{s.category}</small>
              <div className="meter"><motion.i initial={{ width: 0 }} whileInView={{ width: `${Math.round(s.weight * 100)}%` }} viewport={{ once: true }} transition={{ duration: 0.8, delay: 0.2 + i * 0.05 }} /></div>
            </div>
            <span className="w">+{Math.round(s.weight * 100)}</span>
          </motion.div>
        ))}
        {!b.items.length && <div className="muted">{p('No scam signals were found.', 'لم يتم العثور على أي مؤشرات احتيال.')}</div>}
      </div>
    </div>
  )
}

function Breakdown({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<LayoutGrid size={16} color="#a78bfa" />} />
      <div className="card-b col" style={{ gap: 7 }}>
        {b.items.map((r: any, i: number) => (
          <div key={r.id} className="wf-row">
            <span className="wf-label" title={f(r, 'label')}>{f(r, 'label')}</span>
            <div className="wf-track">
              <motion.i className={r.severity} style={{ insetInlineStart: `${r.start}%`, transformOrigin: 'left' }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }}
                transition={{ duration: 0.5, delay: 0.1 + i * 0.09, ease: 'easeOut' }} animate={{ width: `${Math.max(1.5, r.end - r.start)}%` }} />
            </div>
            <span className="wf-val">+{r.weight}<small>→{r.end}</small></span>
          </div>
        ))}
        <div className="wf-row total">
          <span className="wf-label"><b>{p('Total risk score', 'درجة الخطورة الإجمالية')}</b></span>
          <div className="wf-track">
            <motion.i className="total" style={{ insetInlineStart: 0, transformOrigin: 'left', background: `linear-gradient(90deg, #34d399, #ff8a3d, ${scoreColor(b.score)})` }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }}
              transition={{ duration: 0.8, delay: 0.3 + b.items.length * 0.09 }} animate={{ width: `${b.score}%` }} />
          </div>
          <span className="wf-val" style={{ color: scoreColor(b.score) }}><b>{b.score}</b></span>
        </div>
        <div className="faint" style={{ fontSize: 11.5 }}>{f(b, 'note')}</div>
      </div>
    </div>
  )
}

function Campaign({ b, act }: { b: Block; act: BlockActions }) {
  const { f, p, lang } = useLang()
  return (
    <div className="card">
      <div className="card-h">
        <Network size={16} color="#9a8cff" />
        <h3>{f(b, 'title')}</h3>
        {b.cluster_id && <span className="chip violet">{b.cluster_id} · {b.cluster_size} {p('sites', 'موقعاً')}</span>}
        <button className="btn btn-sm right" onClick={act.openCampaign}>{p('Open graph', 'فتح الرسم')} <ArrowUpRight size={14} /></button>
      </div>
      <div className="card-b col" style={{ gap: 8 }}>
        {b.unblocked > 0 && (
          <div className="callout warn" style={{ padding: '10px 12px' }}>
            <Megaphone size={18} color="#ffb37d" />
            <p><b>{b.unblocked}</b> {p('linked scam site(s) are not on any public blocklist yet.', 'من المواقع الاحتيالية المرتبطة غير مدرجة بعد في أي قائمة حجب عامة.')}</p>
          </div>
        )}
        {b.items.map((r: any, i: number) => (
          <motion.div key={r.case_id} className="camp-item" initial={{ opacity: 0, x: 18 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ ...spring, delay: Math.min(i, 8) * 0.05 }} whileHover={{ x: 3 }}>
            <div className="row" style={{ minWidth: 0 }}>
              <span className="dot" style={{ background: scoreColor(r.score), width: 10, height: 10 }} />
              <b className="mono ellipsis" style={{ fontSize: 12.5 }}>{r.kind === 'maps_listing' ? r.label : r.host}</b>
              {r.kind === 'maps_listing' && <span className="chip violet">{p('Maps', 'خرائط')}</span>}
            </div>
            <div className="row">
              <span className="chip" style={{ color: STRENGTH[r.strength as 'strong'].color, borderColor: STRENGTH[r.strength as 'strong'].color + '66' }}>{lang === 'ar' ? STRENGTH[r.strength as 'strong'].ar : STRENGTH[r.strength as 'strong'].en}</span>
              <b style={{ color: scoreColor(r.score), minWidth: 26, textAlign: 'end' }}>{r.score}</b>
              {r.kind === 'site' && <button className="btn btn-sm btn-ghost" title={p('Investigate', 'تحقيق')} onClick={() => act.investigate(r.case_id)}><Search size={13} /></button>}
            </div>
            <div className="why">{f(r, 'reason')}{r.on_blocklist ? '' : r.kind === 'site' && r.score >= 60 ? ' · ' + p('not blocklisted', 'غير محجوب') : ''}</div>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function Indicators({ b }: { b: Block }) {
  const { f, p } = useLang()
  const [copied, setCopied] = useState<string | null>(null)
  const copy = (v: string) => { navigator.clipboard?.writeText(v); setCopied(v); window.setTimeout(() => setCopied(null), 1200) }
  return (
    <div className="card">
      <Title b={b} icon={<Bot size={16} color="#fb4a6c" />} />
      <div className="card-b col" style={{ gap: 14 }}>
        {b.groups.map((g: any, gi: number) => (
          <div key={gi}>
            <div className="eyebrow" style={{ marginBottom: 7 }}>{f(g, 'title')}</div>
            <div className="row wrap" style={{ gap: 7 }}>
              {g.items.map((it: any, i: number) => {
                const val = it.copy ?? it.value
                return (
                  <motion.button key={i} className={`ioc ${it.tone}`} onClick={() => copy(val)} initial={{ opacity: 0, scale: 0.85 }} whileInView={{ opacity: 1, scale: 1 }} viewport={{ once: true }}
                    transition={{ ...spring, delay: (gi * 3 + i) * 0.04 }} whileHover={{ y: -2 }} whileTap={{ scale: 0.96 }}>
                    <span className="mono">{it.value}</span>
                    {copied === val ? <Check size={12} /> : <Copy size={12} />}
                  </motion.button>
                )
              })}
            </div>
          </div>
        ))}
        <div className="faint" style={{ fontSize: 11.5 }}>{p('Click an indicator to copy it. These can be shared with banks, platforms and other agencies.', 'اضغط على أي مؤشر لنسخه. يمكن مشاركتها مع البنوك والمنصات والجهات الأخرى.')}</div>
      </div>
    </div>
  )
}

function KV({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<Server size={16} color="#e5b85c" />} />
      <div className="card-b">
        <dl className="kv" style={{ margin: 0 }}>
          {b.rows.map((r: any, i: number) => (
            <div key={i} style={{ display: 'contents' }}>
              <dt>{f(r, 'k')}</dt>
              <dd className={`${r.mono ? 'mono' : ''} ${r.tone ?? ''}`} style={{ fontSize: r.mono ? 12 : 12.5 }}>{r.v}</dd>
            </div>
          ))}
          {!b.rows.length && <dd className="muted" style={{ gridColumn: '1/-1' }}>{p('Not browsed, so no infrastructure data was captured.', 'لم يتم التصفح، لذا لم تُجمع بيانات البنية التحتية.')}</dd>}
        </dl>
        {b.country && <div style={{ marginTop: 12 }}><WorldMap data={{ [b.country]: 1 }} compact /></div>}
        {b.note && !b.country && <div className="faint" style={{ fontSize: 11.5, marginTop: 10 }}>{f(b, 'note')}</div>}
      </div>
    </div>
  )
}

function Evidence({ b }: { b: Block }) {
  const { p, f } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<Landmark size={16} color="#34d399" />} />
      <div className="card-b">
        <div className="callout info" style={{ padding: '10px 12px', marginBottom: 8 }}>
          <Landmark size={18} color="#f2d39a" />
          <div>
            <p style={{ fontSize: 12.5 }}>{p('Manifest SHA-256 (covers every item below). Changing any artefact changes this value.', 'بصمة SHA-256 للبيان (تغطي كل العناصر أدناه). أي تعديل على أي دليل يغيّر هذه القيمة.')}</p>
            <div className="mono" style={{ fontSize: 11, wordBreak: 'break-all', marginTop: 4, color: '#f2d39a' }}><Scramble text={b.manifest} ms={1100} /></div>
          </div>
        </div>
        <div style={{ maxHeight: 340, overflow: 'auto' }}>
          {b.items.map((e: any) => (
            <div className="ev" key={e.id}>
              <span className="id">{e.id}</span>
              <div><div>{f(e, 'label')}</div><div className="hash">{e.sha256}</div><div className="faint" style={{ fontSize: 10.5 }}>{e.kind} · {e.ts}</div></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function Actions({ b, act }: { b: Block; act: BlockActions }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<Flame size={16} color="#fb4a6c" />} />
      <div className="card-b col" style={{ gap: 8 }}>
        {b.items.map((a: any, i: number) => (
          <motion.div key={a.id} className={`act ${a.priority}`} initial={{ opacity: 0, y: 14 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ ...spring, delay: Math.min(i, 8) * 0.06 }} whileHover={{ x: 3 }}>
            <div className="n">{a.priority === 'now' ? <Flame size={16} /> : i + 1}</div>
            <div><b>{f(a, 'label')}</b>{a.detail && <small>{a.detail}</small>}</div>
            <button className="btn btn-sm" onClick={() => act.openReport(a.target ?? a.kind)}>
              {a.kind === 'blocklist' ? <><Download size={13} /> CSV</> : a.kind === 'warning' ? <><Megaphone size={13} /> {p('Draft', 'مسودة')}</> : a.kind === 'takedown' ? <><FileText size={13} /> {p('Draft', 'مسودة')}</> : <><Radar size={13} /> {p('Open', 'فتح')}</>}
            </button>
          </motion.div>
        ))}
      </div>
    </div>
  )
}

function MapBlock({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className="card">
      <Title b={b} icon={<MapPin size={16} color="#fb4a6c" />} />
      <div className="card-b">
        <UaeMap counts={b.counts} />
        <div className="faint" style={{ fontSize: 11.5 }}>{f(b, 'note')}</div>
      </div>
    </div>
  )
}

function Fallback({ b }: { b: Block }) {
  return <div className="card card-p"><div className="eyebrow">{b.type}</div><pre className="mono" style={{ fontSize: 11, whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify(b, null, 1)}</pre></div>
}

// ------------------------------------------------------------------ layout strip + renderer

/** Shows which blocks were chosen, in order: the visible trace of the generative layout. */
export function LayoutStrip({ blocks, source }: { blocks: Block[]; source: string }) {
  const { p, lang } = useLang()
  return (
    <div className="layout-strip">
      <span className={`chip ${source === 'claude' ? 'violet' : ''}`}><Sparkles size={12} /> {source === 'claude' ? p('Layout composed by Claude', 'التخطيط من تصميم Claude') : p('Layout composed by the offline writer', 'التخطيط من الكاتب غير المتصل')}</span>
      {blocks.map((b, i) => {
        const m = BLOCK_META[b.type]
        if (!m) return null
        return (
          <motion.span key={i} className="ls-chip" initial={{ opacity: 0, scale: 0.6, y: 8 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ ...spring, delay: 0.12 + i * 0.07 }}>
            {m.icon}{lang === 'ar' ? m.ar : m.en}
          </motion.span>
        )
      })}
    </div>
  )
}

const SPAN = new Set(['verdict_hero', 'stat_row', 'journey', 'callout', 'markdown', 'screenshot'])

export function BlockRenderer({ blocks, act }: { blocks: Block[]; act: BlockActions }) {
  return (
    <div className="blocks">
      {blocks.map((b, i) => {
        let node: ReactNode
        switch (b.type) {
          case 'verdict_hero': node = <Verdict b={b} />; break
          case 'screenshot': node = <Screenshot b={b} />; break
          case 'stat_row': node = <Stats b={b} />; break
          case 'callout': node = <Callout b={b} />; break
          case 'markdown': node = <Markdown b={b} />; break
          case 'journey': node = <Journey b={b} />; break
          case 'signal_list': node = <Signals b={b} />; break
          case 'score_breakdown': node = <Breakdown b={b} />; break
          case 'campaign_card': node = <Campaign b={b} act={act} />; break
          case 'indicators': node = <Indicators b={b} />; break
          case 'kv_table': node = <KV b={b} />; break
          case 'evidence_list': node = <Evidence b={b} />; break
          case 'action_list': node = <Actions b={b} act={act} />; break
          case 'emirate_map': node = <MapBlock b={b} />; break
          default: node = <Fallback b={b} />
        }
        return <Reveal key={i} i={i} className={SPAN.has(b.type) ? 'span' : ''}>{node}</Reveal>
      })}
    </div>
  )
}

