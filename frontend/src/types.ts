export type Verdict = 'confirmed_scam' | 'likely_scam' | 'suspicious' | 'no_indicators' | 'official'
export type Lang = 'en' | 'ar'
export type Tone = 'danger' | 'warn' | 'ok' | 'info'

export interface El {
  id: string
  kind: string
  text?: string
  form?: string
  field?: { name: string; type: string; autocomplete?: string; placeholder?: string; label?: string; inputmode?: string; maxlength?: number }
  phone?: string
  whatsapp?: string
  wallet?: string
  email?: string
}

export interface Frame { page_id: string; url: string; title: string; elements: El[]; viewport: { w: number; h: number }; kind?: string; image?: string }

export interface Signal {
  id: string
  category: string
  label: string
  label_ar: string
  weight: number
  severity: 'critical' | 'high' | 'medium' | 'low'
  evidence: { type: string; element?: string; page?: string; note?: string; value?: string }[]
}

export interface Req { method: string; url: string; status: number; type: string; flag?: string }
export interface EvItem { id: string; kind: string; label: string; sha256: string; size: number; ts: string; page?: string | null }

export interface GNode {
  case_id: string
  host: string
  label: string
  kind: 'site' | 'maps_listing'
  score: number
  verdict: Verdict
  scam_type?: string
  cluster_id?: string | null
  on_blocklist?: boolean
  emirates?: string[]
  center?: boolean
}
export interface Reason { kind: string; strength: 'strong' | 'medium' | 'weak'; text: string; text_ar: string; value?: string | null }
export interface GEdge { source: string; target: string; strength: 'strong' | 'medium' | 'weak'; weight: number; reasons: Reason[] }

export interface Indicators {
  contacts: { phones: string[]; whatsapp: string[]; emails: string[] }
  iocs: { telegram_bot_ids: string[]; discord_webhook_ids: string[]; wallets: string[]; analytics_ids: string[] }
  brand: { id: string; name: string; name_ar: string; domains: string[] } | null
  brand_confidence: number
}

export interface Block { type: string; [k: string]: any }

export interface Funnel { scanned: number; unique: number; flagged: number; investigated: number; confirmed: number; unblocked: number }
export interface Cluster {
  cluster_id: string
  size: number
  sites: (GNode & { family?: string })[]
  shared_indicators: string[]
  unblocked: number
  emirates: string[]
  headline: string
}
export interface Overview {
  funnel: Funnel
  hosting_countries: Record<string, number>
  clusters: Cluster[]
  threshold: number
  entities: number
}

export interface Candidate {
  id: string
  source: string
  title: string
  host: string
  detail: string
  case_id: string | null
  when: string
  seen_in?: string[]
  triage: { score: number; reasons: { text: string; points: number }[]; brand: string | null }
}

export interface Status {
  version: string
  requested_mode: string
  claude: { enabled: boolean; model: string; last_error: string | null }
  playwright: boolean
  live_ready: boolean
  speed: number
  cases: number
  entities: number
}

export interface Entity { id: string; name: string; name_ar: string; sector: string; scam_type: string; emirate: string; domains: string[]; keywords: string[] }
