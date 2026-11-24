import { useEffect, useState } from 'react'
import { Check, ChevronDown, ChevronUp, Copy, Download, FileText } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import { SCAM_TYPES, verdictOf } from '../meta'

function CopyBtn({ text }: { text: string }) {
  const { p } = useLang()
  const [ok, setOk] = useState(false)
  return (
    <button className="btn btn-sm" onClick={() => { navigator.clipboard?.writeText(text); setOk(true); setTimeout(() => setOk(false), 1400) }}>
      {ok ? <><Check size={14} strokeWidth={1.5} /> {p('Copied', 'تم النسخ')}</> : <><Copy size={14} strokeWidth={1.5} /> {p('Copy', 'نسخ')}</>}
    </button>
  )
}

export function ReportPack({ runId, focus }: { runId: string; focus?: string }) {
  const { p, lang, f } = useLang()
  const [data, setData] = useState<any>(null)
  const [pack, setPack] = useState<any>(null)
  const [open, setOpen] = useState<string | null>(focus ?? null)

  useEffect(() => {
    api.investigation(runId).then((r) => setData(r.result)).catch(() => {})
    api.pack(runId).then(setPack).catch(() => {})
  }, [runId])
  useEffect(() => { if (focus) setOpen(focus) }, [focus])

  if (!data?.ctx || !pack) return <div className="card card-p"><div className="skeleton" style={{ height: 22, width: '40%' }} /><div className="skeleton" style={{ height: 300, marginTop: 14 }} /></div>
  const { ctx, refined } = data
  const v = verdictOf(ctx.verdict)
  const st = SCAM_TYPES[ctx.scam_type] ?? SCAM_TYPES.unknown
  const T = [
    ['registrar', p('Registrar takedown', 'طلب تعليق من المسجّل')],
    ['host', p('Hosting provider abuse report', 'بلاغ إساءة لمزود الاستضافة')],
    ['safebrowsing', p('Google Safe Browsing report', 'بلاغ Google Safe Browsing')],
    ['maps', p('Google Maps listing report', 'بلاغ عن موقع في خرائط جوجل')],
  ] as const

  return (
    <div className="report-grid">
      <div className="paper" dir="ltr">
        <div className="row between" style={{ alignItems: 'flex-start' }}>
          <div>
            <div className="letterhead">Raqib case report</div>
            <h1>{refined.headline}</h1>
            <div className="meta">Case {runId.toUpperCase()} · {ctx.observed_at} · {ctx.evidence_mode} evidence · summary by {data.source}</div>
          </div>
          <div style={{ textAlign: 'end' }}><div className="big" style={{ color: v.color }}>{ctx.score}</div><div className="meta">/ 100 · {v.en}</div></div>
        </div>
        <p style={{ marginTop: 14 }}>{refined.summary}</p>
        <h4>Subject</h4>
        <table><tbody>
          <tr><th style={{ width: 120 }}>Input URL</th><td className="mono">{ctx.input_url}</td></tr>
          <tr><th>Domain</th><td className="mono">{ctx.domain}</td></tr>
          <tr><th>Scam type</th><td>{st.en}</td></tr>
          <tr><th>Impersonated</th><td>{ctx.brand?.name ?? '—'}</td></tr>
          <tr><th>Campaign</th><td>{ctx.cluster_id ?? '—'} ({ctx.cluster_size} sites)</td></tr>
        </tbody></table>
        {ctx.verdict !== 'no_indicators' && ctx.verdict !== 'official' && <><h4>How the victim is deceived</h4><p>{refined.victim_impact}</p></>}
        <h4>Why this score</h4>
        <table><thead><tr><th>Signal</th><th style={{ width: 90 }}>Category</th><th style={{ width: 44 }}>Wt.</th></tr></thead><tbody>
          {[...ctx.signals].sort((a: any, b: any) => b.weight - a.weight).map((s: any) => <tr key={s.id}><td>{s.label}</td><td>{s.category}</td><td>{Math.round(s.weight * 100)}</td></tr>)}
        </tbody></table>
        {!!ctx.related.length && <>
          <h4>Campaign {ctx.cluster_id}: connected sites</h4>
          <table><thead><tr><th>Site</th><th style={{ width: 40 }}>Score</th><th style={{ width: 60 }}>Link</th><th>Why</th></tr></thead><tbody>
            {ctx.related.map((r: any) => <tr key={r.case_id}><td className="mono">{r.host}</td><td>{r.score}</td><td>{r.strength}</td><td>{r.reasons[0].text}</td></tr>)}
          </tbody></table>
          <div className="note" style={{ marginTop: 4 }}>Strong links are shared operator tooling or contact details. Weak links do not prove a shared operator.</div>
        </>}
        <h4>Evidence chain of custody</h4>
        <div style={{ fontSize: 12 }}>Manifest SHA-256: <span className="hash">{ctx.manifest}</span></div>
        <table style={{ marginTop: 6 }}><tbody>
          {ctx.evidence.map((e: any) => <tr key={e.id}><td style={{ width: 52 }} className="mono">{e.id}</td><td>{e.label}<div className="hash">{e.sha256}</div></td></tr>)}
        </tbody></table>
        <div className="note" style={{ marginTop: 24 }}>Decision support only; officer review is required. Hosting location is an infrastructure indicator, not the location of the operator.</div>
      </div>

      <div className="col" style={{ gap: 16 }}>
        <div className="card card-p col" style={{ gap: 12 }}>
          <div className="eyebrow">{p('Download', 'تنزيل')}</div>
          <div className="row wrap">
            <a className="btn btn-primary" href={`/api/investigations/${runId}/report.pdf`} target="_blank" rel="noreferrer"><FileText size={14} strokeWidth={1.5} /> {p('Case report (PDF)', 'تقرير القضية (PDF)')}</a>
            <a className="btn" href={`/api/investigations/${runId}/blocklist.csv`}><Download size={14} strokeWidth={1.5} /> {p('Blocklist (CSV)', 'قائمة الحجب (CSV)')}</a>
            <a className="btn" href={`/api/investigations/${runId}/bundle.json`}><Download size={14} strokeWidth={1.5} /> {p('Case bundle (JSON)', 'حزمة القضية (JSON)')}</a>
          </div>
          <div className="faint" style={{ fontSize: 12 }}>{p('The PDF includes English and Arabic summaries, the campaign graph and the evidence hashes.', 'يتضمن ملف PDF ملخصاً بالعربية والإنجليزية ورسم الحملة وبصمات الأدلة.')}</div>
        </div>

        <div className="card">
          <div className="card-h"><h3>{p('Public warning', 'تنبيه للجمهور')}</h3><span className="sub">{p('Draft', 'مسودة')}</span></div>
          <div className="card-b col" style={{ gap: 12 }}>
            <div className="draft" style={{ fontFamily: 'var(--font)' }}>{pack.warning.en}</div>
            <div className="draft" dir="rtl" style={{ fontFamily: 'var(--font)' }}>{pack.warning.ar}</div>
            <div className="row"><CopyBtn text={pack.warning.en} /><CopyBtn text={pack.warning.ar} /></div>
          </div>
        </div>

        <div className="card">
          <div className="card-h"><h3>{p('Takedown requests', 'طلبات الإزالة')}</h3><span className="sub">{p('Drafts for officer review', 'مسودات للمراجعة')}</span></div>
          <div className="card-b col accordion">
            {T.map(([k, label]) => (
              <div key={k}>
                <button className="acc" aria-expanded={open === k} onClick={() => setOpen(open === k ? null : k)}>{label}<span className="right faint">{open === k ? <ChevronUp size={16} strokeWidth={1.5} /> : <ChevronDown size={16} strokeWidth={1.5} />}</span></button>
                {open === k && (
                  <div className="col" style={{ marginTop: 8 }}>
                    <div className="faint" style={{ fontSize: 13 }}>{p('To', 'إلى')}: {pack.takedowns[k].to} · {p('Subject', 'الموضوع')}: {pack.takedowns[k].subject}</div>
                    <div className="draft">{pack.takedowns[k].body}</div>
                    <div><CopyBtn text={`${pack.takedowns[k].subject}\n\n${pack.takedowns[k].body}`} /></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
        <div className="faint" style={{ fontSize: 12 }}>{lang === 'ar' ? 'لا يرسل رقيب أي شيء تلقائياً؛ جميع الطلبات مسودات يراجعها المحقق.' : 'Raqib never sends anything by itself; every request is a draft an officer reviews.'}{f({}, '')}</div>
      </div>
    </div>
  )
}
