import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { auditApi } from "../../lib/api";
import { formatDate } from "../../lib/utils";
import { ClockCounterClockwise, Tray } from "phosphor-react";

interface AuditEvent {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: number;
  created_at: string;
}

export default function AuditPage() {
  const { t } = useTranslation();
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    auditApi
      .list(100)
      .then(setEvents)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mx-auto max-w-6xl px-4 py-8"
    >
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <ClockCounterClockwise weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("staff.audit.title")}</h1>
          <p className="text-sm text-slate-500">{t("staff.audit.subtitle")}</p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : events.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("staff.audit.empty")}</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm ring-1 ring-slate-900/5">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 bg-slate-50/80">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.audit.id")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.audit.actor")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.audit.action")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.audit.entity")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.audit.entity_id")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.audit.created")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {events.map((ev) => (
                <tr key={ev.id} className="transition-colors hover:bg-slate-50/50">
                  <td className="px-4 py-3 text-slate-700">{ev.id}</td>
                  <td className="px-4 py-3 text-slate-700">{ev.actor || "\u2014"}</td>
                  <td className="px-4 py-3 text-slate-700">{ev.action || "\u2014"}</td>
                  <td className="px-4 py-3 text-slate-700">{ev.entity_type || "\u2014"}</td>
                  <td className="px-4 py-3 text-slate-700">{ev.entity_id ?? "\u2014"}</td>
                  <td className="px-4 py-3 text-slate-700">{formatDate(ev.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
