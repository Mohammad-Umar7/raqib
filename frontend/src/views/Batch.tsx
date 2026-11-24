import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CheckCircle2, Download, FileUp, FlaskConical, Globe2, Loader2, Play, ShieldCheck, Sparkles, Square, XCircle } from 'lucide-react'
import { api } from '../api'
import { Num, Rise, spring } from '../components/fx'
import { useLang } from '../i18n'
import { scoreColor, verdictOf } from '../meta'
import type { Nav } from './Investigation'

interface Row { n: number; input_url: string; final_url?: string; expected?: string | null; label: string; correct?: boolean | null; score: number; verdict: string; reasons: string[]; engine?: string; seconds?: number; error?: string | null; brand?: string | null; cloaking?: string | null }
interface Snap { id: string; total: number; done: number; finished: boolean; seconds: number; threshold: number; results: Row[]; metrics: any }

function Metric({ label, value, hint, color }: { label: string; value: number | null | undefined; hint: string; color: string }) {
  return (
    <div className="metric" style={{ ['--mc' as any]: color }}>
      <span>{label}</span>
      <b>{value == null ? '–' : <><Num value={Math.round(value * 1000) / 10} ms={700} />%</>}</b>
      <small>{hint}</small>
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

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <div className="eyebrow row"><FlaskConical size={13} /> {p('Detection accuracy', 'دقة الكشف')}</div>
          <h1>{p('Batch scan and evaluation', 'الفحص الجماعي والتقييم')}</h1>
          <p>{p('Paste a list of URLs (or a CSV with url,label). Raqib opens each one in the isolated browser, follows redirects and short links, checks for cloaking and scores it. With labels it reports precision, recall and F1.', 'الصق قائمة روابط (أو ملف CSV بعمودي url,label). يفتح رقيب كل رابط في المتصفح المعزول ويتتبع التحويلات والروابط المختصرة ويكشف الإخفاء ثم يقيّمه. ومع التصنيفات يحسب الدقة والاستدعاء وF1.')}</p>
        </div>
      </div>

      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.25fr) minmax(0,1fr)', alignItems: 'stretch' }}>
        <Rise>
          <div className="card" style={{ height: '100%' }}>
            <div className="card-h"><FileUp size={16} color="#e5b85c" /><h3>{p('URLs to scan', 'الروابط المطلوب فحصها')}</h3><span className="chip right">{count} {p('URLs', 'رابط')}</span></div>
            <div className="card-b col" style={{ gap: 12 }}>
              <textarea className="input mono batch-input" value={text} onChange={(e) => setText(e.target.value)} dir="ltr" spellCheck={false}
                placeholder={'url,label\nhttps://example-bank-verify.top/login,fraud\nhttps://www.rta.ae,legit\nbit.ly/xxxx'} />
              <div className="row wrap" style={{ gap: 8 }}>
                <span className="faint" style={{ fontSize: 12 }}>{p('Load a sample:', 'تحميل عينة:')}</span>
                <button className="btn btn-sm" onClick={() => sample('mixed')} disabled={!!loading}>{loading === 'mixed' ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />} {p('Demo cases + real UAE sites', 'حالات تجريبية + مواقع إماراتية حقيقية')}</button>
                <button className="btn btn-sm" onClick={() => sample('legit')} disabled={!!loading}>{loading === 'legit' ? <Loader2 size={13} className="spin" /> : <ShieldCheck size={13} />} {p('Real UAE sites only', 'مواقع إماراتية حقيقية فقط')}</button>
                <button className="btn btn-sm" onClick={() => sample('openphish')} disabled={!!loading}>{loading === 'openphish' ? <Loader2 size={13} className="spin" /> : <Globe2 size={13} />} {p('Live phishing (OpenPhish)', 'تصيّد حي (OpenPhish)')}</button>
                <button className="btn btn-sm btn-ghost" onClick={() => file.current?.click()}><FileUp size={13} /> {p('Upload file', 'رفع ملف')}</button>
                <input ref={file} type="file" accept=".txt,.csv,.tsv" hidden onChange={(e) => onFile(e.target.files?.[0])} />
              </div>
            </div>
          </div>
        </Rise>
        <Rise i={1}>
          <div className="card" style={{ height: '100%' }}>
            <div className="card-h"><Play size={16} color="#34d399" /><h3>{p('Run', 'تشغيل')}</h3></div>
            <div className="card-b col" style={{ gap: 14 }}>
              <label className="toggle"><input type="checkbox" checked={browser} onChange={(e) => setBrowser(e.target.checked)} /><span><b>{p('Isolated browser', 'المتصفح المعزول')}</b><small>{p('Renders JavaScript, takes screenshots. Off = fast HTTP-only scan.', 'يعرض JavaScript ويلتقط الصور. عند الإيقاف: فحص HTTP سريع فقط.')}</small></span></label>
              <label className="toggle"><input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} /><span><b>{p('Claude vision check', 'فحص بصري بـ Claude')}</b><small>{p('Looks at each screenshot for brand impersonation (needs an API key, slower).', 'يفحص كل لقطة بحثاً عن انتحال العلامات (يتطلب مفتاح API وأبطأ).')}</small></span></label>
              <div className="row wrap">
                {busy ? <button className="btn" onClick={stop}><Square size={14} /> {p('Stop', 'إيقاف')}</button>
                  : <button className="btn btn-primary" disabled={!count} onClick={start}><Play size={14} /> {p(`Scan ${count} URL(s)`, `فحص ${count} رابط`)}</button>}
                {snap && <>
                  <a className="btn btn-sm" href={`/api/batch/${snap.id}/results.csv`}><Download size={13} /> CSV</a>
                  <a className="btn btn-sm" href={`/api/batch/${snap.id}/results.json`}><Download size={13} /> JSON</a>
                </>}
              </div>
              {err && <div className="callout danger" style={{ padding: 10, fontSize: 12.5 }}>{err}</div>}
              {snap && (
                <div>
                  <div className="row between" style={{ fontSize: 12.5, marginBottom: 6 }}><span className="muted">{snap.finished ? p('Finished', 'اكتمل') : p('Scanning…', 'جارٍ الفحص…')}</span><span className="mono">{snap.done}/{snap.total} · {snap.seconds}s</span></div>
                  <div className="f-bar" style={{ height: 8 }}><motion.i animate={{ width: `${(snap.done / Math.max(1, snap.total)) * 100}%` }} style={{ background: 'linear-gradient(90deg,#e5b85c,#34d399)' }} /></div>
                </div>
              )}
              <div className="faint" style={{ fontSize: 11.5 }}>{p(`A URL counts as fraud when its score is ${snap?.threshold ?? 60} or more. Demo cases on fictional .test domains are scored from their recorded evidence.`, `يُعد الرابط احتيالياً عندما تبلغ درجته ${snap?.threshold ?? 60} أو أكثر. الحالات التجريبية على نطاقات .test الوهمية تُقيَّم من أدلتها المسجّلة.`)}</div>
            </div>
          </div>
        </Rise>
      </div>

      <AnimatePresence>
        {m && m.labelled > 0 && (
          <motion.div className="metrics-row" initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
            <Metric label={p('Precision', 'الدقة')} value={m.precision} hint={p('flagged URLs that really are scams', 'روابط مُعلَّمة وهي احتيالية فعلاً')} color="#e5b85c" />
            <Metric label={p('Recall', 'الاستدعاء')} value={m.recall} hint={p('scams that were caught', 'احتيالات تم كشفها')} color="#34d399" />
            <Metric label="F1" value={m.f1} hint={p('balance of both', 'توازن الاثنين')} color="#a78bfa" />
            <Metric label={p('False-positive rate', 'معدل الإنذار الكاذب')} value={m.false_positive_rate} hint={p('legitimate sites wrongly flagged', 'مواقع سليمة عُلّمت خطأً')} color="#fb4a6c" />
            <div className="confusion">
              <div className="cm-h" /><div className="cm-h">{p('Predicted fraud', 'متوقع: احتيال')}</div><div className="cm-h">{p('Predicted legit', 'متوقع: سليم')}</div>
              <div className="cm-h">{p('Actually fraud', 'فعلياً: احتيال')}</div><div className="cm good">{m.tp}<small>TP</small></div><div className="cm bad">{m.fn}<small>FN</small></div>
              <div className="cm-h">{p('Actually legit', 'فعلياً: سليم')}</div><div className="cm bad">{m.fp}<small>FP</small></div><div className="cm good">{m.tn}<small>TN</small></div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {snap && (
        <div className="card" style={{ marginTop: 18 }}>
          <div className="card-h"><FlaskConical size={16} color="#e5b85c" /><h3>{p('Results', 'النتائج')}</h3><span className="sub right">{rows.filter((r) => r.label === 'fraud').length} {p('flagged as fraud', 'مُعلَّم كاحتيال')}</span></div>
          <div style={{ overflow: 'auto', maxHeight: 640 }}>
            <table className="table batch-table">
              <thead><tr><th>#</th><th>URL</th><th>{p('Score', 'الدرجة')}</th><th>{p('Verdict', 'الحكم')}</th><th>{p('Expected', 'المتوقع')}</th><th>{p('Top reasons', 'أهم الأسباب')}</th><th>{p('Engine', 'المحرك')}</th><th /></tr></thead>
              <tbody>
                <AnimatePresence initial={false}>
                  {rows.map((r) => {
                    const v = verdictOf(r.verdict)
                    return (
                      <motion.tr key={r.n} initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }}>
                        <td className="faint mono">{r.n}</td>
                        <td style={{ maxWidth: 340 }}><div className="mono ellipsis" style={{ fontSize: 12 }}>{r.input_url}</div>{r.final_url && r.final_url !== r.input_url && <div className="mono faint ellipsis" style={{ fontSize: 11 }}>→ {r.final_url}</div>}{r.error && <div className="faint" style={{ fontSize: 11, color: '#ffb37d' }}>{r.error}</div>}</td>
                        <td><b style={{ color: scoreColor(r.score), fontSize: 16 }}>{r.score}</b></td>
                        <td><span className={`chip ${v.tone}`}>{lang === 'ar' ? v.ar : v.en}</span></td>
                        <td>{r.expected ? <span className="row" style={{ gap: 5 }}>{r.correct ? <CheckCircle2 size={15} color="#34d399" /> : <XCircle size={15} color="#fb4a6c" />}<span className="faint">{r.expected}</span></span> : <span className="faint">–</span>}</td>
                        <td style={{ maxWidth: 420, fontSize: 12 }} className="muted">{r.reasons.slice(0, 2).join(' · ') || '–'}</td>
                        <td><span className="chip">{r.engine}</span></td>
                        <td><button className="btn btn-sm" onClick={() => nav.investigate(r.input_url)}>{p('Open', 'فتح')}</button></td>
                      </motion.tr>
                    )
                  })}
                </AnimatePresence>
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}

