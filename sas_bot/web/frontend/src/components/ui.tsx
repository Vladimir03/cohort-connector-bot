// Minimal shadcn-style UI primitives (Tailwind only). Dark-mode native.
import { clsx } from "clsx";
import type { ButtonHTMLAttributes, HTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

export const cn = (...args: Parameters<typeof clsx>) => clsx(...args);

export function Card({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-xl border border-zinc-800 bg-zinc-900/60 backdrop-blur p-5", className)} {...p} />;
}
export function CardTitle({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("text-xs uppercase tracking-wide text-zinc-400 font-medium", className)} {...p} />;
}
export function CardValue({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-2 text-3xl font-semibold tabular-nums text-zinc-50", className)} {...p} />;
}
export function CardSub({ className, ...p }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("mt-1 text-xs text-zinc-500", className)} {...p} />;
}

type BtnVariant = "default" | "ghost" | "outline" | "danger";
export function Button({
  variant = "default", className, ...p
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: BtnVariant }) {
  const base = "inline-flex items-center justify-center rounded-md px-3 py-2 text-sm font-medium transition disabled:opacity-50 disabled:cursor-not-allowed";
  const v = {
    default: "bg-emerald-500 text-zinc-950 hover:bg-emerald-400",
    ghost: "text-zinc-300 hover:bg-zinc-800/60",
    outline: "border border-zinc-700 text-zinc-200 hover:bg-zinc-800/60",
    danger: "bg-red-500 text-white hover:bg-red-400",
  }[variant];
  return <button className={cn(base, v, className)} {...p} />;
}

export function Input({ className, ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn("w-full rounded-md bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 focus:border-emerald-500/60", className)} {...p} />;
}
export function Textarea({ className, ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn("w-full rounded-md bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-2 focus:ring-emerald-500/40 focus:border-emerald-500/60", className)} {...p} />;
}
export function Select({ className, children, ...p }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn("rounded-md bg-zinc-900 border border-zinc-800 px-3 py-2 text-sm text-zinc-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/40", className)} {...p}>
      {children}
    </select>
  );
}

export const SEGMENT_COLORS: Record<string, string> = {
  pre_webinar: "bg-zinc-700 text-zinc-200",
  attended_live: "bg-blue-500/20 text-blue-300 border border-blue-500/30",
  no_show: "bg-orange-500/20 text-orange-300 border border-orange-500/30",
  hot_lead: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30",
  customer: "bg-violet-500/20 text-violet-300 border border-violet-500/30",
  churned: "bg-red-500/20 text-red-300 border border-red-500/30",
};

export function Badge({ children, tone, className }: { children: ReactNode; tone?: string; className?: string }) {
  const cls = tone && SEGMENT_COLORS[tone] ? SEGMENT_COLORS[tone] : "bg-zinc-800 text-zinc-300";
  return <span className={cn("inline-flex items-center rounded px-2 py-0.5 text-xs font-medium", cls, className)}>{children}</span>;
}

export function Dialog({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onClose}>
      <div className="w-full max-w-2xl rounded-xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        {children}
      </div>
    </div>
  );
}

// Table primitives
export function Table({ children }: { children: ReactNode }) {
  return <table className="w-full text-sm">{children}</table>;
}
export function Thead({ children }: { children: ReactNode }) {
  return <thead className="sticky top-0 bg-zinc-900 text-left text-xs uppercase tracking-wide text-zinc-400">{children}</thead>;
}
export function Th({ children, className }: { children: ReactNode; className?: string }) {
  return <th className={cn("px-3 py-2 font-medium border-b border-zinc-800", className)}>{children}</th>;
}
export function Tr({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return <tr onClick={onClick} className={cn("border-b border-zinc-800/60 hover:bg-zinc-800/40 transition", onClick && "cursor-pointer")}>{children}</tr>;
}
export function Td({ children, className }: { children: ReactNode; className?: string }) {
  return <td className={cn("px-3 py-2 align-middle", className)}>{children}</td>;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const t = new Date(iso.replace(" ", "T") + (iso.endsWith("Z") ? "" : "Z"));
  const diff = (Date.now() - t.getTime()) / 1000;
  if (diff < 60) return `${Math.floor(diff)}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
