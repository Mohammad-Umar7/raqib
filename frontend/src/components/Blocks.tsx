import { Fragment, useState, type ReactNode } from 'react'
import { motion } from 'framer-motion'
import {
  AlertTriangle, ArrowUpRight, Bot, Check, CheckCircle2, ChevronRight, Copy, CreditCard, Download, FileText, Globe2, IdCard, Info, KeyRound, Link2, LogIn, MapPin, Megaphone,
  MessageSquare, MessageSquareText, Phone, Radar, Search, Send, Server, ShieldAlert, TextCursorInput, UserRoundX, Wallet,
} from 'lucide-react'
import { useLang } from '../i18n'
import { STRENGTH, cap, scoreColor, verdictOf } from '../meta'
import type { Block } from '../types'
import { Gauge } from './Gauge'
import { Num, Reveal, ease } from './fx'
import { WorldMap } from './WorldMap'

export interface BlockActions {
  openReport: (topic?: string) => void
  openCampaign: () => void
  investigate: (caseId: string) => void
}

const I = { size: 16, strokeWidth: 1.5 }
const CAT_ICON: Record<string, ReactNode> = {
  impersonation: <UserRoundX {...I} />, payment: <Wallet {...I} />, exfiltration: <Send {...I} />, fraud: <AlertTriangle {...I} />, infrastructure: <Server {...I} />,
}
const TONE_ICON: Record<string, ReactNode> = { danger: <ShieldAlert {...I} className="ci" />, warn: <AlertTriangle {...I} className="ci" />, info: <Info {...I} className="ci" />, ok: <CheckCircle2 {...I} className="ci" /> }
const STEP_ICON: Record<string, ReactNode> = {
  sms: <MessageSquareText {...I} />, search: <Search {...I} />, map: <MapPin {...I} />, globe: <Globe2 {...I} />, message: <MessageSquare {...I} />, link: <Link2 {...I} />,
  page: <FileText {...I} />, form: <TextCursorInput {...I} />, card: <CreditCard {...I} />, otp: <KeyRound {...I} />, id: <IdCard {...I} />, login: <LogIn {...I} />,
  bot: <Bot {...I} />, wallet: <Wallet {...I} />, phone: <Phone {...I} />,
}

/** What each block type is called, shown in the layout trace. */
export const BLOCK_META: Record<string, { en: string; ar: string }> = {
  verdict_hero: { en: 'Verdict', ar: 'الحكم' },
  screenshot: { en: 'Screenshot', ar: 'لقطة الشاشة' },
  stat_row: { en: 'Key figures', ar: 'أرقام رئيسية' },
  callout: { en: 'Alert', ar: 'تنبيه' },
  markdown: { en: 'Narrative', ar: 'سرد' },
  journey: { en: 'Victim journey', ar: 'رحلة الضحية' },
  signal_list: { en: 'Signals', ar: 'المؤشرات' },
  score_breakdown: { en: 'Score maths', ar: 'حساب الدرجة' },
  campaign_card: { en: 'Campaign', ar: 'الحملة' },
  indicators: { en: 'Indicators', ar: 'المؤشرات التقنية' },
  kv_table: { en: 'Infrastructure', ar: 'البنية التحتية' },
  evidence_list: { en: 'Evidence', ar: 'الأدلة' },
  action_list: { en: 'Actions', ar: 'الإجراءات' },
}

function Title({ b, right }: { b: Block; right?: ReactNode }) {
  const { f } = useLang()
  return b.title ? <div className="card-h"><h3>{f(b, 'title')}</h3>{right}</div> : null
}

// ------------------------------------------------------------------ blocks

function Verdict({ b }: { b: Block }) {
  const { p, f, lang } = useLang()
  const v = verdictOf(b.verdict)
  return (
    <div className="card hero-verdict">
      <div className="col" style={{ alignItems: 'center', gap: 12 }}>
        <Gauge score={b.score} size={176} />
        <span className={`chip ${v.tone}`}>{lang === 'ar' ? v.ar : v.en}</span>
      </div>
      <div>
        <div className="eyebrow">{p('Case summary', 'ملخص القضية')}</div>
        <h2>{f(b, 'headline')}</h2>
        <p>{f(b, 'summary')}</p>
        <div className="row wrap">
          {(b.chips ?? []).map((c: any, i: number) => <span key={i} className={`chip ${c.tone}`}>{f(c, 'label')}</span>)}
        </div>
      </div>
    </div>
  )
}

function Screenshot({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} />
      <div className="card-b shot-block">
        <a className="shot-frame" href={b.src} target="_blank" rel="noreferrer"><img src={b.src} alt={p('Screenshot of the landing page', 'لقطة لصفحة الهبوط')} /></a>
        <div className="col" style={{ gap: 12, minWidth: 0 }}>
          <div><div className="eyebrow">{p('Landing page', 'صفحة الهبوط')}</div><div className="mono" style={{ fontSize: 13, wordBreak: 'break-all' }}>{b.final_url}</div></div>
          {b.chain?.length > 1 && (
            <div><div className="eyebrow" style={{ marginBottom: 4 }}>{p('Redirect chain', 'سلسلة التحويل')}</div>
              {b.chain.map((h: any, i: number) => <div key={i} className="chain-hop"><span className={`st s${String(h.status)[0]}`}>{h.status}</span>{h.url}</div>)}
            </div>
          )}
          <div className="row wrap">
            {b.engine && <span className="chip">{b.engine === 'browser' ? p('Rendered in isolated Chrome', 'عُرض في Chrome معزول') : p('HTTP fetch', 'جلب HTTP')}</span>}
            {b.cloaking && <span className="chip danger">{p('Cloaking', 'إخفاء')}: {b.cloaking}</span>}
            {b.trusted && <span className="chip ok">{b.trusted}</span>}
            {b.ai && b.ai.impersonates && b.ai.impersonates !== 'none' && <span className="chip danger">Claude: {b.ai.impersonates} ({Math.round((b.ai.confidence ?? 0) * 100)}%)</span>}
          </div>
          {b.ai?.reason && <div className="muted" style={{ fontSize: 13 }}>{b.ai.reason}</div>}
          <div className="faint" style={{ fontSize: 12 }}>{p('Captured', 'التُقطت')} {b.captured} · {p('mobile profile, UAE locale · SHA-256 in the evidence list', 'ملف جوال بإعدادات الإمارات · بصمة SHA-256 في قائمة الأدلة')}</div>
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
        <div key={i} className="card tile-stat">
          <div className="fig-label">{(it.tone === 'danger' || it.tone === 'warn') && <span className={`dot ${it.tone}`} style={{ width: 6, height: 6 }} />}{f(it, 'label')}</div>
          <div className="fig"><Num value={Number(it.value)} ms={900} /><small>{it.suffix}</small></div>
          {(it.hint || it.hint_ar) && <div className="fig-sub">{f(it, 'hint')}</div>}
        </div>
      ))}
    </div>
  )
}

function Callout({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className={`card callout ${b.tone}`}>
      {TONE_ICON[b.tone] ?? TONE_ICON.info}
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
    <div className="card card-p prose">
      {b.title && <h4>{f(b, 'title')}</h4>}
      {f(b, 'text').split(/\n\n+/).map((t: string, i: number) => <p key={i}>{t}</p>)}
    </div>
  )
}

function Journey({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className="card">
      <Title b={b} />
      <div className="card-b">
        <div className="journey">
          {b.steps.map((st: any, i: number) => (
            <Fragment key={i}>
              <div className={`j-step ${st.tone}`}>
                <div className="j-ico">{STEP_ICON[st.icon] ?? <FileText {...I} />}</div>
                <span className="j-n">{String(i + 1).padStart(2, '0')}</span>
                <b>{f(st, 'title')}</b>
                {(st.detail || st.detail_ar) && <small>{f(st, 'detail')}</small>}
              </div>
              {i < b.steps.length - 1 && <ChevronRight size={16} strokeWidth={1.5} className="j-link flip-rtl" />}
            </Fragment>
          ))}
        </div>
        <p className="muted" style={{ margin: '16px 0 0', fontSize: 13 }}>{f(b, 'summary')}</p>
      </div>
    </div>
  )
}

function Signals({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} right={<span className="right mono num" style={{ fontSize: 12 }}>{b.items.length}</span>} />
      <div className="list">
        {b.items.map((s: any) => (
          <div key={s.id} className={`sig ${s.severity}`}>
            <div className="si">{CAT_ICON[s.category] ?? <Info {...I} />}</div>
            <div><p>{f(s, 'label')}</p><small>{cap(s.category)}</small></div>
            <span className="w">+{Math.round(s.weight * 100)}</span>
          </div>
        ))}
        {!b.items.length && <div className="empty">{p('No scam signals were found', 'لم يتم العثور على أي مؤشرات احتيال')}</div>}
      </div>
    </div>
  )
}

function Breakdown({ b }: { b: Block }) {
  const { f, p, lang } = useLang()
  const origin = lang === 'ar' ? 'right' : 'left'
  return (
    <div className="card">
      <Title b={b} />
      <div className="card-b col" style={{ gap: 8 }}>
        {b.items.map((r: any, i: number) => (
          <div key={r.id} className="wf-row">
            <span className="wf-label" title={f(r, 'label')}>{f(r, 'label')}</span>
            <div className="wf-track">
              <motion.i className={r.severity} style={{ insetInlineStart: `${r.start}%`, width: `${Math.max(1.5, r.end - r.start)}%`, transformOrigin: origin }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }}
                transition={{ duration: 0.4, delay: 0.05 + Math.min(i, 6) * 0.05, ease }} />
            </div>
            <span className="wf-val">+{r.weight}<small>→ {r.end}</small></span>
          </div>
        ))}
        <div className="wf-row total">
          <span className="wf-label">{p('Total risk score', 'درجة الخطورة الإجمالية')}</span>
          <div className="wf-track">
            <motion.i style={{ insetInlineStart: 0, width: `${b.score}%`, transformOrigin: origin, background: scoreColor(b.score) }} initial={{ scaleX: 0 }} whileInView={{ scaleX: 1 }} viewport={{ once: true }}
              transition={{ duration: 0.6, delay: 0.2, ease }} />
          </div>
          <span className="wf-val" style={{ color: 'var(--text)' }}><b>{b.score}</b></span>
        </div>
        <div className="faint" style={{ fontSize: 12, marginTop: 4 }}>{f(b, 'note')}</div>
      </div>
    </div>
  )
}

function Campaign({ b, act }: { b: Block; act: BlockActions }) {
  const { f, p, lang } = useLang()
  return (
    <div className="card">
      <div className="card-h">
        <h3>{f(b, 'title')}</h3>
        {b.cluster_id && <span className="tag-id">{b.cluster_id}</span>}
        {b.cluster_id && <span className="sub num">{b.cluster_size} {p('sites', 'موقعاً')}</span>}
        <button className="btn btn-sm right" onClick={act.openCampaign}>{p('Open graph', 'فتح الرسم')} <ArrowUpRight size={14} strokeWidth={1.5} /></button>
      </div>
      {b.unblocked > 0 && (
        <div className="callout" style={{ borderBottom: '1px solid var(--line)', padding: '12px 20px' }}>
          <Megaphone size={16} strokeWidth={1.5} className="ci" color="var(--orange)" />
          <p><span className="num" style={{ color: 'var(--text)' }}>{b.unblocked}</span> {p('linked scam sites are not on any public blocklist yet', 'من المواقع الاحتيالية المرتبطة غير مدرجة بعد في أي قائمة حجب عامة')}</p>
        </div>
      )}
      <div className="list">
        {b.items.map((r: any) => (
          <div key={r.case_id} className="camp-item list-row">
            <div className="row" style={{ minWidth: 0 }}>
              <span className="dot" style={{ background: scoreColor(r.score) }} />
              <span className="mono ellipsis" style={{ fontSize: 13 }}>{r.kind === 'maps_listing' ? r.label : r.host}</span>
              {r.kind === 'maps_listing' && <span className="chip">{p('Maps', 'خرائط')}</span>}
            </div>
            <div className="row" style={{ gap: 12 }}>
              <span className="faint" style={{ fontSize: 12 }}>{lang === 'ar' ? STRENGTH[r.strength as 'strong'].ar : STRENGTH[r.strength as 'strong'].en}</span>
              <span className="score-n" style={{ color: scoreColor(r.score), fontSize: 14, minWidth: 24 }}>{r.score}</span>
              {r.kind === 'site' && <button className="btn btn-sm btn-ghost" title={p('Investigate', 'تحقيق')} aria-label={p('Investigate', 'تحقيق')} onClick={() => act.investigate(r.case_id)}><Search size={14} strokeWidth={1.5} /></button>}
            </div>
            <div className="why">{f(r, 'reason')}{r.on_blocklist ? '' : r.kind === 'site' && r.score >= 60 ? ' · ' + p('not blocklisted', 'غير محجوب') : ''}</div>
          </div>
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
      <Title b={b} />
      <div className="card-b col" style={{ gap: 16 }}>
        {b.groups.map((g: any, gi: number) => (
          <div key={gi}>
            <div className="eyebrow" style={{ marginBottom: 8 }}>{f(g, 'title')}</div>
            <div className="row wrap">
              {g.items.map((it: any, i: number) => {
                const val = it.copy ?? it.value
                return (
                  <button key={i} className="ioc" onClick={() => copy(val)} title={p('Copy', 'نسخ')}>
                    {(it.tone === 'danger' || it.tone === 'warn') && <span className={`dot ${it.tone}`} style={{ width: 6, height: 6 }} />}
                    <span className="mono">{it.value}</span>
                    {copied === val ? <Check size={14} strokeWidth={1.5} /> : <Copy size={14} strokeWidth={1.5} />}
                  </button>
                )
              })}
            </div>
          </div>
        ))}
        <div className="faint" style={{ fontSize: 12 }}>{p('Click an indicator to copy it. These can be shared with banks, platforms and other agencies.', 'اضغط على أي مؤشر لنسخه. يمكن مشاركتها مع البنوك والمنصات والجهات الأخرى.')}</div>
      </div>
    </div>
  )
}

function KV({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} />
      <div className="card-b">
        <dl className="kv">
          {b.rows.map((r: any, i: number) => (
            <div key={i} style={{ display: 'contents' }}>
              <dt>{f(r, 'k')}</dt>
              <dd className={`${r.mono ? 'mono' : ''} ${r.tone ?? ''}`} style={{ fontSize: r.mono ? 12 : 13 }}>{r.v}</dd>
            </div>
          ))}
          {!b.rows.length && <dd className="muted" style={{ gridColumn: '1/-1' }}>{p('Not browsed, so no infrastructure data was captured', 'لم يتم التصفح، لذا لم تُجمع بيانات البنية التحتية')}</dd>}
        </dl>
        {b.country && <div style={{ marginTop: 12 }}><WorldMap data={{ [b.country]: 1 }} compact /></div>}
        {b.note && !b.country && <div className="faint" style={{ fontSize: 12, marginTop: 12 }}>{f(b, 'note')}</div>}
      </div>
    </div>
  )
}

function Evidence({ b }: { b: Block }) {
  const { p, f } = useLang()
  return (
    <div className="card">
      <Title b={b} />
      <div className="card-b">
        <div className="manifest">
          {p('Manifest SHA-256, covering every item below. Changing any artefact changes this value.', 'بصمة SHA-256 للبيان، تغطي كل العناصر أدناه. أي تعديل على أي دليل يغيّر هذه القيمة.')}
          <div className="mono">{b.manifest}</div>
        </div>
        <div style={{ maxHeight: 340, overflow: 'auto' }}>
          {b.items.map((e: any) => (
            <div className="ev" key={e.id}>
              <span><span className="tag-id">{e.id}</span></span>
              <div><div>{f(e, 'label')}</div><div className="hash">{e.sha256}</div><div className="faint" style={{ fontSize: 12 }}>{e.kind} · {e.ts}</div></div>
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
      <Title b={b} />
      <div className="list">
        {b.items.map((a: any, i: number) => (
          <div key={a.id} className={`act list-row ${a.priority}`}>
            <div className="n">{a.priority === 'now' ? p('Now', 'الآن') : String(i + 1).padStart(2, '0')}</div>
            <div><b>{f(a, 'label')}</b>{a.detail && <small>{a.detail}</small>}</div>
            <button className="btn btn-sm" onClick={() => act.openReport(a.target ?? a.kind)}>
              {a.kind === 'blocklist' ? <><Download size={14} strokeWidth={1.5} /> CSV</> : a.kind === 'warning' || a.kind === 'takedown' ? <><FileText size={14} strokeWidth={1.5} /> {p('Draft', 'مسودة')}</> : <><Radar size={14} strokeWidth={1.5} /> {p('Open', 'فتح')}</>}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}


// ------------------------------------------------------------------ layout trace + renderer

/** Shows which blocks were chosen, in order: the visible trace of the generative layout. */
export function LayoutStrip({ blocks, source }: { blocks: Block[]; source: string }) {
  const { p, lang } = useLang()
  const names = blocks.map((b) => BLOCK_META[b.type]).filter(Boolean).map((m) => (lang === 'ar' ? m.ar : m.en))
  return (
    <div className="layout-strip">
      <b>{source === 'claude' ? p('Layout composed by Claude', 'التخطيط من تصميم Claude') : p('Layout composed by the offline writer', 'التخطيط من الكاتب غير المتصل')}</b>
      {' · '}{names.join(lang === 'ar' ? ' ← ' : ' → ')}
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
          default: return null
        }
        return <Reveal key={i} i={i} className={SPAN.has(b.type) ? 'span' : ''}>{node}</Reveal>
      })}
    </div>
  )
}
