import type { Tone, Verdict } from './types'

/** Colour carries risk and nothing else: red scam, orange suspicious, green clean. */
export const RISK = { high: '#e5484d', mid: '#e2803c', low: '#4cc38a', none: '#85858b' } as const

export const VERDICT: Record<Verdict, { en: string; ar: string; tone: Tone; color: string }> = {
  confirmed_scam: { en: 'Confirmed scam', ar: 'احتيال مؤكد', tone: 'danger', color: RISK.high },
  likely_scam: { en: 'Likely scam', ar: 'احتيال محتمل', tone: 'danger', color: RISK.high },
  suspicious: { en: 'Suspicious', ar: 'مشبوه', tone: 'warn', color: RISK.mid },
  no_indicators: { en: 'No scam indicators', ar: 'لا مؤشرات احتيال', tone: 'ok', color: RISK.low },
  official: { en: 'Official domain', ar: 'نطاق رسمي', tone: 'ok', color: RISK.low },
}

export const verdictOf = (v?: string) => VERDICT[(v as Verdict) ?? 'no_indicators'] ?? VERDICT.no_indicators

export const scoreColor = (s: number) => (s >= 60 ? RISK.high : s >= 30 ? RISK.mid : RISK.low)

/** Link strength is a magnitude, so it is drawn in neutral steps, not hues. */
export const STRENGTH = {
  strong: { en: 'Strong link', ar: 'ارتباط قوي', color: '#d4d4d8', width: 2.5 },
  medium: { en: 'Medium link', ar: 'ارتباط متوسط', color: '#85858b', width: 1.75 },
  weak: { en: 'Weak link', ar: 'ارتباط ضعيف', color: '#55555a', width: 1.25 },
} as const

export const cap = (s?: string | null) => (s ? s.charAt(0).toUpperCase() + s.slice(1).replace(/_/g, ' ') : '')

export const SCAM_TYPES: Record<string, { en: string; ar: string }> = {
  toll_topup: { en: 'Fake toll top-up', ar: 'رسوم سالك مزيفة' },
  traffic_fine: { en: 'Fake traffic fine', ar: 'مخالفات مرورية مزيفة' },
  parcel_fee: { en: 'Fake parcel fee', ar: 'رسوم طرد مزيفة' },
  bank_verification: { en: 'Bank phishing', ar: 'تصيّد مصرفي' },
  bill_refund: { en: 'Fake bill refund', ar: 'استرداد فواتير مزيف' },
  government_service: { en: 'Fake government service', ar: 'خدمة حكومية مزيفة' },
  investment: { en: 'Investment fraud', ar: 'احتيال استثماري' },
  advance_fee_loan: { en: 'Advance-fee loan', ar: 'قرض برسوم مقدّمة' },
  job_offer: { en: 'Fake job offer', ar: 'عرض وظيفي مزيف' },
  fake_shop: { en: 'Fake shop', ar: 'متجر مزيف' },
  prize_travel: { en: 'Fake prize', ar: 'جائزة مزيفة' },
  phishing: { en: 'Payment phishing', ar: 'تصيّد بيانات الدفع' },
  unknown: { en: 'Suspicious site', ar: 'موقع مشبوه' },
  none: { en: 'No scam', ar: 'لا احتيال' },
}

export const SOURCES: Record<string, { en: string; ar: string; icon: string }> = {
  ct: { en: 'New domain', ar: 'نطاق جديد', icon: 'shield' },
  search: { en: 'Search result', ar: 'نتيجة بحث', icon: 'search' },
  search_ad: { en: 'Sponsored ad', ar: 'إعلان ممول', icon: 'megaphone' },
  maps: { en: 'Maps listing', ar: 'موقع على الخرائط', icon: 'map' },
  report: { en: 'Citizen report', ar: 'بلاغ مواطن', icon: 'message' },
  sms: { en: 'SMS link', ar: 'رابط رسالة', icon: 'message' },
  nrd: { en: 'New domain', ar: 'نطاق جديد', icon: 'shield' },
  sibling: { en: 'Sibling site', ar: 'موقع شقيق', icon: 'network' },
}

export const REASON_SHORT: Record<string, { en: string; ar: string }> = {
  exfil: { en: 'Same data bot', ar: 'نفس بوت البيانات' },
  wallet: { en: 'Same wallet', ar: 'نفس المحفظة' },
  phone: { en: 'Same phone', ar: 'نفس الهاتف' },
  kit: { en: 'Same kit file', ar: 'نفس ملف الأدوات' },
  email: { en: 'Same e-mail', ar: 'نفس البريد' },
  favicon: { en: 'Same favicon', ar: 'نفس الأيقونة' },
  analytics: { en: 'Same analytics ID', ar: 'نفس معرّف التحليلات' },
  redirect: { en: 'Same redirector', ar: 'نفس نطاق التحويل' },
  registration: { en: 'Same registration batch', ar: 'نفس دفعة التسجيل' },
  ip: { en: 'Same server', ar: 'نفس الخادم' },
  asn: { en: 'Same hosting', ar: 'نفس الاستضافة' },
  layout: { en: 'Similar layout', ar: 'تخطيط مشابه' },
  text: { en: 'Similar wording', ar: 'صياغة مشابهة' },
}

/** Where a radar item stands, in plain words. */
export const RADAR_STATE: Record<string, { en: string; ar: string; tone: string }> = {
  queued: { en: 'Queued', ar: 'في الانتظار', tone: '' },
  checking: { en: 'Checking now', ar: 'قيد الفحص', tone: 'live' },
  watching: { en: 'Watching', ar: 'تحت المراقبة', tone: '' },
  confirmed: { en: 'Confirmed scam', ar: 'احتيال مؤكد', tone: 'danger' },
  down: { en: 'Offline now', ar: 'متوقف الآن', tone: 'ok' },
  cleared: { en: 'Cleared', ar: 'سليم', tone: 'ok' },
  dismissed: { en: 'Not a scam', ar: 'ليس احتيالاً', tone: 'ok' },
}

export const ACTION_KIND: Record<string, { en: string; ar: string }> = {
  blocklist: { en: 'Blocklist feed', ar: 'قائمة الحجب' },
  safebrowsing: { en: 'Google Safe Browsing', ar: 'التصفح الآمن من جوجل' },
  brand_alert: { en: 'Brand alert', ar: 'تنبيه الجهة' },
  registrar: { en: 'Registrar takedown', ar: 'طلب إيقاف لدى المسجّل' },
  host: { en: 'Host takedown', ar: 'طلب إيقاف لدى المستضيف' },
}

export const ACTION_STATUS: Record<string, { en: string; ar: string; tone: string }> = {
  done: { en: 'done', ar: 'تم', tone: 'ok' },
  drafted: { en: 'drafted', ar: 'مسودة جاهزة', tone: '' },
  pending: { en: 'waiting for you', ar: 'بانتظارك', tone: 'warn' },
  approved: { en: 'approved', ar: 'تمت الموافقة', tone: 'ok' },
  rejected: { en: 'rejected', ar: 'مرفوض', tone: '' },
  revoked: { en: 'withdrawn', ar: 'مسحوب', tone: '' },
}

export function ago(ts: number | null | undefined, p: (en: string, ar: string) => string): string {
  if (!ts) return '–'
  const s = Date.now() / 1000 - ts
  const a = Math.abs(s)
  const v = a < 60 ? p('seconds', 'ثوانٍ') : a < 3600 ? `${Math.round(a / 60)} ${p('min', 'دقيقة')}` : a < 86400 ? `${Math.round(a / 3600)} ${p('h', 'ساعة')}` : `${Math.round(a / 86400)} ${p('d', 'يوم')}`
  return s >= 0 ? p(`${v} ago`, `قبل ${v}`) : p(`in ${v}`, `بعد ${v}`)
}
