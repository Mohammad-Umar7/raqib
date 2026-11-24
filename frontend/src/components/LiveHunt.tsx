import { useEffect, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { ArrowRight, Globe2, Loader2, MapPin, Radio, Search, Sparkles } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import { scoreColor } from '../meta'
import { Num, spring } from './fx'

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
    <div className="card live-hunt">
      <div className="card-h">
        <Radio size={16} color="#34d399" />
        <h3>{p('Live hunt · real-world feeds', 'رصد مباشر · مصادر حقيقية')}</h3>
        <span className="sub">{p('not the demo dataset', 'ليست البيانات التجريبية')}</span>
      </div>
      <div className="card-b">
        <div className="lh-sources">
          <div className="lh-src on">
            <Globe2 size={18} />
            <div className="grow">
              <b>{p('Newly registered domains', 'النطاقات المسجّلة حديثاً')}</b>
              <small>{p('~70,000 new domains a day checked for 36 protected UAE brands', 'نحو 70,000 نطاق جديد يومياً يُفحص بحثاً عن 36 علامة إماراتية محمية')}</small>
            </div>
            <div className="seg">{[1, 2, 3].map((d) => <button key={d} className={days === d ? 'on' : ''} onClick={() => setDays(d)}>{d}{p('d', 'ي')}</button>)}</div>
            <button className="btn btn-primary btn-sm" onClick={runNrd} disabled={busy === 'nrd'}>{busy === 'nrd' ? <Loader2 size={13} className="spin" /> : <Sparkles size={13} />} {p('Hunt now', 'ابدأ')}</button>
          </div>
          <div className={`lh-src ${serp?.available ? 'on' : 'off'}`}>
            <Search size={18} />
            <div className="grow">
              <b>{p('Google Search, ads & Maps', 'بحث جوجل والإعلانات والخرائط')}</b>
              <small>{serp?.available ? p(`${serp.rows?.length ?? 0} live results triaged`, `${serp.rows?.length ?? 0} نتيجة حية تم فرزها`) : p('Connect a SerpAPI key (SERPAPI_KEY) to hunt live; the recorded feed powers the radar meanwhile.', 'اربط مفتاح SerpAPI للرصد المباشر؛ يعمل الرادار حالياً على المصدر المسجّل.')}</small>
            </div>
            <MapPin size={16} className="faint" />
          </div>
        </div>
        {err && <div className="callout danger" style={{ padding: 10, marginTop: 10, fontSize: 12.5 }}>{err}</div>}
        <AnimatePresence>
          {nrd && (
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={spring}>
              <div className="lh-stats">
                <span><b><Num value={nrd.scanned} ms={900} /></b> {p('domains checked', 'نطاق تم فحصه')}</span>
                <span><b><Num value={nrd.total} ms={700} /></b> {p('mention a protected brand', 'تذكر علامة محمية')}</span>
                <span className="hot"><b><Num value={nrd.flagged} ms={700} /></b> {p('flagged for investigation', 'مُعلَّمة للتحقيق')}</span>
                <label className="row faint" style={{ gap: 6, fontSize: 12, marginInlineStart: 'auto' }}><input type="checkbox" checked={onlyFlagged} onChange={(e) => setOnlyFlagged(e.target.checked)} /> {p('flagged only', 'المُعلَّمة فقط')}</label>
              </div>
              <div className="lh-list">
                {rows.slice(0, 40).map((r, i) => (
                  <motion.div key={r.id} className="lh-row" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: Math.min(i, 15) * 0.03 }}>
                    <b className="lh-score" style={{ color: scoreColor(r.triage.score), borderColor: scoreColor(r.triage.score) }}>{r.triage.score}</b>
                    <div style={{ minWidth: 0 }}>
                      <div className="mono ellipsis" style={{ fontSize: 12.5, fontWeight: 600 }}>{r.host}</div>
                      <div className="faint ellipsis" style={{ fontSize: 11.5 }}>{r.detail} · {r.triage.reasons.slice(0, 1).map((x) => x.text).join('')}</div>
                    </div>
                    <button className="btn btn-sm" onClick={() => onScan(r.host)}>{p('Scan now', 'افحص الآن')} <ArrowRight size={12} /></button>
                  </motion.div>
                ))}
                {!rows.length && <div className="muted" style={{ padding: 12 }}>{p('No brand look-alikes above the threshold in this window.', 'لا توجد نطاقات مشابهة فوق الحد في هذه الفترة.')}</div>}
              </div>
              <div className="faint" style={{ fontSize: 11, marginTop: 8 }}>{p('Source: WhoisDS daily newly-registered-domain list. Fetched', 'المصدر: قائمة WhoisDS اليومية للنطاقات الجديدة. جُلبت')} {nrd.fetched_at?.slice(0, 16).replace('T', ' ')} UTC{nrd.cached ? ' · cached' : ''}</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
