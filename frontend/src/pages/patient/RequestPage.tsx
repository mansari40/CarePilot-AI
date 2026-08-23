import { useEffect, useState, useRef, useCallback } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { PaperPlaneRight, Check, WarningCircle, ChatCircle, Tray, X } from "phosphor-react";
import { workflowApi } from "../../lib/api";
import { useAuth } from "../../context/AuthContext";
import { classNames, formatDate, statusBadge, statusDot } from "../../lib/utils";

const TERMINAL_STATUSES = new Set([
  "completed",
  "awaiting_confirmation",
  "awaiting_document",
  "escalated",
  "failed",
]);

const HIDEABLE_STATUSES = new Set(["completed", "escalated", "failed", "cancelled"]);

export default function RequestPage() {
  const { t } = useTranslation();
  const { user } = useAuth();

  const [text, setText] = useState("");
  const [runs, setRuns] = useState<any[]>([]);
  const [selected, setSelected] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [clarifyText, setClarifyText] = useState("");
  const [clarifying, setClarifying] = useState(false);
  const [error, setError] = useState("");
  const [hideConfirmId, setHideConfirmId] = useState<number | null>(null);

  const pollingRef = useRef<number | null>(null);
  const pollListRef = useRef<number | null>(null);

  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current);
      pollingRef.current = null;
    }
  }, []);

  const stopListPolling = useCallback(() => {
    if (pollListRef.current) {
      clearInterval(pollListRef.current);
      pollListRef.current = null;
    }
  }, []);

  useEffect(() => {
    loadRuns();
    return () => { stopPolling(); stopListPolling(); };
  }, [stopPolling, stopListPolling]);

  async function loadRuns() {
    setLoading(true);
    try {
      const data = await workflowApi.list(50);
      setRuns(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("patient.error_load"));
    } finally {
      setLoading(false);
    }
  }

  function startPolling(runId: number) {
    stopPolling();
    pollingRef.current = window.setInterval(async () => {
      try {
        const detail = await workflowApi.get(runId);
        setSelected(detail);
        setRuns((prev) => prev.map((r) => (r.id === detail.id ? detail : r)));
        if (TERMINAL_STATUSES.has(detail.status)) {
          stopPolling();
        }
      } catch {
        stopPolling();
      }
    }, 2500);
  }

  function startListPolling() {
    stopListPolling();
    pollListRef.current = window.setInterval(async () => {
      try {
        const data = await workflowApi.list(50);
        setRuns(data);
      } catch { /* silent */ }
    }, 3000);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim() || !user) return;
    setSubmitting(true);
    setError("");
    try {
      const run = await workflowApi.run(user.id, text.trim());
      setText("");
      setRuns((prev) => [run, ...prev]);
      setSelected(run);
      if (run.status === "failed") {
        setError(run.state?.error || t("patient.error_process"));
      } else if (!TERMINAL_STATUSES.has(run.status)) {
        startPolling(run.id);
        startListPolling();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("patient.error_submit"));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleConfirm() {
    if (!selected) return;
    try {
      const updated = await workflowApi.resume(selected.id, "confirmed");
      setSelected(updated);
      setRuns((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      if (updated.status === "failed") {
        setError(updated.state?.error || t("patient.error_confirm"));
      } else if (!TERMINAL_STATUSES.has(updated.status)) {
        startPolling(updated.id);
        startListPolling();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("patient.error_confirm_generic"));
    }
  }

  async function handleClarifyReply() {
    if (!selected || !clarifyText.trim()) return;
    setClarifying(true);
    setError("");
    try {
      const updated = await workflowApi.resume(selected.id, clarifyText.trim());
      setClarifyText("");
      setSelected(updated);
      setRuns((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      if (updated.status === "failed") {
        setError(updated.state?.error || t("patient.error_reply"));
      } else if (!TERMINAL_STATUSES.has(updated.status)) {
        startPolling(updated.id);
        startListPolling();
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("patient.error_reply"));
    } finally {
      setClarifying(false);
    }
  }

  async function handleHide(runId: number) {
    setHideConfirmId(null);
    try {
      await workflowApi.hide(runId);
      setRuns((prev) => prev.filter((r) => r.id !== runId));
      if (selected?.id === runId) {
        setSelected(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("patient.error_hide"));
    }
  }

  async function handleSelectRun(run: any) {
    try {
      const detail = await workflowApi.get(run.id);
      setSelected(detail);
      setClarifyText("");
      if (!TERMINAL_STATUSES.has(detail.status)) {
        startPolling(detail.id);
      } else {
        stopPolling();
      }
    } catch {
      setSelected(run);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mx-auto max-w-4xl px-4 py-8"
    >
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <PaperPlaneRight weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("patient.request")}</h1>
          <p className="text-sm text-slate-500">{t("patient.request_subtitle")}</p>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="mb-8 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/5">
        <label className="mb-2 block text-sm font-medium text-slate-700">{t("patient.request_placeholder")}</label>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={3}
          className="w-full rounded-xl border border-slate-300 bg-slate-50/50 px-4 py-3 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          placeholder={t("patient.request_placeholder")}
        />
        <AnimatePresence>
          {error && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
            >
              <div className="mt-3 flex items-center gap-2 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-600/10">
                <WarningCircle className="h-4 w-4 shrink-0" />
                {error}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={submitting || !text.trim()}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md active:scale-[0.98] disabled:opacity-50"
          >
            {submitting ? (
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <PaperPlaneRight className="h-4 w-4" />
            )}
            {submitting ? t("patient.submitting") : t("patient.submit_request")}
          </button>
        </div>
      </form>

      <div className="grid gap-6 md:grid-cols-5">
        <div className="md:col-span-2">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <ChatCircle className="h-4 w-4" />
            {t("patient.request_history")}
          </h2>
          {loading ? (
            <div className="space-y-2">
              <div className="skeleton h-16 w-full rounded-xl" />
              <div className="skeleton h-16 w-full rounded-xl" />
              <div className="skeleton h-16 w-full rounded-xl" />
            </div>
          ) : runs.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white py-12 ring-1 ring-slate-900/5">
              <div className="flex flex-col items-center gap-2 text-slate-400">
                <Tray className="h-8 w-8" />
                <p className="text-sm italic">{t("patient.no_requests")}</p>
              </div>
            </div>
          ) : (
            <ul className="space-y-2">
              {runs.map((run) => (
                <li key={run.id}>
                  <div className="group relative">
                    <button
                      onClick={() => handleSelectRun(run)}
                      className={classNames(
                        "w-full rounded-xl border p-3 text-left text-sm transition-all duration-150",
                        selected?.id === run.id
                          ? "border-blue-500 bg-blue-50 ring-1 ring-blue-500/20"
                          : "border-slate-200 bg-white hover:border-blue-300 hover:shadow-sm"
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span className="truncate font-medium text-slate-800">{run.request_text || `#${run.id}`}</span>
                        <span className={classNames("ml-2 flex shrink-0 items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium", statusBadge(run.status))}>
                          <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(run.status))} />
                          {run.status}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-slate-400">{formatDate(run.created_at)}</p>
                    </button>
                    {HIDEABLE_STATUSES.has(run.status) && (
                      hideConfirmId === run.id ? (
                        <div className="absolute right-2 top-2 z-10 flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 shadow-md">
                          <span className="text-xs text-slate-500">{t("patient.hide_confirm")}</span>
                          <button
                            onClick={() => handleHide(run.id)}
                            className="rounded bg-red-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-red-700"
                          >
                            {t("patient.yes")}
                          </button>
                          <button
                            onClick={() => setHideConfirmId(null)}
                            className="rounded bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600 hover:bg-slate-200"
                          >
                            {t("patient.no")}
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={(e) => { e.stopPropagation(); setHideConfirmId(run.id); }}
                          className="absolute right-2 top-2 z-10 rounded-lg p-1 text-slate-300 opacity-0 transition-all hover:bg-red-50 hover:text-red-500 group-hover:opacity-100"
                          title={t("patient.hide_request")}
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      )
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="md:col-span-3">
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
            <ChatCircle className="h-4 w-4" />
            {t("patient.request_details")}
          </h2>
          {selected ? (
            <div className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/5">
              <div className="mb-3 flex items-center gap-3">
                <span className={classNames("flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", statusBadge(selected.status))}>
                  <span className={classNames("h-1.5 w-1.5 rounded-full", statusDot(selected.status))} />
                  {selected.status}
                </span>
                <span className="text-xs text-slate-400">#{selected.id}</span>
              </div>
              <p className="mb-2 text-sm text-slate-700">{selected.request_text}</p>
              <p className="mb-4 text-xs text-slate-400">{formatDate(selected.created_at)}</p>

              {selected.summary && (
                <div className="mb-3 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-900/5">
                  <p className="text-xs font-medium uppercase tracking-wider text-slate-600">{t("patient.summary")}</p>
                  <p className="mt-1 text-sm text-slate-700">{selected.summary}</p>
                </div>
              )}

              {selected.status === "awaiting_confirmation" && (
                <button
                  onClick={handleConfirm}
                  className="flex items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-emerald-700 hover:shadow-md active:scale-[0.98]"
                >
                  <Check className="h-4 w-4" />
                  {t("patient.confirm")}
                </button>
              )}

              {selected.status === "awaiting_clarification" && (
                <div className="space-y-3">
                  {(selected.state?.clarify_question || selected.final_response || selected.summary) && (
                    <div className="rounded-xl bg-violet-50 p-4 ring-1 ring-violet-600/10">
                      <p className="text-xs font-medium uppercase tracking-wider text-violet-700">{t("patient.clarification_question")}</p>
                      <p className="mt-1 text-sm text-violet-800">{selected.state?.clarify_question || selected.final_response || selected.summary}</p>
                    </div>
                  )}
                  <form
                    onSubmit={(e) => { e.preventDefault(); handleClarifyReply(); }}
                    className="flex gap-2"
                  >
                    <input
                      type="text"
                      value={clarifyText}
                      onChange={(e) => setClarifyText(e.target.value)}
                      placeholder={t("patient.clarification_placeholder")}
                      className="flex-1 rounded-xl border border-slate-300 bg-slate-50/50 px-4 py-2.5 text-sm text-slate-900 placeholder-slate-400 transition-colors focus:border-violet-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-violet-500/20"
                    />
                    <button
                      type="submit"
                      disabled={clarifying || !clarifyText.trim()}
                      className="flex items-center gap-2 rounded-xl bg-violet-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm transition-all hover:bg-violet-700 hover:shadow-md active:scale-[0.98] disabled:opacity-50"
                    >
                      {clarifying ? (
                        <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                      ) : (
                        <PaperPlaneRight className="h-4 w-4" />
                      )}
                      {clarifying ? t("patient.replying") : t("patient.reply")}
                    </button>
                  </form>
                </div>
              )}

              {selected.status === "escalated" && selected.state?.escalation_reason && (
                <div className="flex items-start gap-2 rounded-xl border border-orange-200 bg-orange-50 p-4 ring-1 ring-orange-600/10">
                  <WarningCircle className="mt-0.5 h-4 w-4 shrink-0 text-orange-500" />
                  <div>
                    <p className="text-xs font-medium text-orange-700">{t("patient.escalation_reason")}</p>
                    <p className="mt-1 text-sm text-orange-800">{selected.state.escalation_reason}</p>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white py-12 ring-1 ring-slate-900/5">
              <div className="flex flex-col items-center gap-2 text-slate-400">
                <Tray className="h-8 w-8" />
                <p className="text-sm italic">{t("patient.select_request")}</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
}
