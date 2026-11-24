import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Globe2, Loader2, Play, Search } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import { scoreColor } from '../meta'
import { Num, soft } from './fx'

interface Row { id: string; host: string; when: string; detail: string; source: string; title: string; url: string; triage: { score: number; reasons: { text: string; points: number }[] } }

export function LiveHunt({ onScan }: { onScan: (url: string) => void }) {
  const { p } = useLang()
  const [nrd, setNrd] = useState<any>(null)
  const [serp, setSerp] = useState<any>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)
  const [days, setDays] = useState(2)
  const [onlyFlagged, setOnlyFlagged] = useState(true)

  useEffect(() => { api.searchMaps().then(setSerp).catch(() => {}) }, [])

  const runNrd = async () => {
    setBusy('nrd'); setErr(null)
    try { setNrd(await api.newDomains(days)) } catch (e: any) { setErr(e.message) } finally { setBusy(null) }
  }
  const rows: Row[] = (nrd?.rows ?? []).filter((r: Row) => !onlyFlagged || r.triage.score >= 40)

  return (
    <div className="card">
      <div className="card-h">
        <h3>{p('Live hunt on real-world feeds', 'رصد مباشر على مصادر حقيقية')}</h3>
        <span className="sub">{p('Not the demo dataset', 'ليست البيانات التجريبية')}</span>
      </div>
      <div className="grid-2" style={{ gap: 0 }}>
        <div className="lh-src">
          <Globe2 size={16} strokeWidth={1.5} />
          <div className="grow">
            <b>{p('Newly registered domains', 'النطاقات المسجّلة حديثاً')}</b>
            <small>{p('About 70,000 new domains a day, checked for 36 protected UAE brands', 'نحو 70,000 نطاق جديد يومياً يُفحص بحثاً عن 36 علامة إماراتية محمية')}</small>
          </div>
          <div className="seg" role="group" aria-label={p('Days', 'الأيام')}>{[1, 2, 3].map((d) => <button key={d} className={days === d ? 'on' : ''} onClick={() => setDays(d)}>{d}{p('d', 'ي')}</button>)}</div>
          <button className="btn" onClick={runNrd} disabled={busy === 'nrd'}>{busy === 'nrd' ? <Loader2 size={14} className="spin" /> : <Play size={14} strokeWidth={1.5} className="flip-rtl" />} {p('Hunt now', 'ابدأ')}</button>
        </div>
        <div className="lh-src" style={{ borderInlineStart: '1px solid var(--line)' }}>
          <Search size={16} strokeWidth={1.5} />
          <div className="grow">
            <b>{p('Google Search, ads and Maps', 'بحث جوجل والإعلانات والخرائط')}</b>
            <small>{serp?.available ? p(`${serp.rows?.length ?? 0} live results triaged`, `${serp.rows?.length ?? 0} نتيجة حية تم فرزها`) : p('Add a SerpAPI key (SERPAPI_KEY) to hunt live. The radar uses the recorded feed meanwhile.', 'أضف مفتاح SerpAPI للرصد المباشر. يعمل الرادار حالياً على المصدر المسجّل.')}</small>
          </div>
          <span className="lh-state"><span className={`dot ${serp?.available ? 'ok' : ''}`} style={{ width: 6, height: 6 }} />{serp?.available ? p('Live', 'مباشر') : p('Not connected', 'غير متصل')}</span>
        </div>
      </div>
      {err && <div className="callout danger" style={{ borderTop: '1px solid var(--line)' }}><p>{err}</p></div>}
      <AnimatePresence>
        {nrd && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={soft}>
            <div className="lh-stats">
              <span><b><Num value={nrd.scanned} ms={900} /></b> {p('domains checked', 'نطاق تم فحصه')}</span>
              <span><b><Num value={nrd.total} ms={700} /></b> {p('mention a protected brand', 'تذكر علامة محمية')}</span>
              <span className="hot"><b><Num value={nrd.flagged} ms={700} /></b> {p('flagged for investigation', 'مُعلَّمة للتحقيق')}</span>
              <label className="row faint" style={{ fontSize: 13, marginInlineStart: 'auto' }}><input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} style={{ accentColor: 'var(--accent)' }} /> {p('Flagged only', 'المُعلَّمة فقط')}</label>
            </div>
            <div className="lh-list">
              {rows.slice(0, 40).map((r) => (
                <div key={r.id} className="lh-row">
                  <span className="score-n" style={{ color: scoreColor(r.triage.score), fontSize: 14 }}>{r.triage.score}</span>
                  <div style={{ minWidth: 0 }}>
                    <div className="mono ellipsis" style={{ fontSize: 13 }}>{r.host}</div>
                    <div className="faint ellipsis" style={{ fontSize: 12 }}>{r.detail} · {r.triage.reasons.slice(0, 1).map((x) => x.text).join('')}</div>
                  </div>
                  <button className="btn btn-sm" onClick={() => onScan(r.host)}>{p('Scan', 'افحص')} <ArrowRight size={14} className="flip-rtl" /></button>
                </div>
              ))}
              {!rows.length && <div className="empty">{p('No brand look-alikes above the threshold in this window', 'لا توجد نطاقات مشابهة فوق الحد في هذه الفترة')}</div>}
            </div>
            <div className="lh-foot">{p('Source: WhoisDS daily newly registered domain list, fetched', 'المصدر: قائمة WhoisDS اليومية للنطاقات الجديدة، جُلبت')} {nrd.fetched_at?.slice(0, 16).replace('T', ' ')} UTC{nrd.cached ? ' · cached' : ''}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
