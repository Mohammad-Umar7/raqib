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
