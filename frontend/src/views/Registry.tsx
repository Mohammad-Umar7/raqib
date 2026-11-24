import { useEffect, useMemo, useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import { api } from '../api'
import { useLang } from '../i18n'
import type { Entity } from '../types'

const SECTOR: Record<string, [string, string]> = {
  toll: ['Toll', 'رسوم طرق'], government: ['Government', 'حكومي'], courier: ['Courier', 'شحن'], bank: ['Bank', 'بنك'], telecom: ['Telecom', 'اتصالات'], utility: ['Utility', 'مرافق'],
  regulator: ['Regulator', 'جهة رقابية'], travel: ['Travel', 'سفر'], retail: ['Retail', 'تجزئة'], mobility: ['Mobility', 'تنقل'],
}

export function Registry() {
  const { p, lang } = useLang()
  const [items, setItems] = useState<Entity[]>([])
  const [q, setQ] = useState('')

  useEffect(() => { api.registry().then((r) => setItems(r.entities)) }, [])
  const shown = useMemo(() => items.filter((e) => (e.name + e.name_ar + e.domains.join(' ') + e.sector).toLowerCase().includes(q.toLowerCase())), [items, q])

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <h1>{p('Protected entities', 'الجهات المحمية')}</h1>
          <p>{p('The UAE organisations scammers pretend to be. A page that names one of them on a domain that is not in its official list is flagged. Domains below should be verified with each organisation before operational use.', 'الجهات الإماراتية التي ينتحل المحتالون صفتها. تُعلَّم أي صفحة تذكر إحداها على نطاق ليس ضمن قائمتها الرسمية. يجب التحقق من النطاقات مع كل جهة قبل الاستخدام التشغيلي.')}</p>
        </div>
      </div>
      <div>
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
      </div>
    </div>
  )
}
