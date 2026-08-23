export function formatDate(s: string | null | undefined): string {
  if (!s) return "\u2014";
  return new Date(s).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function classNames(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(" ");
}

export const STATUS_COLORS: Record<string, string> = {
  pending: "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20",
  requested: "bg-blue-50 text-blue-700 ring-1 ring-blue-600/20",
  scheduled: "bg-indigo-50 text-indigo-700 ring-1 ring-indigo-600/20",
  confirmed: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20",
  booked: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20",
  completed: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20",
  cancelled: "bg-red-50 text-red-700 ring-1 ring-red-600/20",
  escalated: "bg-orange-50 text-orange-700 ring-1 ring-orange-600/20",
  failed: "bg-red-50 text-red-700 ring-1 ring-red-600/20",
  open: "bg-orange-50 text-orange-700 ring-1 ring-orange-600/20",
  resolved: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20",
  covered: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-600/20",
  not_covered: "bg-red-50 text-red-700 ring-1 ring-red-600/20",
  needs_preauth: "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20",
  awaiting_confirmation: "bg-amber-50 text-amber-700 ring-1 ring-amber-600/20",
  awaiting_document: "bg-sky-50 text-sky-700 ring-1 ring-sky-600/20",
  awaiting_clarification: "bg-violet-50 text-violet-700 ring-1 ring-violet-600/20",
};

export function statusBadge(status: string): string {
  return STATUS_COLORS[status] || "bg-slate-50 text-slate-700 ring-1 ring-slate-600/20";
}

export const STATUS_DOT: Record<string, string> = {
  pending: "bg-amber-500",
  requested: "bg-blue-500",
  scheduled: "bg-indigo-500",
  confirmed: "bg-emerald-500",
  booked: "bg-emerald-500",
  completed: "bg-emerald-500",
  cancelled: "bg-red-500",
  escalated: "bg-orange-500",
  failed: "bg-red-500",
  open: "bg-orange-500",
  resolved: "bg-emerald-500",
  covered: "bg-emerald-500",
  not_covered: "bg-red-500",
  needs_preauth: "bg-amber-500",
  awaiting_confirmation: "bg-amber-500",
  awaiting_document: "bg-sky-500",
  awaiting_clarification: "bg-violet-500",
};

export function statusDot(status: string): string {
  return STATUS_DOT[status] || "bg-slate-500";
}
