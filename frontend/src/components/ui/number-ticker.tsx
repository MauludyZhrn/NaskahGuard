"use client"

import { useEffect, useRef, type ComponentPropsWithoutRef } from "react"
import { useInView, useMotionValue, useReducedMotion, useSpring } from "motion/react"

import { cn } from "@/lib/utils"

interface NumberTickerProps extends ComponentPropsWithoutRef<"span"> {
  value: number
  startValue?: number
  direction?: "up" | "down"
  delay?: number
  decimalPlaces?: number
  locale?: string
}

export function NumberTicker({
  value,
  startValue = 0,
  direction = "up",
  delay = 0,
  className,
  decimalPlaces = 0,
  locale = "id-ID",
  ...props
}: NumberTickerProps) {
  const ref = useRef<HTMLSpanElement>(null)
  const prefersReduced = useReducedMotion()
  const targetVal = direction === "down" ? startValue : value
  const motionValue = useMotionValue(prefersReduced ? targetVal : direction === "down" ? value : startValue)
  const springValue = useSpring(motionValue, {
    damping: 60,
    stiffness: 110,
  })
  const isInView = useInView(ref, { once: true, margin: "0px" })

  const formatNum = (n: number) =>
    Intl.NumberFormat(locale, {
      minimumFractionDigits: decimalPlaces,
      maximumFractionDigits: decimalPlaces,
    }).format(Number(n.toFixed(decimalPlaces)))

  useEffect(() => {
    if (prefersReduced) {
      if (ref.current) {
        ref.current.textContent = formatNum(targetVal)
      }
      return
    }

    let timer: ReturnType<typeof setTimeout> | null = null
    if (isInView) {
      timer = setTimeout(() => {
        motionValue.set(targetVal)
      }, delay * 1000)
    }
    return () => {
      if (timer !== null) clearTimeout(timer)
    }
  }, [motionValue, isInView, delay, targetVal, prefersReduced, decimalPlaces, locale])

  useEffect(() => {
    if (prefersReduced) return
    return springValue.on("change", (latest) => {
      if (ref.current) {
        ref.current.textContent = formatNum(latest)
      }
    })
  }, [springValue, decimalPlaces, locale, prefersReduced])

  return (
    <span
      ref={ref}
      className={cn("inline-block tabular-nums text-foreground", className)}
      {...props}
    >
      {formatNum(prefersReduced || value === 0 ? targetVal : startValue)}
    </span>
  )
}
