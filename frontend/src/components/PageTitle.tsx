import type { ReactNode } from "react";

export function PageTitle({ eyebrow, title, detail, action }: { eyebrow: string; title: string; detail: string; action?: ReactNode }) {
  return <div className="flex flex-wrap items-end justify-between gap-4"><div><p className="font-mono text-[10px] uppercase tracking-[0.18em] text-spectral-emerald">{eyebrow}</p><h1 className="mt-2 text-2xl font-semibold tracking-tight text-white sm:text-3xl">{title}</h1><p className="mt-2 max-w-2xl text-sm leading-relaxed text-white/45">{detail}</p></div>{action}</div>;
}
