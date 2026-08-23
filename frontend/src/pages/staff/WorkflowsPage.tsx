import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { workflowApi } from "../../lib/api";
import { classNames, formatDate, statusBadge, statusDot } from "../../lib/utils";
import { ArrowsClockwise, Tray } from "phosphor-react";

interface WorkflowRun {
  id: number;
  patient_id: number;
  request_text: string;
  status: string;
  current_step: string;
  created_at: string;
  state: Record<string, any>;
}

export default function WorkflowsPage() {
  const { t } = useTranslation();
  const [runs, setRuns] = useState<WorkflowRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    workflowApi
      .list(50)
      .then(setRuns)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  function toggle(id: number) {
    setExpandedId(expandedId === id ? null : id);
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
          <ArrowsClockwise weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("staff.workflows.title")}</h1>
          <p className="text-sm text-slate-500">{t("staff.workflows.subtitle")}</p>
        </div>
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : runs.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("staff.workflows.empty")}</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white shadow-sm ring-1 ring-slate-900/5">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-100 bg-slate-50/80">
              <tr>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.workflows.id")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.workflows.patient_id")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.workflows.request")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.status")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.workflows.step")}</th>
                <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.workflows.created")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {runs.map((run) => (
                <>
                  <tr
                    key={run.id}
                    className="cursor-pointer transition-colors hover:bg-slate-50/50"
                    onClick={() => toggle(run.id)}
                  >
                    <td className="px-4 py-3 text-slate-700">{run.id}</td>
                    <td className="px-4 py-3 text-slate-700">{run.patient_id}</td>
                    <td className="max-w-[240px] truncate px-4 py-3 text-slate-700">
                      {run.request_text}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={classNames(
                          "inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium",
                          statusBadge(run.status)
                        )}
                      >
                        <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(run.status))} />
                        {run.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{run.current_step || "—"}</td>
                    <td className="px-4 py-3 text-slate-700">{formatDate(run.created_at)}</td>
                  </tr>

                  {expandedId === run.id && (
                    <tr key={`${run.id}-detail`}>
                      <td colSpan={6} className="border-t border-slate-100 bg-slate-50 px-6 py-4">
                        <div className="space-y-3 text-sm">
                          <div>
                            <span className="font-medium text-slate-700">{t("staff.workflows.full_request")}:</span>
                            <p className="mt-1 whitespace-pre-wrap text-slate-600">{run.request_text}</p>
                          </div>
                          {run.state?.summary && (
                            <div>
                              <span className="font-medium text-slate-700">{t("staff.workflows.summary")}:</span>
                              <p className="mt-1 text-slate-600">{run.state.summary}</p>
                            </div>
                          )}
                          <div>
                            <span className="font-medium text-slate-700">{t("staff.workflows.state_json")}:</span>
                            <pre className="mt-1 overflow-x-auto rounded-xl bg-slate-100 p-3 text-xs text-slate-600">
                              {JSON.stringify(run.state, null, 2)}
                            </pre>
                          </div>
                          {run.status === "escalated" && run.state?.escalation && (
                            <div className="rounded-xl border border-orange-200 bg-orange-50 p-3 ring-1 ring-orange-600/20">
                              <span className="font-medium text-orange-700">{t("staff.workflows.escalation_details")}:</span>
                              <pre className="mt-1 overflow-x-auto text-xs text-orange-800">
                                {JSON.stringify(run.state.escalation, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  )}
                </>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </motion.div>
  );
}
