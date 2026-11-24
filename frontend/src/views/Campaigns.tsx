import { useEffect, useMemo, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { api } from '../api'
import { Graph } from '../components/Graph'
import { useLang } from '../i18n'
import { SCAM_TYPES, STRENGTH, cap, scoreColor, verdictOf } from '../meta'
import type { Cluster, GEdge, GNode } from '../types'
import type { Nav } from './Investigation'

export function Campaigns({ nav }: { nav: Nav }) {
  const { p, lang } = useLang()
  const [g, setG] = useState<{ nodes: GNode[]; edges: GEdge[]; cluster_of: Record<string, string> } | null>(null)
  const [clusters, setClusters] = useState<Cluster[]>([])
  const [filter, setFilter] = useState<string | null>(null)
  const [weak, setWeak] = useState(true)
  const [node, setNode] = useState<string | null>(null)
  const [edge, setEdge] = useState<GEdge | null>(null)

  useEffect(() => { api.graph().then(setG); api.campaigns().then((r) => setClusters(r.clusters)) }, [])

  const view = useMemo(() => {
    if (!g) return { nodes: [] as GNode[], edges: [] as GEdge[] }
    const keep = (n: GNode) => !filter ? true : g.cluster_of[n.case_id] === filter
    const nodes = g.nodes.filter((n) => keep(n) && (filter || g.cluster_of[n.case_id] || g.edges.some((e) => e.source === n.case_id || e.target === n.case_id)))
    const ids = new Set(nodes.map((n) => n.case_id))
    return { nodes, edges: g.edges.filter((e) => ids.has(e.source) && ids.has(e.target)) }
  }, [g, filter])

  const sel = g?.nodes.find((n) => n.case_id === node)
  const selEdges = g?.edges.filter((e) => node && (e.source === node || e.target === node)) ?? []
  const host = (id: string) => g?.nodes.find((n) => n.case_id === id)?.host ?? id
  const typeName = (k: string) => (SCAM_TYPES[k] ? (lang === 'ar' ? SCAM_TYPES[k].ar : SCAM_TYPES[k].en) : k)

  return (
    <div className="page">
      <div className="page-h">
        <div className="grow">
          <h1>{p('Scam campaigns', 'حملات الاحتيال')}</h1>
          <p>{p('Sites are linked when they share the operator’s own tooling or contact details. Look-alike pages alone are shown as weak links, because two operators can copy the same brand.', 'تُربط المواقع عندما تشترك في أدوات المحتال أو بيانات اتصاله. التشابه الشكلي وحده رابط ضعيف لأن محتالَين قد ينسخان العلامة التجارية نفسها.')}</p>
        </div>
        <label className="row muted" style={{ fontSize: 13 }}><input type="checkbox" checked={weak} onChange={(e) => setWeak(e.target.checked)} style={{ accentColor: 'var(--accent)' }} /> {p('Show weak links', 'إظهار الروابط الضعيفة')}</label>
      </div>
      <div className="filters" role="group" aria-label={p('Campaign filter', 'تصفية الحملات')}>
        <button className={filter === null ? 'on' : ''} onClick={() => setFilter(null)}>{p('All campaigns', 'كل الحملات')}</button>
        {clusters.map((c) => (
          <button key={c.cluster_id} className={filter === c.cluster_id ? 'on' : ''} onClick={() => { setFilter(filter === c.cluster_id ? null : c.cluster_id); setNode(null); setEdge(null) }}>
            <span className="mono">{c.cluster_id}</span> {typeName(c.headline)} <span className="faint num">{c.size}</span>
          </button>
        ))}
      </div>
      <div className="grid-2" style={{ gridTemplateColumns: 'minmax(0,1.9fr) minmax(0,1fr)' }}>
        <div className="card">
          <div className="card-h"><h3>{p('Campaign map', 'خريطة الحملات')}</h3><span className="sub num">{view.nodes.length} {p('items', 'عنصراً')} · {view.edges.length} {p('links', 'رابطاً')}</span></div>
          {g && <Graph nodes={view.nodes} edges={view.edges} width={1000} height={640} labels={!!filter || view.nodes.length < 14} showWeak={weak} clusterOf={g.cluster_of} selectedNode={node} selectedEdge={edge ? `${edge.source}|${edge.target}` : null}
            onNode={(id) => { setNode(id); setEdge(null) }} onEdge={(e) => { setEdge(e); setNode(null) }} />}
        </div>
        <div className="col" style={{ gap: 16 }}>
          <div className="card">
            <div className="card-h"><h3>{edge ? p('Why these are linked', 'سبب الربط') : sel ? p('Selected site', 'الموقع المحدد') : p('Details', 'التفاصيل')}</h3></div>
            {edge && (
              <>
                <div className="card-b mono" style={{ fontSize: 12, paddingBottom: 12 }}>{host(edge.source)} <span className="faint">↔</span> {host(edge.target)}</div>
                <div className="list" style={{ borderTop: '1px solid var(--line)' }}>
                  {edge.reasons.map((r, i) => (
                    <div key={i} className="sig" style={{ gridTemplateColumns: '8px minmax(0,1fr)' }}>
                      <span className="dot" style={{ background: STRENGTH[r.strength].color, marginTop: 6 }} />
                      <div><p>{lang === 'ar' ? r.text_ar : r.text}</p><small>{lang === 'ar' ? STRENGTH[r.strength].ar : STRENGTH[r.strength].en} · {cap(r.kind)}</small></div>
                    </div>
                  ))}
                </div>
              </>
            )}
            {sel && !edge && (
              <div className="card-b col" style={{ gap: 12 }}>
                <div className="mono" style={{ wordBreak: 'break-all', fontSize: 13 }}>{sel.kind === 'maps_listing' ? sel.label : sel.host}</div>
                <div className="row wrap">
                  <span className={`chip ${verdictOf(sel.verdict).tone}`}>{lang === 'ar' ? verdictOf(sel.verdict).ar : verdictOf(sel.verdict).en}</span>
                  <span className="chip"><span className="num" style={{ color: scoreColor(sel.score) }}>{sel.score}</span>/ 100</span>
                  {sel.scam_type && SCAM_TYPES[sel.scam_type] && <span className="chip">{typeName(sel.scam_type)}</span>}
                  {sel.kind === 'site' && <span className={`chip ${sel.on_blocklist ? '' : 'warn'}`}>{sel.on_blocklist ? p('On a public blocklist', 'مدرج في قائمة حجب') : p('Not blocklisted', 'غير محجوب')}</span>}
                </div>
                <div className="muted" style={{ fontSize: 13 }}><span className="num">{selEdges.length}</span> {p('links', 'رابطاً')}, <span className="num">{selEdges.filter((e) => e.strength === 'strong').length}</span> {p('strong', 'قوي')}</div>
                {sel.kind === 'site' && <button className="btn btn-primary" style={{ alignSelf: 'flex-start' }} onClick={() => nav.investigate('case:' + sel.case_id)}>{p('Investigate this site', 'التحقيق في هذا الموقع')} <ArrowRight size={14} className="flip-rtl" /></button>}
              </div>
            )}
            {!edge && !sel && <div className="card-b muted">{p('Click a site to see its details, or a line to see why two sites are linked', 'اضغط على موقع لعرض تفاصيله أو على خط لمعرفة سبب الربط')}</div>}
          </div>
          <div className="card list">
            {clusters.filter((c) => !filter || c.cluster_id === filter).map((c) => (
              <div key={c.cluster_id} className="list-row col" style={{ gap: 4 }}>
                <div className="row"><span className="tag-id">{c.cluster_id}</span><b style={{ fontWeight: 500 }}>{typeName(c.headline)}</b>{c.unblocked > 0 && <span className="right row" style={{ gap: 6, fontSize: 12, color: 'var(--text-2)' }}><span className="dot danger" style={{ width: 6, height: 6 }} /><span className="num">{c.unblocked}</span> {p('not blocklisted', 'غير محجوب')}</span>}</div>
                <div className="faint mono ellipsis" style={{ fontSize: 12 }}>{c.shared_indicators.join(' · ')}</div>
                <div className="muted" style={{ fontSize: 13 }}>{c.sites.map((s) => (s.kind === 'maps_listing' ? s.label : s.host)).join(', ')}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
