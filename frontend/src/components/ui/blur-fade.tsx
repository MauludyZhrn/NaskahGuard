import React from "react"
import { cn } from "@/lib/utils"

interface BlurFadeProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
  className?: string
  duration?: number
  delay?: number
  offset?: number
  direction?: "up" | "down" | "left" | "right"
  inView?: boolean
  blur?: string
}

/**
 * Lightweight Magic UI–style fade-in entrance using pure CSS keyframes.
 * Never gets stuck at opacity: 0 across React StrictMode mounts or font loads,
 * and automatically collapses to instant reveal under prefers-reduced-motion.
 */
export function BlurFade({
  children,
  className,
  duration = 0.22,
  delay = 0,
  style,
  ...props
}: BlurFadeProps) {
  return (
    <div
      className={cn("ng-fade-in", className)}
      style={{
        animationDuration: `${duration}s`,
        animationDelay: `${delay}s`,
        ...style,
      }}
      {...props}
    >
      {children}
    </div>
  )
}
