import { FileBadge2, Globe2, Play, Search } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import { ago } from '../meta'
import type { RadarSnap } from '../types'

/** The radar's three always-on sensors: what each one watched, when it runs next, what went wrong. */
export function RadarStatus({ snap, onChange }: { snap: RadarSnap | null; onChange: (s: RadarSnap) => void }) {
  const { p, lang } = useLang()
  const n = (v: number) => v.toLocaleString(lang === 'ar' ? 'ar-AE' : 'en-US')
  const by = Object.fromEntries((snap?.sensors ?? []).map((s) => [s.key, s]))
  const rows = [
    { key: 'ct', icon: <FileBadge2 size={16} strokeWidth={1.5} />, title: p('Certificate logs', 'سجلات الشهادات'),
      line: by.ct ? `${n(by.ct.seen)} ${p('new HTTPS certificates read', 'شهادة HTTPS جديدة قُرئت')}${by.ct.coverage ? ` (${Math.round(by.ct.coverage * 100)}% ${p('of all issued while watching', 'من كل ما صدر أثناء المراقبة')})` : ''} · ${by.ct.flagged} ${p('flagged', 'مشتبه')}` : '', sub: by.ct?.note, run: false },
    { key: 'nrd', icon: <Globe2 size={16} strokeWidth={1.5} />, title: p('Newly registered domains', 'النطاقات المسجّلة حديثاً'),
      line: by.nrd ? `${n(by.nrd.seen)} ${p('domains in the latest daily lists', 'نطاق في أحدث القوائم اليومية')} · ${by.nrd.flagged} ${p('flagged', 'مشتبه')}` : '', sub: by.nrd ? `${p('Every 6 hours', 'كل 6 ساعات')} · ${p('next', 'التالي')} ${ago(by.nrd.next_run, p)}` : '', run: true },
    { key: 'serp', icon: <Search size={16} strokeWidth={1.5} />, title: p('Google Search, ads and Maps', 'بحث جوجل والإعلانات والخرائط'),
      line: by.serp?.on ? `${n(by.serp.seen)} ${p('results triaged', 'نتيجة تم فرزها')} · ${by.serp.flagged} ${p('flagged', 'مشتبه')}` : p('Not connected', 'غير متصل'), sub: by.serp?.note, run: !!by.serp?.on },
  ]
  return (
    <div className="card">
      <div className="card-h">
        <h3>{p('Always-on sensors', 'مستشعرات تعمل دائماً')}</h3>
        <span className="sub">{snap && !snap.started ? p('Off · start the server with RAQIB_RADAR=1 inside a VM or sandbox', 'متوقف · شغّل الخادم مع RAQIB_RADAR=1 داخل جهاز افتراضي أو بيئة معزولة') : snap?.paused ? p('Paused', 'متوقف') : p('No one has to paste a link', 'لا حاجة للصق أي رابط')}</span>
        <span className="right faint num" style={{ fontSize: 12 }}>{snap ? `${snap.scans_last_hour}/${snap.cap} ${p('sandbox scans this hour', 'فحص معزول هذه الساعة')}` : ''}</span>
      </div>
      <div className="rs-grid">
        {rows.map((r) => {
          const s = by[r.key]
          const live = s && s.on && !s.error && !snap?.paused
          return (
            <div key={r.key} className="lh-src">
              {r.icon}
              <div className="grow" style={{ minWidth: 0 }}>
                <b>{r.title}</b>
                <small>{r.line}</small>
                <small className="faint ellipsis" title={s?.error ?? r.sub ?? ''}>{s?.error ? `${p('Error', 'خطأ')}: ${s.error}` : r.sub}</small>
              </div>
              <span className="lh-state"><span className={`dot ${live ? 'live' : s?.error ? 'warn' : ''}`} style={{ width: 6, height: 6 }} />{live ? p('Live', 'مباشر') : s?.error ? p('Retrying', 'إعادة المحاولة') : p('Off', 'متوقف')}</span>
              {r.run && <button className="btn btn-sm" onClick={async () => onChange(await api.radarControl({ run: r.key }))} title={p('Run now', 'شغّل الآن')}><Play size={12} className="flip-rtl" /></button>}
            </div>
          )
        })}
      </div>
    </div>
  )
}
