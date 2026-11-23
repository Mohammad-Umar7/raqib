import type { Candidate, Cluster, Entity, GEdge, GNode, Overview, Status } from './types'

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText
    try { msg = (await res.json()).detail ?? msg } catch { /* not json */ }
    throw new Error(msg)
  }
  return res.json() as Promise<T>
}

const post = (url: string, body: unknown) =>
  fetch(url, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })

export const api = {
  status: () => fetch('/api/status').then((r) => j<Status>(r)),
  overview: () => fetch('/api/overview').then((r) => j<Overview>(r)),
  registry: () => fetch('/api/registry').then((r) => j<{ entities: Entity[] }>(r)),
  targets: () => fetch('/api/demo-targets').then((r) => j<{ targets: { case_id: string; label: string; url: string; source: string; truth: string }[] }>(r)),
  candidates: () => fetch('/api/candidates').then((r) => j<{ candidates: (Candidate & { verdict: string | null; score: number | null })[] }>(r)),
  campaigns: () => fetch('/api/campaigns').then((r) => j<{ clusters: Cluster[] }>(r)),
  graph: () => fetch('/api/graph').then((r) => j<{ nodes: GNode[]; edges: GEdge[]; cluster_of: Record<string, string> }>(r)),
  triage: (host: string) => fetch('/api/triage?host=' + encodeURIComponent(host)).then((r) => j<{ score: number; reasons: { text: string; points: number }[]; brand: string | null }>(r)),
  start: (url: string, opts: { mode?: string; speed?: number } = {}) => post('/api/investigations', { url, ...opts }).then((r) => j<{ id: string; mode: string }>(r)),
  investigation: (id: string) => fetch(`/api/investigations/${id}`).then((r) => j<any>(r)),
  ask: (id: string, question: string) => post(`/api/investigations/${id}/ask`, { question }).then((r) => j<{ answer: string; answer_ar: string; blocks: any[]; source: string }>(r)),
  pack: (id: string) => fetch(`/api/investigations/${id}/pack`).then((r) => j<any>(r)),
  setKey: (key: string) => post('/api/settings/key', { key }).then((r) => j<{ ok: boolean }>(r)),
  clearKey: () => fetch('/api/settings/key', { method: 'DELETE' }).then((r) => j<{ ok: boolean }>(r)),
}

/** Subscribe to a server-sent event stream. Returns an unsubscribe function. */
export function stream(url: string, onEvent: (ev: any) => void, onClose?: () => void): () => void {
  const es = new EventSource(url)
  es.onmessage = (m) => {
    try { onEvent(JSON.parse(m.data)) } catch { /* ignore malformed frame */ }
  }
  es.onerror = () => { es.close(); onClose?.() }
  return () => es.close()
}
