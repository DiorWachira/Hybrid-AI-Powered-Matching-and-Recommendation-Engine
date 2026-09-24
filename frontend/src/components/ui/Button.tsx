import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "gold" | "emerald" | "ghost" | "onEmerald";

const base =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full px-5 py-2.5 text-sm font-semibold " +
  "transition-all duration-200 ease-out hover:-translate-y-0.5 active:translate-y-0 " +
  "disabled:pointer-events-none disabled:opacity-60";

// Gold still carries dark ink: it is bright enough to read on the dark canvas as
// text, but CTAs stay ink-on-gold for the strongest contrast.
const variants: Record<Variant, string> = {
  gold: `${base} bg-gold text-ink shadow-sm hover:bg-gold-bright hover:shadow-md`,
  emerald: `${base} bg-surface-strong text-fg hover:bg-emerald`,
  ghost: `${base} text-fg hover:bg-surface`,
  onEmerald: `${base} border border-fg/25 text-fg hover:border-gold hover:text-gold-bright`,
};

type Props = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  children: ReactNode;
};

export function Button({ variant = "gold", className = "", children, ...rest }: Props) {
  return (
    <button className={`${variants[variant]} ${className}`} {...rest}>
      {children}
    </button>
  );
}
