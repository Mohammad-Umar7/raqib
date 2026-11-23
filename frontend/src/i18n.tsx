import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Lang } from './types'

interface Ctx {
  lang: Lang
  setLang: (l: Lang) => void
  /** pick the English or Arabic string */
  p: (en: string, ar: string) => string
  /** pick a field from an object that has `x` and `x_ar` */
  f: (o: any, key: string) => string
}

const LangCtx = createContext<Ctx>({ lang: 'en', setLang: () => {}, p: (en) => en, f: (o, k) => o?.[k] ?? '' })

export function LangProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>(() => (localStorage.getItem('raqib.lang') as Lang) || 'en')
  useEffect(() => {
    document.documentElement.lang = lang
    document.documentElement.dir = lang === 'ar' ? 'rtl' : 'ltr'
    localStorage.setItem('raqib.lang', lang)
  }, [lang])
  const p = useCallback((en: string, ar: string) => (lang === 'ar' && ar ? ar : en), [lang])
  const f = useCallback((o: any, key: string) => (lang === 'ar' && o?.[key + '_ar'] ? o[key + '_ar'] : o?.[key] ?? ''), [lang])
  const value = useMemo(() => ({ lang, setLang, p, f }), [lang, p, f])
  return <LangCtx.Provider value={value}>{children}</LangCtx.Provider>
}

export const useLang = () => useContext(LangCtx)
