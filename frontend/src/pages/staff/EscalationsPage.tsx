import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { escalationApi } from "../../lib/api";
import { classNames, formatDate, statusBadge, statusDot } from "../../lib/utils";
import { WarningCircle, Tray } from "phosphor-react";

const SEVERITY_CLASSES: Record<string, string> = {
  critical: "bg-red-50 text-red-700 ring-1 ring-red-600/20",
  high: "bg-orange-50 text-orange-700 ring-1 ring-orange-600/20",
  medium: "bg-yellow-50 text-yellow-700 ring-1 ring-yellow-600/20",
  low: "bg-blue-50 text-blue-700 ring-1 ring-blue-600/20",
};

const SEVERITY_DOT: Record<string, string> = {
  critical: "bg-red-500",
  high: "bg-orange-500",
  medium: "bg-yellow-500",
  low: "bg-blue-500",
};

interface Escalation {
  id: number;
  severity: string;
  reason: string;
  status: string;
  patient_id: number;
  created_at: string;
  resolution_notes?: string;
  resolved_at?: string;
}

export default function EscalationsPage() {
  const { t } = useTranslation();
  const [escalations, setEscalations] = useState<Escalation[]>([]);
  const [loading, setLoading] = useState(true);
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    escalationApi
      .list()
      .then(setEscalations)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleResolve(id: number) {
    setSubmitting(true);
    try {
      const updated = await escalationApi.resolve(id, notes);
      setEscalations((prev) => prev.map((e) => (e.id === id ? { ...e, ...updated } : e)));
      setResolvingId(null);
      setNotes("");
    } catch {
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mx-auto max-w-6xl px-4 py-8"
    >
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <WarningCircle weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("staff.escalations.title")}</h1>
          <p className="text-sm text-slate-500">{t("staff.escalations.subtitle")}</p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : escalations.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("staff.escalations.empty")}</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm ring-1 ring-slate-900/5">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 bg-slate-50/80">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.escalations.id")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.escalations.severity")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.escalations.reason")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.status")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.escalations.patient_id")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.escalations.created")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.escalations.actions")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {escalations.map((esc) => (
                <tr key={esc.id} className="transition-colors hover:bg-slate-50/50">
                  <td className="px-4 py-3 text-slate-700">{esc.id}</td>
                  <td className="px-4 py-3">
                    <span
                      className={classNames(
                        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                        SEVERITY_CLASSES[esc.severity] || "bg-gray-50 text-gray-700 ring-1 ring-gray-600/20"
                      )}
                    >
                      <span className={classNames("h-1.5 w-1.5 rounded-full", SEVERITY_DOT[esc.severity] || "bg-gray-500")} />
                      {esc.severity}
                    </span>
                  </td>
                  <td className="max-w-[240px] truncate px-4 py-3 text-slate-700">{esc.reason}</td>
                  <td className="px-4 py-3">
                    <span
                      className={classNames(
                        "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                        statusBadge(esc.status)
                      )}
                    >
                      <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(esc.status))} />
                      {esc.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-700">{esc.patient_id}</td>
                  <td className="px-4 py-3 text-slate-700">{formatDate(esc.created_at)}</td>
                  <td className="px-4 py-3">
                    {esc.status === "open" && resolvingId !== esc.id && (
                      <button
                        onClick={() => setResolvingId(esc.id)}
                        className="rounded-xl bg-teal-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all hover:shadow-md hover:bg-teal-700 active:scale-[0.98]"
                      >
                        {t("staff.escalations.resolve")}
                      </button>
                    )}
                    {esc.status === "open" && resolvingId === esc.id && (
                      <button
                        onClick={() => setResolvingId(null)}
                        className="rounded-xl px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:text-slate-700 hover:bg-slate-100 active:scale-[0.98]"
                      >
                        {t("staff.manage.cancel")}
                      </button>
                    )}
                    {esc.status === "resolved" && esc.resolution_notes && (
                      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-600">
                        <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                        {t("staff.escalations.resolved_label")}
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {resolvingId !== null && (
            <div className="border-t border-slate-100 bg-slate-50/50 px-4 py-4">
              <label className="mb-2 block text-sm font-medium text-slate-700">{t("staff.escalations.resolution_notes")}</label>
              <textarea
                className="mb-3 w-full rounded-xl border border-slate-300 bg-slate-50/50 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
                rows={3}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder={t("staff.escalations.resolution_placeholder")}
              />
              <button
                onClick={() => handleResolve(resolvingId)}
                disabled={submitting || !notes.trim()}
                className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all hover:shadow-md hover:bg-teal-700 active:scale-[0.98] disabled:opacity-50"
              >
                {submitting ? t("staff.manage.submitting") : t("staff.escalations.confirm_resolve")}
              </button>
            </div>
          )}

          {escalations
            .filter((e) => e.status === "resolved" && e.resolution_notes)
            .map((esc) => (
              <div key={`resolved-${esc.id}`} className="border-t border-slate-100 bg-green-50/50 px-4 py-3">
                <p className="flex items-center gap-2 text-xs text-green-700">
                  <span className="font-medium">{t("staff.escalations.escalation")} #{esc.id}</span> &mdash; {esc.resolution_notes}
                  {esc.resolved_at && <span className="ml-2 text-green-600">({formatDate(esc.resolved_at)})</span>}
                </p>
              </div>
            ))}
        </div>
      )}
    </motion.div>
  );
}
