import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { patientApi } from "../../lib/api";
import { formatDate } from "../../lib/utils";
import { Receipt, CalendarCheck, Tray } from "phosphor-react";

export default function BillingPage() {
  const { t } = useTranslation();
  const [billing, setBilling] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    patientApi.getBilling().then(setBilling).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <Receipt weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("patient.billing")}</h1>
          <p className="text-sm text-slate-500">{t("patient.billing_subtitle")}</p>
        </div>
      </div>

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2">{[1, 2].map((i) => (<div key={i} className="skeleton h-28 w-full rounded-2xl" />))}</div>
      ) : billing.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("patient.no_billing")}</p>
          <p className="mt-1 text-xs text-slate-400">{t("patient.billing_empty_hint")}</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2">
          {billing.map((item) => (
            <div key={item.id} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/5 transition-all hover:shadow-md hover:ring-slate-900/10">
              <div className="mb-3 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CalendarCheck className="h-4 w-4 text-blue-600" />
                  <p className="text-sm font-semibold text-slate-900">
                    {t("patient.appointment")}: #{item.appointment_id || "—"}
                  </p>
                </div>
                <span className="text-xs text-slate-400">{formatDate(item.generated_at || item.created_at)}</span>
              </div>
              <p className="text-sm leading-relaxed text-slate-600">{item.summary_text || "—"}</p>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
