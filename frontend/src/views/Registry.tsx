import { useEffect, useMemo, useState } from 'react'
import { Search, ShieldCheck } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import { scoreColor } from '../meta'
import type { Entity } from '../types'

const SECTOR: Record<string, [string, string]> = {
  toll: ['Toll', 'رسوم طرق'], government: ['Government', 'حكومي'], courier: ['Courier', 'شحن'], bank: ['Bank', 'بنك'], telecom: ['Telecom', 'اتصالات'], utility: ['Utility', 'مرافق'],
  regulator: ['Regulator', 'جهة رقابية'], travel: ['Travel', 'سفر'], retail: ['Retail', 'تجزئة'], mobility: ['Mobility', 'تنقل'],
}

export function Registry() {
  const { p, lang } = useLang()
  const [items, setItems] = useState<Entity[]>([])
  const [q, setQ] = useState('')
  const [host, setHost] = useState('')
  const [res, setRes] = useState<{ score: number; reasons: { text: string; points: number }[]; brand: string | null } | null>(null)

  useEffect(() => { api.registry().then((r) => setItems(r.entities)) }, [])
  const shown = useMemo(() => items.filter((e) => (e.name + e.name_ar + e.domains.join(' ') + e.sector).toLowerCase().includes(q.toLowerCase())), [items, q])
  const check = async (e: React.FormEvent) => { e.preventDefault(); if (host.trim()) setRes(await api.triage(host.trim())) }

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <h1>{p('Protected entities', 'الجهات المحمية')}</h1>
          <p>{p('The UAE organisations scammers pretend to be. A page that names one of them on a domain that is not in its official list is flagged. Domains below should be verified with each organisation before operational use.', 'الجهات الإماراتية التي ينتحل المحتالون صفتها. تُعلَّم أي صفحة تذكر إحداها على نطاق ليس ضمن قائمتها الرسمية. يجب التحقق من النطاقات مع كل جهة قبل الاستخدام التشغيلي.')}</p>
        </div>
      </div>
      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,2fr) minmax(0,1fr)', alignItems: 'start' }}>
        <div className="card">
          <div className="card-h"><ShieldCheck size={16} color="#34d399" /><h3>{items.length} {p('entities', 'جهة')}</h3>
            <input className="input right" style={{ maxWidth: 260, padding: '6px 10px' }} placeholder={p('Filter…', 'تصفية…')} value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <div style={{ maxHeight: 640, overflow: 'auto' }}>
            <table className="table">
              <thead><tr><th>{p('Entity', 'الجهة')}</th><th>{p('Sector', 'القطاع')}</th><th>{p('Official domains', 'النطاقات الرسمية')}</th></tr></thead>
              <tbody>
                {shown.map((e) => (
                  <tr key={e.id}>
                    <td><b>{lang === 'ar' ? e.name_ar : e.name}</b><div className="faint" style={{ fontSize: 12 }}>{lang === 'ar' ? e.name : e.name_ar}</div></td>
                    <td><span className="chip">{lang === 'ar' ? SECTOR[e.sector]?.[1] ?? e.sector : SECTOR[e.sector]?.[0] ?? e.sector}</span></td>
                    <td className="mono" style={{ fontSize: 12 }}>{e.domains.join(', ')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <div className="card">
          <div className="card-h"><Search size={16} color="#e5b85c" /><h3>{p('Check a domain', 'فحص نطاق')}</h3></div>
          <div className="card-b">
            <form className="row" onSubmit={check}>
              <input className="input mono" value={host} onChange={(e) => setHost(e.target.value)} placeholder="salik-topup-ae.com" dir="ltr" />
              <button className="btn btn-primary">{p('Check', 'فحص')}</button>
            </form>
            {res && (
              <div className="col" style={{ marginTop: 14, gap: 8 }}>
                <div className="row"><b style={{ fontSize: 30, color: scoreColor(res.score) }}>{res.score}</b><span className="muted">/ 100 {p('triage score', 'درجة الفرز')}</span>{res.brand && <span className="chip danger right">{p('imitates', 'ينتحل')} {items.find((i) => i.id === res.brand)?.name}</span>}</div>
                {res.reasons.map((r, i) => <div key={i} className="sig" style={{ gridTemplateColumns: '1fr auto' }}><p>{r.text}</p><span className="w">+{r.points}</span></div>)}
                {!res.reasons.length && <div className="muted">{p('No look-alike or lure signals in this domain name.', 'لا مؤشرات تشابه أو استدراج في اسم النطاق.')}</div>}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
