import type { ReactNode } from "react";

type Props = {
  children: ReactNode;
  tone?: "gold" | "emerald" | "outline";
  className?: string;
};

const tones = {
  gold: "bg-gold text-ink",
  emerald: "bg-surface-strong text-fg",
  outline: "border border-gold/60 text-gold",
};

export function Badge({ children, tone = "outline", className = "" }: Props) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 font-mono text-[11px] font-medium tracking-wide uppercase ${tones[tone]} ${className}`}
    >
      {children}
    </span>
  );
}
