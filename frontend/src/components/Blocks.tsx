import { AlertTriangle, ArrowUpRight, Ban, CheckCircle2, Download, FileText, Flame, Info, Landmark, Megaphone, Radar, Search, Server, ShieldAlert, Smartphone, Sparkles, Wallet, Send, UserRoundX } from 'lucide-react'
import type { ReactNode } from 'react'
import { useLang } from '../i18n'
import { STRENGTH, scoreColor, verdictOf } from '../meta'
import type { Block } from '../types'
import { Gauge } from './Gauge'
import { HostingBars, UaeMap } from './Maps'

export interface BlockActions {
  openReport: (topic?: string) => void
  openCampaign: () => void
  investigate: (caseId: string) => void
}

const CAT_ICON: Record<string, ReactNode> = {
  impersonation: <UserRoundX size={17} />, payment: <Wallet size={17} />, exfiltration: <Send size={17} />, fraud: <AlertTriangle size={17} />, infrastructure: <Server size={17} />,
}
const TONE_ICON: Record<string, ReactNode> = { danger: <ShieldAlert size={20} />, warn: <AlertTriangle size={20} />, info: <Info size={20} />, ok: <CheckCircle2 size={20} /> }

function Title({ b }: { b: Block }) {
  const { f } = useLang()
  return b.title ? <div className="card-h"><h3>{f(b, 'title')}</h3></div> : null
}

function Verdict({ b }: { b: Block }) {
  const { p, f, lang } = useLang()
  const v = verdictOf(b.verdict)
  return (
    <div className={`card hero-verdict ${b.tone}`}>
      <div className="col" style={{ alignItems: 'center', gap: 4 }}>
        <Gauge score={b.score} size={170} />
        <span className={`chip ${v.tone}`}>{lang === 'ar' ? v.ar : v.en}</span>
      </div>
      <div>
        <div className="eyebrow row"><Sparkles size={13} /> {p('Case summary', 'ملخص القضية')}</div>
        <h2>{f(b, 'headline')}</h2>
        <p>{f(b, 'summary')}</p>
        <div className="row wrap">
          {(b.chips ?? []).map((c: any, i: number) => <span key={i} className={`chip ${c.tone}`}>{f(c, 'label')}</span>)}
        </div>
      </div>
    </div>
  )
}

function Callout({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className={`callout ${b.tone}`}>
      <div style={{ color: b.tone === 'danger' ? '#ff8da4' : b.tone === 'warn' ? '#ffc766' : b.tone === 'ok' ? '#6ee7b7' : '#7dd3fc' }}>{TONE_ICON[b.tone] ?? TONE_ICON.info}</div>
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
      {f(b, 'text').split(/\n\n+/).map((t: string, i: number) => <p key={i} style={{ margin: '0 0 8px', color: '#c3cde6' }}>{t}</p>)}
    </div>
  )
}

function Signals({ b }: { b: Block }) {
  const { f, p } = useLang()
  return (
    <div className="card">
      <Title b={b} />
      <div className="card-b col" style={{ gap: 8 }}>
        {b.items.map((s: any) => (
          <div key={s.id} className={`sig ${s.severity}`}>
            <div className="si">{CAT_ICON[s.category] ?? <Info size={17} />}</div>
            <div>
              <p>{f(s, 'label')}</p>
              <small>{s.category}</small>
            </div>
            <span className="w">+{Math.round(s.weight * 100)}</span>
          </div>
        ))}
        {!b.items.length && <div className="muted">{p('No scam signals were found.', 'لم يتم العثور على أي مؤشرات احتيال.')}</div>}
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
        {b.cluster_id && <span className="chip violet">{b.cluster_id} · {b.cluster_size} {p('sites', 'موقعاً')}</span>}
        <button className="btn btn-sm right" onClick={act.openCampaign}>{p('Open graph', 'فتح الرسم')} <ArrowUpRight size={14} /></button>
      </div>
      <div className="card-b col" style={{ gap: 8 }}>
        {b.unblocked > 0 && (
          <div className="callout warn" style={{ padding: '10px 12px' }}>
            <Megaphone size={18} color="#ffc766" />
            <p><b>{b.unblocked}</b> {p('linked scam site(s) are not on any public blocklist yet.', 'من المواقع الاحتيالية المرتبطة غير مدرجة بعد في أي قائمة حجب عامة.')}</p>
          </div>
        )}
        {b.items.map((r: any) => (
          <div key={r.case_id} className="camp-item">
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
          </div>
        ))}
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
        <dl className="kv" style={{ margin: 0 }}>
          {b.rows.map((r: any, i: number) => (
            <div key={i} style={{ display: 'contents' }}>
              <dt>{f(r, 'k')}</dt>
              <dd className={`${r.mono ? 'mono' : ''} ${r.tone ?? ''}`} style={{ fontSize: r.mono ? 12 : 12.5 }}>{r.v}</dd>
            </div>
          ))}
          {!b.rows.length && <dd className="muted" style={{ gridColumn: '1/-1' }}>{p('Not browsed, so no infrastructure data was captured.', 'لم يتم التصفح، لذا لم تُجمع بيانات البنية التحتية.')}</dd>}
        </dl>
        {b.note && <div className="faint" style={{ fontSize: 11.5, marginTop: 10 }}>{f(b, 'note')}</div>}
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
        <div className="callout info" style={{ padding: '10px 12px', marginBottom: 8 }}>
          <Landmark size={18} color="#7dd3fc" />
          <div>
            <p style={{ fontSize: 12.5 }}>{p('Manifest SHA-256 (covers every item below). Changing any artefact changes this value.', 'بصمة SHA-256 للبيان (تغطي كل العناصر أدناه). أي تعديل على أي دليل يغيّر هذه القيمة.')}</p>
            <div className="mono" style={{ fontSize: 11, wordBreak: 'break-all', marginTop: 4, color: '#a5d8ff' }}>{b.manifest}</div>
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
      <Title b={b} />
      <div className="card-b col" style={{ gap: 8 }}>
        {b.items.map((a: any, i: number) => (
          <div key={a.id} className={`act ${a.priority}`}>
            <div className="n">{a.priority === 'now' ? <Flame size={16} /> : i + 1}</div>
            <div><b>{f(a, 'label')}</b>{a.detail && <small>{a.detail}</small>}</div>
            <button className="btn btn-sm" onClick={() => act.openReport(a.target ?? a.kind)}>
              {a.kind === 'blocklist' ? <><Download size={13} /> CSV</> : a.kind === 'warning' ? <><Megaphone size={13} /> {p('Draft', 'مسودة')}</> : a.kind === 'takedown' ? <><FileText size={13} /> {p('Draft', 'مسودة')}</> : <><Radar size={13} /> {p('Open', 'فتح')}</>}
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

function MapBlock({ b }: { b: Block }) {
  const { f } = useLang()
  return (
    <div className="card">
      <Title b={b} />
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

export function BlockRenderer({ blocks, act }: { blocks: Block[]; act: BlockActions }) {
  return (
    <div className="blocks">
      {blocks.map((b, i) => {
        const span = ['verdict_hero', 'callout', 'markdown'].includes(b.type)
        let node: ReactNode
        switch (b.type) {
          case 'verdict_hero': node = <Verdict b={b} />; break
          case 'callout': node = <Callout b={b} />; break
          case 'markdown': node = <Markdown b={b} />; break
          case 'signal_list': node = <Signals b={b} />; break
          case 'campaign_card': node = <Campaign b={b} act={act} />; break
          case 'kv_table': node = <KV b={b} />; break
          case 'evidence_list': node = <Evidence b={b} />; break
          case 'action_list': node = <Actions b={b} act={act} />; break
          case 'emirate_map': node = <MapBlock b={b} />; break
          default: node = <Fallback b={b} />
        }
        return <div key={i} className={span ? 'span wf-enter' : 'wf-enter'} style={{ animationDelay: `${i * 70}ms`, animationFillMode: 'backwards' }}>{node}</div>
      })}
    </div>
  )
}

export { HostingBars }
export { Ban }
