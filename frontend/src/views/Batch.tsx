import type React from 'react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Download, FileUp, Globe2, ListChecks, Loader2, Play, ShieldCheck, Square, XCircle } from 'lucide-react'
import { api } from '../api'
import { Num, Rise, soft } from '../components/fx'
import { useLang } from '../i18n'
import { scoreColor, verdictOf } from '../meta'
import type { Nav } from './Investigation'

interface Row { n: number; input_url: string; final_url?: string; expected?: string | null; label: string; correct?: boolean | null; score: number; verdict: string; reasons: string[]; engine?: string; seconds?: number; error?: string | null; brand?: string | null; cloaking?: string | null }
interface Snap { id: string; total: number; done: number; finished: boolean; seconds: number; threshold: number; results: Row[]; metrics: any }

const I = { size: 14, strokeWidth: 1.5 }

function Metric({ label, value, hint }: { label: string; value: number | null | undefined; hint: string }) {
  return (
    <div>
      <div className="fig-label">{label}</div>
      <div className="fig">{value == null ? '–' : <><Num value={Math.round(value * 1000) / 10} ms={700} /><small>%</small></>}</div>
      <div className="fig-sub">{hint}</div>
    </div>
  )
}

export function Batch({ nav }: { nav: Nav }) {
  const { p, lang } = useLang()
  const [text, setText] = useState('')
  const [browser, setBrowser] = useState(true)
  const [ai, setAi] = useState(false)
  const [snap, setSnap] = useState<Snap | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const timer = useRef<number | null>(null)
  const file = useRef<HTMLInputElement>(null)

  useEffect(() => () => { if (timer.current) window.clearInterval(timer.current) }, [])

  const count = useMemo(() => text.split(/\r?\n/).filter((l) => l.trim() && !l.trim().startsWith('#') && !/^url\b/i.test(l.trim())).length, [text])

  const sample = async (kind: string) => {
    setLoading(kind); setErr(null)
    try { const r = await api.batchSample(kind); setText(r.text) } catch (e: any) { setErr(e.message) } finally { setLoading(null) }
  }
  const start = async () => {
    setErr(null); setBusy(true); setSnap(null)
    try {
      const { id } = await api.batchStart({ text, use_browser: browser, use_ai: ai, concurrency: 4 })
      const poll = async () => {
        const s = await api.batch(id)
        setSnap(s)
        if (s.finished && timer.current) { window.clearInterval(timer.current); timer.current = null; setBusy(false) }
      }
      await poll()
      timer.current = window.setInterval(poll, 1200)
    } catch (e: any) { setErr(e.message); setBusy(false) }
  }
  const stop = async () => { if (snap) await api.batchCancel(snap.id) }
  const onFile = async (f: File | undefined) => { if (f) setText(await f.text()) }

  const m = snap?.metrics
  const rows = useMemo(() => [...(snap?.results ?? [])].sort((a, b) => a.n - b.n), [snap])
  const spin = (k: string, icon: React.ReactNode) => (loading === k ? <Loader2 size={14} className="spin" /> : icon)

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <div className="eyebrow">{p('Detection accuracy', 'دقة الكشف')}</div>
          <h1>{p('Batch scan and evaluation', 'الفحص الجماعي والتقييم')}</h1>
          <p>{p('Paste a list of URLs, or a CSV with url,label. Raqib opens each one in the isolated browser, follows redirects and short links, checks for cloaking and scores it. With labels it reports precision, recall and F1.', 'الصق قائمة روابط أو ملف CSV بعمودي url,label. يفتح رقيب كل رابط في المتصفح المعزول ويتتبع التحويلات والروابط المختصرة ويكشف الإخفاء ثم يقيّمه. ومع التصنيفات يحسب الدقة والاستدعاء وF1.')}</p>
        </div>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.25fr) minmax(0,1fr)', alignItems: 'stretch' }}>
        <Rise>
          <div className="card" style={{ height: '100%' }}>
            <div className="card-h"><h3>{p('URLs to scan', 'الروابط المطلوب فحصها')}</h3><span className="right mono num" style={{ fontSize: 12 }}>{count} {p('URLs', 'رابط')}</span></div>
            <div className="card-b col" style={{ gap: 12 }}>
              <textarea className="input mono batch-input" value={text} onChange={(e) => setText(e.target.value)} dir="ltr" spellCheck={false} aria-label={p('URLs to scan', 'الروابط المطلوب فحصها')}
                placeholder={'url,label\nhttps://example-bank-verify.top/login,fraud\nhttps://www.rta.ae,legit\nbit.ly/xxxx'} />
              <div className="row wrap" style={{ gap: 4 }}>
                <span className="faint" style={{ fontSize: 13, marginInlineEnd: 4 }}>{p('Samples', 'عينات')}</span>
                <button className="btn btn-sm" onClick={() => sample('mixed')} disabled={!!loading}>{spin('mixed', <ListChecks {...I} />)} {p('Demo cases and real UAE sites', 'حالات تجريبية ومواقع إماراتية حقيقية')}</button>
                <button className="btn btn-sm" onClick={() => sample('legit')} disabled={!!loading}>{spin('legit', <ShieldCheck {...I} />)} {p('Real UAE sites only', 'مواقع إماراتية حقيقية فقط')}</button>
                <button className="btn btn-sm" onClick={() => sample('openphish')} disabled={!!loading}>{spin('openphish', <Globe2 {...I} />)} {p('Live phishing (OpenPhish)', 'تصيّد حي (OpenPhish)')}</button>
                <button className="btn btn-sm btn-ghost" onClick={() => file.current?.click()}><FileUp {...I} /> {p('Upload file', 'رفع ملف')}</button>
                <input ref={file} type="file" accept=".txt,.csv,.tsv" hidden onChange={(e) => onFile(e.target.files?.[0])} />
              </div>
            </div>
          </div>
        </Rise>
        <Rise i={1}>
          <div className="card" style={{ height: '100%' }}>
            <div className="card-h"><h3>{p('Run', 'تشغيل')}</h3></div>
            <div className="card-b col" style={{ gap: 16 }}>
              <label className="toggle"><input type="checkbox" checked={browser} onChange={(e) => setBrowser(e.target.checked)} /><span><b>{p('Isolated browser', 'المتصفح المعزول')}</b><small>{p('Renders JavaScript and takes screenshots. Off gives a fast HTTP-only scan.', 'يعرض JavaScript ويلتقط الصور. عند الإيقاف: فحص HTTP سريع فقط.')}</small></span></label>
              <label className="toggle"><input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} /><span><b>{p('Claude vision check', 'فحص بصري بـ Claude')}</b><small>{p('Looks at each screenshot for brand impersonation. Needs an API key and is slower.', 'يفحص كل لقطة بحثاً عن انتحال العلامات. يتطلب مفتاح API وأبطأ.')}</small></span></label>
              <div className="row wrap">
                {busy ? <button className="btn" onClick={stop}><Square {...I} /> {p('Stop', 'إيقاف')}</button>
                  : <button className="btn btn-primary" disabled={!count} onClick={start}><Play {...I} className="flip-rtl" /> {p(`Scan ${count} URLs`, `فحص ${count} رابط`)}</button>}
                {snap && <>
                  <a className="btn btn-sm" href={`/api/batch/${snap.id}/results.csv`}><Download {...I} /> CSV</a>
                  <a className="btn btn-sm" href={`/api/batch/${snap.id}/results.json`}><Download {...I} /> JSON</a>
                </>}
              </div>
              {err && <div className="callout danger card" style={{ padding: 12, fontSize: 13 }}>{err}</div>}
              {snap && (
                <div>
                  <div className="row between" style={{ fontSize: 13, marginBottom: 8 }}><span className="muted">{snap.finished ? p('Finished', 'اكتمل') : p('Scanning…', 'جارٍ الفحص…')}</span><span className="mono num">{snap.done}/{snap.total} · {snap.seconds}s</span></div>
                  <div className="progress"><motion.i style={{ transformOrigin: lang === 'ar' ? 'right' : 'left' }} animate={{ scaleX: snap.done / Math.max(1, snap.total) }} initial={{ scaleX: 0 }} transition={soft} /></div>
                </div>
              )}
              <div className="faint" style={{ fontSize: 12 }}>{p(`A URL counts as fraud when its score is ${snap?.threshold ?? 60} or more. Demo cases on fictional .test domains are scored from their recorded evidence.`, `يُعد الرابط احتيالياً عندما تبلغ درجته ${snap?.threshold ?? 60} أو أكثر. الحالات التجريبية على نطاقات .test الوهمية تُقيَّم من أدلتها المسجّلة.`)}</div>
            </div>
          </div>
        </Rise>
      </div>

      <AnimatePresence>
        {m && m.labelled > 0 && (
          <motion.div className="metrics-row" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={soft}>
            <div className="card metrics">
              <Metric label={p('Precision', 'الدقة')} value={m.precision} hint={p('Flagged URLs that really are scams', 'روابط مُعلَّمة وهي احتيالية فعلاً')} />
              <Metric label={p('Recall', 'الاستدعاء')} value={m.recall} hint={p('Scams that were caught', 'احتيالات تم كشفها')} />
              <Metric label="F1" value={m.f1} hint={p('Balance of both', 'توازن الاثنين')} />
              <Metric label={p('False-positive rate', 'معدل الإنذار الكاذب')} value={m.false_positive_rate} hint={p('Legitimate sites wrongly flagged', 'مواقع سليمة عُلّمت خطأً')} />
            </div>
            <div className="card confusion">
              <div className="cm-h" /><div className="cm-h">{p('Predicted fraud', 'متوقع: احتيال')}</div><div className="cm-h">{p('Predicted legit', 'متوقع: سليم')}</div>
              <div className="cm-h">{p('Actually fraud', 'فعلياً: احتيال')}</div><div className="cm good">{m.tp}<small>TP</small></div><div className="cm bad">{m.fn}<small>FN</small></div>
              <div className="cm-h">{p('Actually legit', 'فعلياً: سليم')}</div><div className="cm bad">{m.fp}<small>FP</small></div><div className="cm good">{m.tn}<small>TN</small></div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {snap && (
        <div className="card">
          <div className="card-h"><h3>{p('Results', 'النتائج')}</h3><span className="sub right"><span className="num">{rows.filter((r) => r.label === 'fraud').length}</span> {p('flagged as fraud', 'مُعلَّم كاحتيال')}</span></div>
          <div style={{ overflow: 'auto', maxHeight: 640 }}>
            <table className="table batch-table">
              <thead><tr><th>#</th><th>URL</th><th>{p('Score', 'الدرجة')}</th><th>{p('Verdict', 'الحكم')}</th><th>{p('Expected', 'المتوقع')}</th><th>{p('Top reasons', 'أهم الأسباب')}</th><th>{p('Engine', 'المحرك')}</th><th /></tr></thead>
              <tbody>
                {rows.map((r) => {
                  const v = verdictOf(r.verdict)
                  return (
                    <tr key={r.n}>
                      <td className="faint mono num">{r.n}</td>
                      <td style={{ maxWidth: 340 }}><div className="mono ellipsis" style={{ fontSize: 12 }}>{r.input_url}</div>{r.final_url && r.final_url !== r.input_url && <div className="mono faint ellipsis" style={{ fontSize: 12 }}>→ {r.final_url}</div>}{r.error && <div style={{ fontSize: 12, color: 'var(--orange)' }}>{r.error}</div>}</td>
                      <td><span className="score-n" style={{ color: scoreColor(r.score), fontSize: 14 }}>{r.score}</span></td>
                      <td><span className="row" style={{ gap: 8, whiteSpace: 'nowrap' }}><span className={`dot ${v.tone}`} style={{ width: 6, height: 6 }} />{lang === 'ar' ? v.ar : v.en}</span></td>
                      <td>{r.expected ? <span className="row" style={{ gap: 6 }}>{r.correct ? <CheckCircle2 size={14} strokeWidth={1.5} color="var(--green)" /> : <XCircle size={14} strokeWidth={1.5} color="var(--red)" />}<span className="faint">{r.expected}</span></span> : <span className="faint">–</span>}</td>
                      <td style={{ maxWidth: 420, fontSize: 13 }} className="muted">{r.reasons.slice(0, 2).join(' · ') || '–'}</td>
                      <td className="faint mono" style={{ fontSize: 12 }}>{r.engine}</td>
                      <td><button className="btn btn-sm" onClick={() => nav.investigate(r.input_url)}>{p('Open', 'فتح')}</button></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
