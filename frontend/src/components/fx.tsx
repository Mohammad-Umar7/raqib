import { useEffect, useRef, useState, type ReactNode } from 'react'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { useCountUp } from '../hooks'

export const spring = { type: 'spring' as const, stiffness: 420, damping: 32, mass: 0.8 }
export const soft = { type: 'spring' as const, stiffness: 190, damping: 24, mass: 0.9 }

/** Types text out quickly (the whole string takes at most ~1.4 s) with a blinking caret. */
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

const HEX = '0123456789abcdef'
/** Shows random characters that settle left to right: used for hashes so evidence feels "decoded". */
export function Scramble({ text, ms = 700 }: { text: string; ms?: number }) {
  const [out, setOut] = useState(text)
  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const tick = (t: number) => {
      const k = Math.min(1, (t - start) / ms)
      const fixed = Math.floor(k * text.length)
      setOut(text.slice(0, fixed) + Array.from(text.slice(fixed), () => HEX[(Math.random() * 16) | 0]).join(''))
      if (k < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [text, ms])
  return <>{out}</>
}

export function Num({ value, ms = 900, suffix = '' }: { value: number; ms?: number; suffix?: string }) {
  const v = useCountUp(value, ms)
  return <>{Math.round(v).toLocaleString('en-US')}{suffix}</>
}

/** Fade + rise on mount, staggered by index. */
export function Rise({ i = 0, y = 16, children, ...rest }: { i?: number; y?: number; children: ReactNode } & HTMLMotionProps<'div'>) {
  return (
    <motion.div initial={{ opacity: 0, y }} animate={{ opacity: 1, y: 0 }} transition={{ ...soft, delay: Math.min(i, 12) * 0.06 }} {...rest}>
      {children}
    </motion.div>
  )
}

/** Same, but triggered when scrolled into view (used for case-file blocks). */
export function Reveal({ i = 0, children, className }: { i?: number; children: ReactNode; className?: string }) {
  return (
    <motion.div className={className} initial={{ opacity: 0, y: 28, scale: 0.985 }} whileInView={{ opacity: 1, y: 0, scale: 1 }} viewport={{ once: true, margin: '0px 0px -40px 0px' }}
      transition={{ ...soft, delay: Math.min(i, 6) * 0.05 }}>
      {children}
    </motion.div>
  )
}
