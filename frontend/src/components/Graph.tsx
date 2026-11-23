import { useEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { forceCollide, forceLink, forceManyBody, forceRadial, forceSimulation, forceX, forceY, type Simulation } from 'd3-force'
import { useLang } from '../i18n'
import { REASON_SHORT, SCAM_TYPES, STRENGTH, scoreColor, verdictOf } from '../meta'
import type { GEdge, GNode } from '../types'

interface SimNode extends GNode { id: string; x: number; y: number; vx?: number; vy?: number; fx?: number | null; fy?: number | null }

interface Props {
  nodes: GNode[]
  edges: GEdge[]
  width?: number
  height?: number
  selectedNode?: string | null
  selectedEdge?: string | null
  onNode?: (id: string) => void
  onEdge?: (e: GEdge) => void
  labels?: boolean
  showWeak?: boolean
  clusterOf?: Record<string, string>
}

const ekey = (e: GEdge) => `${e.source}|${e.target}`
const short = (host: string, n = 26) => (host.length > n ? host.slice(0, n - 1) + '…' : host)

export function Graph({ nodes, edges, width = 900, height = 520, selectedNode, selectedEdge, onNode, onEdge, labels = true, showWeak = true, clusterOf }: Props) {
  const { p, lang } = useLang()
  const boxRef = useRef<HTMLDivElement>(null)
  const svgRef = useRef<SVGSVGElement>(null)
  const simRef = useRef<Simulation<SimNode, undefined> | null>(null)
  const nodeMap = useRef(new Map<string, SimNode>())
  const [, setTick] = useState(0)
  const [hover, setHover] = useState<string | null>(null)
  const drag = useRef<{ id: string; moved: boolean } | null>(null)

  const visibleEdges = useMemo(() => edges.filter((e) => showWeak || e.strength !== 'weak'), [edges, showWeak])

  useEffect(() => {
    const map = nodeMap.current
    const ids = new Set(nodes.map((n) => n.case_id))
    for (const k of [...map.keys()]) if (!ids.has(k)) map.delete(k)
    const centre0 = nodes.find((n) => n.center)
    nodes.forEach((n, i) => {
      const prev = map.get(n.case_id)
      if (prev) Object.assign(prev, n)
      else {
        const ang = (i / Math.max(nodes.length, 1)) * Math.PI * 2 + 0.4
        const o = map.get(centre0?.case_id ?? '')
        map.set(n.case_id, { ...n, id: n.case_id, x: (o?.x ?? width / 2) + Math.cos(ang) * 14, y: (o?.y ?? height / 2) + Math.sin(ang) * 14 })
      }
    })
    const list = [...map.values()]
    const centre = list.find((n) => n.center)
    if (centre) { centre.fx = width / 2; centre.fy = height / 2 }
    const centreId = centre?.case_id
    const ring: Record<string, number> = {}
    const R = Math.min(width, height) / 2 - 40
    if (centreId) {
      for (const e of visibleEdges) {
        if (e.source === centreId || e.target === centreId) {
          const other = e.source === centreId ? e.target : e.source
          ring[other] = e.strength === 'strong' ? R * 0.8 : e.strength === 'medium' ? R * 0.92 : R
        }
      }
    }
    const links = visibleEdges.filter((e) => map.has(e.source) && map.has(e.target) && (!centreId || e.source === centreId || e.target === centreId))
      .map((e) => ({ source: e.source, target: e.target, strength: e.strength }))
    simRef.current?.stop()
    const sim = forceSimulation<SimNode>(list)
      .force('link', forceLink<SimNode, any>(links).id((d) => d.id).distance((l: any) => (l.strength === 'strong' ? 190 : l.strength === 'medium' ? 230 : 290)).strength((l: any) => (l.strength === 'weak' ? 0.08 : 0.5)))
      .force('charge', forceManyBody().strength(centre ? -420 : -1300))
      .force('x', forceX(width / 2).strength(centre ? 0.02 : 0.06))
      .force('y', forceY(height / 2).strength(centre ? 0.02 : 0.08))
      .force('collide', forceCollide(42))
      .force('radial', centre ? forceRadial<SimNode>((n) => (n.center ? 0 : ring[n.case_id] ?? R), width / 2, height / 2).strength(0.9) : null)
      .alpha(0.85).alphaDecay(0.03)
    let raf = 0
    sim.on('tick', () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(() => setTick((t) => t + 1)) })
    simRef.current = sim
    return () => { sim.stop(); cancelAnimationFrame(raf) }
  }, [nodes.map((n) => n.case_id).join(','), visibleEdges.length, width, height])

  const pos = (id: string) => nodeMap.current.get(id)
  const toSvg = (ev: React.PointerEvent) => {
    const r = svgRef.current!.getBoundingClientRect()
    return { x: ((ev.clientX - r.left) / r.width) * width, y: ((ev.clientY - r.top) / r.height) * height }
  }
  const onDown = (id: string) => (ev: React.PointerEvent) => {
    (ev.target as Element).setPointerCapture?.(ev.pointerId)
    drag.current = { id, moved: false }
    simRef.current?.alphaTarget(0.2).restart()
  }
  const onMove = (ev: React.PointerEvent) => {
    if (!drag.current) return
    const n = pos(drag.current.id)
    if (!n) return
    const { x, y } = toSvg(ev)
    drag.current.moved = true
    n.fx = x; n.fy = y
  }
  const onUp = () => {
    if (!drag.current) return
    const n = pos(drag.current.id)
    if (n && !n.center) { n.fx = null; n.fy = null }
    drag.current = null
    simRef.current?.alphaTarget(0)
  }

  const centreId = nodes.find((n) => n.center)?.case_id
  const active = hover ?? selectedNode ?? null
  const touches = (e: GEdge) => !active || e.source === active || e.target === active
  const hovered = hover ? pos(hover) : null

  const halos = useMemo(() => {
    if (!clusterOf) return []
    const groups = new Map<string, SimNode[]>()
    for (const n of nodeMap.current.values()) {
      const c = clusterOf[n.case_id]
      if (c) groups.set(c, [...(groups.get(c) ?? []), n])
    }
    return [...groups.entries()].filter(([, v]) => v.length > 1).map(([c, v]) => {
      const cx = v.reduce((a, n) => a + n.x, 0) / v.length, cy = v.reduce((a, n) => a + n.y, 0) / v.length
      const r = Math.max(...v.map((n) => Math.hypot(n.x - cx, n.y - cy))) + 46
      return { c, cx, cy, r }
    })
  }, [clusterOf, nodes.length, Math.round((simRef.current?.alpha() ?? 0) * 20)])

  return (
    <div className="graph-box" dir="ltr" ref={boxRef}>
      <svg ref={svgRef} viewBox={`0 0 ${width} ${height}`} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={onUp} style={{ touchAction: 'none' }}>
        <defs>
          <filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
          <radialGradient id="nodeFill"><stop offset="0" stopColor="#1a2850" /><stop offset="1" stopColor="#0d1530" /></radialGradient>
        </defs>
        {centreId && pos(centreId) && [1, 2, 3].map((k) => (
          <circle key={k} cx={width / 2} cy={height / 2} r={(Math.min(width, height) / 2 - 40) * (0.4 + k * 0.2)} fill="none" stroke="#1b2a4d" strokeDasharray="2 7" opacity="0.6" />
        ))}
        {halos.map((h) => (
          <g key={h.c}>
            <circle cx={h.cx} cy={h.cy} r={h.r} fill="rgba(99,102,241,0.06)" stroke="rgba(129,140,248,0.28)" strokeDasharray="4 6" />
            <text x={h.cx} y={h.cy - h.r - 6} textAnchor="middle" className="g-label" style={{ fill: '#a5b4fc', fontWeight: 700, fontSize: 11 }}>{h.c}</text>
          </g>
        ))}
        {visibleEdges.map((e) => {
          const a = pos(e.source), b = pos(e.target)
          if (!a || !b) return null
          const st = STRENGTH[e.strength]
          const sel = selectedEdge === ekey(e)
          const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2
          const lab = REASON_SHORT[e.reasons[0]?.kind]
          const dim = !touches(e) ? 0.12 : centreId && !active && e.source !== centreId && e.target !== centreId ? 0.22 : 1
          const showLabel = labels && lab && (active ? touches(e) : centreId ? (e.source === centreId || e.target === centreId) && e.strength !== 'weak' : e.strength !== 'weak')
          return (
            <g key={ekey(e)} className="g-edge" style={{ opacity: dim }}>
              <motion.line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={st.color} strokeWidth={sel ? st.width + 2 : st.width} strokeLinecap="round"
                strokeDasharray={e.strength === 'weak' ? '5 5' : undefined} initial={{ pathLength: 0, opacity: 0 }} animate={{ pathLength: 1, opacity: 0.9 }} transition={{ duration: 0.7, ease: 'easeOut' }} />
              {e.strength === 'strong' && (dim === 1) && <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="#fff" strokeWidth="1.4" strokeLinecap="round" className="flow" opacity="0.55" />}
              <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth={16} style={{ cursor: 'pointer' }} onClick={() => onEdge?.(e)} />
              {showLabel && (
                <motion.g initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} transition={{ delay: 0.5 }} style={{ transformOrigin: `${mx}px ${my}px` }}>
                  <rect x={mx - 46} y={my - 17} width={92} height={15} rx={7.5} fill="#0a1123" stroke={st.color} strokeOpacity="0.5" />
                  <text x={mx} y={my - 6} textAnchor="middle" className="g-label" style={{ fill: st.color, fontWeight: 650, stroke: 'none', fontSize: 9.5 }}>{lang === 'ar' ? lab.ar : lab.en}{e.reasons.length > 1 ? ` +${e.reasons.length - 1}` : ''}</text>
                </motion.g>
              )}
            </g>
          )
        })}
        {[...nodeMap.current.values()].map((n) => {
          const r = n.center ? 27 : 19
          const color = scoreColor(n.score)
          const dim = active && active !== n.case_id && !visibleEdges.some((e) => touches(e) && (e.source === n.case_id || e.target === n.case_id))
          const sel = selectedNode === n.case_id
          return (
            <g key={n.case_id} className="g-node" transform={`translate(${n.x},${n.y})`} style={{ opacity: dim ? 0.2 : 1 }}
              onPointerDown={onDown(n.case_id)} onClick={() => { if (!drag.current?.moved) onNode?.(n.case_id) }} onPointerEnter={() => setHover(n.case_id)} onPointerLeave={() => setHover(null)}>
              <motion.g initial={{ scale: 0, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} transition={{ type: 'spring', stiffness: 380, damping: 17 }}>
                {n.score >= 85 && <circle r={r + 6} fill="none" stroke={color} className="halo" />}
                {n.center && <circle r={r + 13} fill="none" stroke={color} strokeOpacity="0.4" strokeDasharray="3 5"><animateTransform attributeName="transform" type="rotate" from="0" to="360" dur="14s" repeatCount="indefinite" /></circle>}
                {n.kind === 'maps_listing'
                  ? <rect x={-r + 2} y={-r + 2} width={2 * r - 4} height={2 * r - 4} rx={8} transform="rotate(45)" fill="url(#nodeFill)" stroke={sel ? '#fff' : '#a78bfa'} strokeWidth={sel ? 3 : 2} />
                  : <circle r={r} fill="url(#nodeFill)" stroke={sel ? '#fff' : color} strokeWidth={sel ? 3.5 : 2.5} filter={n.score >= 60 ? 'url(#glow)' : undefined} />}
                <text textAnchor="middle" dy="0.35em" style={{ fontSize: n.center ? 14 : 12, fontWeight: 700, fill: color, fontVariantNumeric: 'tabular-nums' }}>{n.score}</text>
                {n.kind === 'maps_listing' && <text textAnchor="middle" y={r + 25} className="g-label" style={{ fill: '#c4b5fd', fontSize: 9.5 }}>{p('Maps listing', 'موقع خرائط')}</text>}
                <text textAnchor="middle" y={r + 14} className="g-label">{short(n.kind === 'maps_listing' ? n.label : n.host, 24)}</text>
                {n.kind === 'site' && n.verdict !== 'no_indicators' && !n.on_blocklist && n.score >= 60 && (
                  <g transform={`translate(${r - 4},${-r + 4})`}><circle r="7" fill="#f5a524" stroke="#080d1b" strokeWidth="2" /><text textAnchor="middle" dy="0.35em" style={{ fontSize: 9, fontWeight: 800, fill: '#231600' }}>!</text></g>
                )}
              </motion.g>
            </g>
          )
        })}
      </svg>
      <AnimatePresence>
        {hovered && (
          <motion.div className="g-tip" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} transition={{ duration: 0.12 }}
            style={{ left: `${(hovered.x / width) * 100}%`, top: `${(hovered.y / height) * 100}%` }}>
            <b className="mono">{hovered.kind === 'maps_listing' ? hovered.label : hovered.host}</b>
            <div className="row" style={{ gap: 6, marginTop: 4, flexWrap: 'wrap' }}>
              <span className={`chip ${verdictOf(hovered.verdict).tone}`}>{lang === 'ar' ? verdictOf(hovered.verdict).ar : verdictOf(hovered.verdict).en}</span>
              {hovered.scam_type && SCAM_TYPES[hovered.scam_type] && <span className="chip">{lang === 'ar' ? SCAM_TYPES[hovered.scam_type].ar : SCAM_TYPES[hovered.scam_type].en}</span>}
              {hovered.kind === 'site' && <span className={`chip ${hovered.on_blocklist ? 'info' : 'warn'}`}>{hovered.on_blocklist ? p('blocklisted', 'محجوب') : p('not blocklisted', 'غير محجوب')}</span>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      <div className="g-legend">
        {(['strong', 'medium', 'weak'] as const).map((k) => <span key={k}><i style={{ borderColor: STRENGTH[k].color, borderTopStyle: k === 'weak' ? 'dashed' : 'solid' }} />{lang === 'ar' ? STRENGTH[k].ar : STRENGTH[k].en}</span>)}
        <span><span style={{ color: '#f5a524', fontWeight: 800 }}>!</span> {p('not on a public blocklist', 'غير مدرج في قائمة حجب')}</span>
        <span><span style={{ color: '#a78bfa' }}>◆</span> {p('Maps listing', 'موقع خرائط')}</span>
      </div>
    </div>
  )
}
