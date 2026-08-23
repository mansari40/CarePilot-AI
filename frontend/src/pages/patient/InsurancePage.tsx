import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { patientApi } from "../../lib/api";
import { formatDate, statusBadge, statusDot, classNames } from "../../lib/utils";
import { ShieldCheck, ClipboardText, Tray } from "phosphor-react";

export default function InsurancePage() {
  const { t } = useTranslation();
  const [policies, setPolicies] = useState<any[]>([]);
  const [eligibility, setEligibility] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([patientApi.getInsurance(), patientApi.getEligibility()])
      .then(([ins, elig]) => { setPolicies(ins); setEligibility(elig); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <ShieldCheck weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("patient.insurance")}</h1>
          <p className="text-sm text-slate-500">{t("patient.insurance_subtitle")}</p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-4">{[1, 2].map((i) => (<div key={i} className="skeleton h-32 w-full rounded-2xl" />))}</div>
      ) : policies.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("patient.no_insurance")}</p>
          <p className="mt-1 text-xs text-slate-400">{t("patient.insurance_empty_hint")}</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2">
            {policies.map((pol) => (
              <div key={pol.id} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/5">
                <div className="mb-3 flex items-center justify-between">
                  <p className="text-sm font-semibold text-slate-900">{pol.provider || pol.insurance_provider || "—"}</p>
                  <span className={classNames("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", statusBadge(pol.is_active ? "covered" : "not_covered"))}>
                    <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(pol.is_active ? "covered" : "not_covered"))} />
                    {pol.is_active ? t("patient.active") : t("patient.inactive")}
                  </span>
                </div>
                <div className="space-y-1.5 text-xs text-slate-600">
                  <p>{t("patient.policy_number")}: <span className="font-medium text-slate-800">{pol.policy_number || "—"}</span></p>
                  <p>{t("patient.plan_type")}: <span className="font-medium text-slate-800">{pol.plan_type || pol.type || "—"}</span></p>
                  <p>{t("patient.valid_from")}: <span className="font-medium text-slate-800">{formatDate(pol.start_date || pol.valid_from)}</span></p>
                  <p>{t("patient.valid_to")}: <span className="font-medium text-slate-800">{formatDate(pol.end_date || pol.valid_to)}</span></p>
                </div>
              </div>
            ))}
          </div>
          <h2 className="mb-4 mt-8 flex items-center gap-2 font-heading text-lg font-bold text-slate-900">
            <ClipboardText className="h-5 w-5 text-blue-600" />{t("patient.eligibility")}
          </h2>
          {eligibility.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
              <Tray className="mb-3 h-12 w-12 text-slate-300" />
              <p className="text-sm font-medium text-slate-500">{t("patient.no_eligibility")}</p>
            </div>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2">
              {eligibility.map((el) => (
                <div key={el.id} className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/5">
                  <div className="mb-2 flex items-center justify-between">
                    <p className="text-sm font-medium text-slate-800">{el.service || el.procedure || "—"}</p>
                    <span className={classNames("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", statusBadge(el.status || el.coverage_status))}>
                      <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(el.status || el.coverage_status || "pending"))} />
                      {el.status || el.coverage_status || "—"}
                    </span>
                  </div>
                  <div className="space-y-1 text-xs text-slate-600">
                    {el.coverage_pct != null && <p>{t("patient.coverage")}: <span className="font-medium text-slate-800">{el.coverage_pct}%</span></p>}
                    {el.notes && <p>{el.notes}</p>}
                    <p>{t("patient.checked")} {formatDate(el.checked_at || el.created_at)}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </motion.div>
  );
}
