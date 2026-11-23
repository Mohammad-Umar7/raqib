import type { Tone, Verdict } from './types'

export const VERDICT: Record<Verdict, { en: string; ar: string; tone: Tone; color: string }> = {
  confirmed_scam: { en: 'Confirmed scam', ar: 'احتيال مؤكد', tone: 'danger', color: '#fb4a6c' },
  likely_scam: { en: 'Likely scam', ar: 'احتيال محتمل', tone: 'danger', color: '#fb6a4a' },
  suspicious: { en: 'Suspicious', ar: 'مشبوه', tone: 'warn', color: '#f5a524' },
  no_indicators: { en: 'No scam indicators', ar: 'لا مؤشرات احتيال', tone: 'ok', color: '#34d399' },
  official: { en: 'Official domain', ar: 'نطاق رسمي', tone: 'ok', color: '#34d399' },
}

export const verdictOf = (v?: string) => VERDICT[(v as Verdict) ?? 'no_indicators'] ?? VERDICT.no_indicators

export const scoreColor = (s: number) => (s >= 85 ? '#fb4a6c' : s >= 60 ? '#fb7a4a' : s >= 30 ? '#f5a524' : '#34d399')

export const STRENGTH = {
  strong: { en: 'Strong link', ar: 'ارتباط قوي', color: '#fb4a6c', width: 2.8 },
  medium: { en: 'Medium link', ar: 'ارتباط متوسط', color: '#f5a524', width: 2 },
  weak: { en: 'Weak link', ar: 'ارتباط ضعيف', color: '#6b7aa0', width: 1.2 },
} as const

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
  ct: { en: 'New certificate', ar: 'شهادة جديدة', icon: 'shield' },
  search: { en: 'Search result', ar: 'نتيجة بحث', icon: 'search' },
  search_ad: { en: 'Sponsored ad', ar: 'إعلان ممول', icon: 'megaphone' },
  maps: { en: 'Maps listing', ar: 'موقع على الخرائط', icon: 'map' },
  report: { en: 'Citizen report', ar: 'بلاغ مواطن', icon: 'message' },
  sms: { en: 'SMS link', ar: 'رابط رسالة', icon: 'message' },
}

export const EMIRATES = ['Abu Dhabi', 'Dubai', 'Sharjah', 'Ajman', 'Umm Al Quwain', 'Ras Al Khaimah', 'Fujairah'] as const
export const EMIRATE_AR: Record<string, string> = {
  'Abu Dhabi': 'أبوظبي', Dubai: 'دبي', Sharjah: 'الشارقة', Ajman: 'عجمان', 'Umm Al Quwain': 'أم القيوين', 'Ras Al Khaimah': 'رأس الخيمة', Fujairah: 'الفجيرة',
}

export const CATEGORY_ICON: Record<string, string> = {
  impersonation: 'mask', payment: 'card', exfiltration: 'send', fraud: 'alert', infrastructure: 'server',
}

export const PHASES = ['browsing', 'analyzing', 'fingerprinting', 'linking', 'reporting'] as const
export const PHASE_LABEL: Record<string, { en: string; ar: string }> = {
  browsing: { en: 'Browse', ar: 'التصفح' },
  analyzing: { en: 'Analyse', ar: 'التحليل' },
  fingerprinting: { en: 'Fingerprint', ar: 'البصمة' },
  linking: { en: 'Link campaign', ar: 'ربط الحملة' },
  reporting: { en: 'Case view', ar: 'ملف القضية' },
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
