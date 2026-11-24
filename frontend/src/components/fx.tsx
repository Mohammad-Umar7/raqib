import { useEffect, useRef, useState, type ReactNode } from 'react'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { useCountUp } from '../hooks'

/** One easing curve for the whole app; short for feedback, longer for things that enter. */
export const ease = [0.22, 1, 0.36, 1] as const
export const spring = { duration: 0.18, ease }
export const soft = { duration: 0.36, ease }

/** Types text out quickly (the whole string takes at most ~1.4 s) with a caret while typing. */
export function Typewriter({ text, onDone, caret = true }: { text: string; onDone?: () => void; caret?: boolean }) {
  const [n, setN] = useState(0)
  const done = useRef(onDone)
  done.current = onDone
  useEffect(() => {
    setN(0)
    if (!text) return
    const step = Math.max(1, Math.ceil(text.length / 70))
    let i = 0
    const id = window.setInterval(() => {
      i = Math.min(text.length, i + step)
      setN(i)
      if (i >= text.length) { window.clearInterval(id); done.current?.() }
    }, 20)
    return () => window.clearInterval(id)
  }, [text])
  return <>{text.slice(0, n)}{caret && n < text.length && <span className="caret" />}</>
}

export function Num({ value, ms = 900, suffix = '' }: { value: number; ms?: number; suffix?: string }) {
  const v = useCountUp(value, ms)
  return <>{Math.round(v).toLocaleString('en-US')}{suffix}</>
}

/** Fade and a short rise on mount, staggered by index (at most six steps). */
export function Rise({ i = 0, y = 8, children, ...rest }: { i?: number; y?: number; children: ReactNode } & HTMLMotionProps<'div'>) {
  return (
    <motion.div initial={{ opacity: 0, y }} animate={{ opacity: 1, y: 0 }} transition={{ ...soft, delay: Math.min(i, 6) * 0.05 }} {...rest}>
      {children}
    </motion.div>
  )
}

/** Same, but triggered when scrolled into view (used for case-file blocks). */
export function Reveal({ i = 0, children, className }: { i?: number; children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 8 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true, margin: '0px 0px -40px 0px' }}
      transition={{ ...soft, delay: Math.min(i, 6) * 0.04 }}>
      {children}
    </motion.div>
  )
}
