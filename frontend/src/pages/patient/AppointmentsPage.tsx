import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { patientApi } from "../../lib/api";
import { formatDate, statusBadge, statusDot, classNames } from "../../lib/utils";
import { Calendar, FirstAid, UserCircle, Clock, FileText, Tray, XCircle } from "phosphor-react";

const CANCELLABLE_STATUSES = new Set(["scheduled", "confirmed", "rescheduled"]);

export default function AppointmentsPage() {
  const { t } = useTranslation();
  const [appointments, setAppointments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState<number | null>(null);
  const [confirmId, setConfirmId] = useState<number | null>(null);

  useEffect(() => {
    patientApi
      .getAppointments()
      .then(setAppointments)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleCancel(id: number) {
    setCancellingId(id);
    setConfirmId(null);
    try {
      const updated = await patientApi.cancelAppointment(id);
      setAppointments((prev) => prev.map((a) => (a.id === updated.id ? updated : a)));
    } catch {
    } finally {
      setCancellingId(null);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mx-auto max-w-5xl px-4 py-8"
    >
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <Calendar weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("patient.appointments")}</h1>
          <p className="text-sm text-slate-500">{t("patient.appointments_subtitle")}</p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-16 w-full rounded-xl" />
          ))}
        </div>
      ) : appointments.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("patient.no_appointments")}</p>
          <p className="mt-1 text-xs text-slate-400">{t("patient.appointments_empty_hint")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm ring-1 ring-slate-900/5">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/80">
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.date")}</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.department")}</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.doctor")}</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.status")}</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.visit_type")}</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {appointments.map((appt) => (
                  <tr key={appt.id} className="transition-colors hover:bg-slate-50/50">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <Clock className="h-3.5 w-3.5 text-slate-400" />
                        <span className="text-slate-700">{formatDate(appt.scheduled_for)}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <FirstAid className="h-3.5 w-3.5 text-slate-400" />
                        <span className="text-slate-700">{appt.department_name || "\u2014"}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <UserCircle className="h-3.5 w-3.5 text-slate-400" />
                        <span className="text-slate-700">{appt.doctor_name || appt.doctor || "\u2014"}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className={classNames("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", statusBadge(appt.status))}>
                        <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(appt.status))} />
                        {appt.status}
                      </span>
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-slate-400" />
                        <span className="text-slate-700">{appt.visit_type || "\u2014"}</span>
                      </div>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      {CANCELLABLE_STATUSES.has(appt.status) && (
                        confirmId === appt.id ? (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="text-xs text-slate-500">{t("patient.cancel_confirm")}</span>
                            <button
                              onClick={() => handleCancel(appt.id)}
                              disabled={cancellingId === appt.id}
                              className="rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-red-700 disabled:opacity-50"
                            >
                              {cancellingId === appt.id ? <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" /> : t("patient.yes")}
                            </button>
                            <button
                              onClick={() => setConfirmId(null)}
                              className="rounded-lg bg-slate-100 px-3 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-200"
                            >
                              {t("patient.no")}
                            </button>
                          </span>
                        ) : (
                          <button
                            onClick={() => setConfirmId(appt.id)}
                            disabled={cancellingId === appt.id}
                            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                            {t("patient.cancel")}
                          </button>
                        )
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </motion.div>
  );
}
