import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { patientApi } from "../../lib/api";
import { formatDate, statusBadge, statusDot, classNames } from "../../lib/utils";
import { Bell, Calendar, Tag, Tray } from "phosphor-react";

export default function RemindersPage() {
  const { t } = useTranslation();
  const [reminders, setReminders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    patientApi.getReminders().then(setReminders).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <Bell weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("patient.reminders")}</h1>
          <p className="text-sm text-slate-500">{t("patient.reminders_subtitle")}</p>
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[1, 2, 3].map((i) => (<div key={i} className="skeleton h-32 w-full rounded-2xl" />))}
        </div>
      ) : reminders.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("patient.no_reminders")}</p>
          <p className="mt-1 text-xs text-slate-400">{t("patient.reminders_empty_hint")}</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {reminders.map((rem) => (
            <div key={rem.id} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/5 transition-all hover:shadow-md hover:ring-slate-900/10">
              <p className="mb-3 text-sm font-medium text-slate-900">{rem.message || rem.text || "\u2014"}</p>
              {rem.appointment_date && (
                <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                  <Calendar className="h-3.5 w-3.5 text-blue-500" />
                  <span className="font-medium">{t("patient.appointment_date")}:</span>
                  <span>{formatDate(rem.appointment_date)}</span>
                </div>
              )}
              <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                <Bell className="h-3.5 w-3.5 text-amber-500" />
                <span className="font-medium">{t("patient.notify_on")}:</span>
                <span>{formatDate(rem.scheduled_for || rem.scheduled_at)}</span>
              </div>
              <div className="mb-3 flex items-center gap-2 text-xs text-slate-500">
                <Tag className="h-3.5 w-3.5" />
                <span className="font-medium">{t("patient.type")}:</span>
                <span>{rem.type || rem.reminder_type || "\u2014"}</span>
              </div>
              <span className={classNames("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", statusBadge(rem.status))}>
                <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(rem.status))} />
                {rem.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
