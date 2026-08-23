import { useEffect, useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { patientApi, workflowApi } from "../../lib/api";
import { formatDate, classNames } from "../../lib/utils";
import { FolderOpen, Upload, Trash, FileText, FileImage, Tray, CheckCircle, WarningCircle } from "phosphor-react";

const DOC_TYPES = ["ecg", "lab_report", "prescription", "referral", "id_proof", "imaging", "other"];

const DOC_TYPE_COLORS: Record<string, string> = {
  ecg: "bg-rose-50 text-rose-600",
  lab_report: "bg-sky-50 text-sky-600",
  prescription: "bg-emerald-50 text-emerald-600",
  referral: "bg-amber-50 text-amber-600",
  id_proof: "bg-violet-50 text-violet-600",
  imaging: "bg-indigo-50 text-indigo-600",
  other: "bg-slate-50 text-slate-600",
};

const DOC_TYPE_ICONS: Record<string, typeof FileText> = {
  ecg: FileText,
  lab_report: FileText,
  prescription: FileText,
  referral: FileText,
  id_proof: FileText,
  imaging: FileImage,
  other: FileText,
};

export default function DocumentsPage() {
  const { t } = useTranslation();
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [docType, setDocType] = useState("other");
  const fileRef = useRef<HTMLInputElement>(null);

  function load() {
    patientApi.getDocuments().then(setDocuments).catch(() => {}).finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, []);

  async function handleUpload() {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    setError("");
    setSuccess("");
    try {
      const doc = await patientApi.uploadDocument(file, docType);
      setDocuments((prev) => [doc, ...prev]);
      let resumedCount = 0;
      try {
        const runs = await workflowApi.list(50);
        for (const run of runs) {
          if (run.status === "awaiting_document") {
            try {
              await workflowApi.resume(run.id, `Uploaded document: ${file.name}`, doc.id);
              resumedCount++;
            } catch { /* resume may fail */ }
          }
        }
      } catch { /* workflow list fetch failed; doc still uploaded */ }
      setSuccess(resumedCount > 0 ? t("patient.upload_and_resume_success") : t("patient.upload_success"));
      if (fileRef.current) fileRef.current.value = "";
    } catch (e: any) {
      setError(e.message || t("patient.upload_error"));
    } finally {
      setUploading(false);
    }
  }

  async function handleDelete(docId: number) {
    setError("");
    setSuccess("");
    try {
      await patientApi.deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      setSuccess(t("patient.delete_success"));
    } catch (e: any) {
      setError(e.message || t("patient.delete_error"));
    }
  }

  return (
    <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }} className="mx-auto max-w-5xl px-4 py-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <FolderOpen weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("patient.documents")}</h1>
          <p className="text-sm text-slate-500">{t("patient.documents_subtitle")}</p>
        </div>
      </div>

      <div className="mb-6 rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm ring-1 ring-slate-900/5">
        <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
          <Upload className="h-4 w-4" />{t("patient.upload_title")}
        </h2>
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[140px]">
            <label className="mb-1.5 block text-xs font-medium text-slate-500">{t("patient.doc_type")}</label>
            <select value={docType} onChange={(e) => setDocType(e.target.value)}
              className="w-full rounded-xl border border-slate-300 bg-slate-50/50 px-3 py-2 text-sm transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20">
              {DOC_TYPES.map((dt) => (<option key={dt} value={dt}>{t(`patient.doctype.${dt}`, dt)}</option>))}
            </select>
          </div>
          <div className="min-w-[200px] flex-1">
            <label className="mb-1.5 block text-xs font-medium text-slate-500">{t("patient.choose_file")}</label>
            <input ref={fileRef} type="file"
              className="w-full rounded-xl border border-dashed border-slate-300 bg-slate-50/50 px-4 py-2 text-sm text-slate-600 file:mr-3 file:rounded-lg file:border-0 file:bg-blue-50 file:px-3 file:py-1 file:text-sm file:font-medium file:text-blue-600 hover:file:bg-blue-100" />
          </div>
          <button onClick={handleUpload} disabled={uploading}
            className="flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md active:scale-[0.98] disabled:opacity-50">
            {uploading ? <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" /> : <Upload className="h-4 w-4" />}
            {uploading ? t("patient.uploading") : t("patient.upload_btn")}
          </button>
        </div>
        {error && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 flex items-center gap-2 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-700 ring-1 ring-red-600/10"><WarningCircle className="h-3.5 w-3.5 shrink-0" />{error}</motion.div>}
        {success && <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-3 flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700 ring-1 ring-emerald-600/10"><CheckCircle className="h-3.5 w-3.5 shrink-0" />{success}</motion.div>}
      </div>

      {loading ? (
        <div className="space-y-3">{[1, 2, 3].map((i) => (<div key={i} className="skeleton h-14 w-full rounded-xl" />))}</div>
      ) : documents.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white py-16 ring-1 ring-slate-900/5">
          <Tray className="mb-3 h-12 w-12 text-slate-300" />
          <p className="text-sm font-medium text-slate-500">{t("patient.no_documents")}</p>
          <p className="mt-1 text-xs text-slate-400">{t("patient.documents_empty_hint")}</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-slate-200/80 bg-white shadow-sm ring-1 ring-slate-900/5">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50/80">
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.filename")}</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.doc_type")}</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.uploaded")}</th>
                  <th className="px-5 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("patient.duplicate")}</th>
                  <th className="px-5 py-3"></th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => {
                  const TypeIcon = DOC_TYPE_ICONS[doc.document_type] || FileText;
                  return (
                    <tr key={doc.id} className="transition-colors hover:bg-slate-50/50">
                      <td className="px-5 py-3.5"><div className="flex items-center gap-2"><FileText className="h-4 w-4 text-slate-400" /><span className="font-medium text-slate-700">{doc.filename}</span></div></td>
                      <td className="px-5 py-3.5">
                        <span className={classNames("inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium", DOC_TYPE_COLORS[doc.document_type] || "bg-slate-50 text-slate-600")}>
                          <TypeIcon className="h-3 w-3" />{doc.document_type}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-slate-600">{formatDate(doc.uploaded_at)}</td>
                      <td className="px-5 py-3.5">
                        {doc.is_duplicate ? <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-600"><WarningCircle className="h-3 w-3" />{t("patient.yes")}</span> : <span className="text-xs text-slate-400">{t("patient.no")}</span>}
                      </td>
                      <td className="px-5 py-3.5">
                        <button onClick={() => handleDelete(doc.id)} className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-red-500 transition-colors hover:bg-red-50 hover:text-red-700">
                          <Trash className="h-3.5 w-3.5" />{t("patient.delete")}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </motion.div>
  );
}
