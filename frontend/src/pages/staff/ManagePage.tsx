import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { staffApi } from "../../lib/api";
import { classNames } from "../../lib/utils";
import { Wrench, Tray } from "phosphor-react";

type Tab = "departments" | "doctors" | "slots";

const TABS: { key: Tab; labelKey: string }[] = [
  { key: "departments", labelKey: "staff.manage.tabs.departments" },
  { key: "doctors", labelKey: "staff.manage.tabs.doctors" },
  { key: "slots", labelKey: "staff.manage.tabs.slots" },
];

const INPUT_CLS =
  "rounded-xl border border-slate-300 bg-slate-50/50 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20";

function DepartmentsTable({ data }: { data: any[] }) {
  const { t } = useTranslation();
  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Tray className="mb-3 h-12 w-12 text-slate-300" />
        <p className="text-sm font-medium text-slate-500">{t("staff.manage.empty.departments")}</p>
      </div>
    );
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b border-slate-100 bg-slate-50/80">
        <tr>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.dept.name")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.dept.code")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.dept.building")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.dept.floor")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.active")}</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {data.map((d) => (
          <tr key={d.id} className="transition-colors hover:bg-slate-50/50">
            <td className="px-4 py-3 text-slate-700">{d.name}</td>
            <td className="px-4 py-3 text-slate-700">{d.code}</td>
            <td className="px-4 py-3 text-slate-700">{d.building || "\u2014"}</td>
            <td className="px-4 py-3 text-slate-700">{d.floor ?? "\u2014"}</td>
            <td className="px-4 py-3 text-slate-700">
              {d.is_active ? (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                  {t("staff.yes")}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                  {t("staff.no")}
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DoctorsTable({ data }: { data: any[] }) {
  const { t } = useTranslation();
  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Tray className="mb-3 h-12 w-12 text-slate-300" />
        <p className="text-sm font-medium text-slate-500">{t("staff.manage.empty.doctors")}</p>
      </div>
    );
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b border-slate-100 bg-slate-50/80">
        <tr>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.doc.name")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.doc.specialty")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.doc.license")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.doc.department")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.active")}</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {data.map((d) => (
          <tr key={d.id} className="transition-colors hover:bg-slate-50/50">
            <td className="px-4 py-3 text-slate-700">{d.name}</td>
            <td className="px-4 py-3 text-slate-700">{d.specialty || "\u2014"}</td>
            <td className="px-4 py-3 text-slate-700">{d.license_number || "\u2014"}</td>
            <td className="px-4 py-3 text-slate-700">{d.department_name || d.department_id || "\u2014"}</td>
            <td className="px-4 py-3 text-slate-700">
              {d.is_active ? (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-green-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                  {t("staff.yes")}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                  {t("staff.no")}
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function SlotsTable({ data }: { data: any[] }) {
  const { t } = useTranslation();
  if (data.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16">
        <Tray className="mb-3 h-12 w-12 text-slate-300" />
        <p className="text-sm font-medium text-slate-500">{t("staff.manage.empty.slots")}</p>
      </div>
    );
  }
  return (
    <table className="w-full text-left text-sm">
      <thead className="border-b border-slate-100 bg-slate-50/80">
        <tr>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.slot.doctor_id")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.slot.start")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.slot.end")}</th>
          <th className="px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">{t("staff.manage.slot.booked")}</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {data.map((s) => (
          <tr key={s.id} className="transition-colors hover:bg-slate-50/50">
            <td className="px-4 py-3 text-slate-700">{s.doctor_id}</td>
            <td className="px-4 py-3 text-slate-700">{s.start_time || "\u2014"}</td>
            <td className="px-4 py-3 text-slate-700">{s.end_time || "\u2014"}</td>
            <td className="px-4 py-3 text-slate-700">
              {s.is_booked ? (
                <span className="inline-flex items-center gap-1.5 text-xs font-medium text-orange-600">
                  <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                  {t("staff.yes")}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 text-xs text-slate-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
                  {t("staff.no")}
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function DepartmentForm({ onSuccess, onCancel }: { onSuccess: (d: any) => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ name: "", code: "", description: "", building: "", floor: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const dept = await staffApi.createDepartment({
        name: form.name,
        code: form.code,
        description: form.description || undefined,
        building: form.building || undefined,
        floor: form.floor ? Number(form.floor) : undefined,
      });
      onSuccess(dept);
    } catch (err: any) {
      setError(err.message || t("staff.manage.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <input className={INPUT_CLS} placeholder={t("staff.manage.dept.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input className={INPUT_CLS} placeholder={t("staff.manage.dept.code")} value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} required />
      <input className={INPUT_CLS} placeholder={t("staff.manage.dept.description")} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
      <input className={INPUT_CLS} placeholder={t("staff.manage.dept.building")} value={form.building} onChange={(e) => setForm({ ...form, building: e.target.value })} />
      <input className={INPUT_CLS} placeholder={t("staff.manage.dept.floor")} type="number" value={form.floor} onChange={(e) => setForm({ ...form, floor: e.target.value })} />
      <div className="flex gap-2 sm:col-span-2 lg:col-span-3">
        <button type="submit" disabled={submitting} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all hover:shadow-md hover:bg-teal-700 active:scale-[0.98] disabled:opacity-50">{submitting ? t("staff.manage.submitting") : t("staff.manage.submit")}</button>
        <button type="button" onClick={onCancel} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition-all hover:shadow-md hover:bg-slate-100 active:scale-[0.98]">{t("staff.manage.cancel")}</button>
      </div>
      {error && (
        <p className="sm:col-span-2 lg:col-span-3 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-600 ring-1 ring-red-600/20">{error}</p>
      )}
    </form>
  );
}

function DoctorForm({ departments, onSuccess, onCancel }: { departments: any[]; onSuccess: (d: any) => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ name: "", specialty: "", license_number: "", department_id: "", email: "", phone: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const doc = await staffApi.createDoctor({
        name: form.name,
        specialty: form.specialty || undefined,
        license_number: form.license_number || undefined,
        department_id: form.department_id ? Number(form.department_id) : undefined,
        email: form.email || undefined,
        phone: form.phone || undefined,
      });
      onSuccess(doc);
    } catch (err: any) {
      setError(err.message || t("staff.manage.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
      <input className={INPUT_CLS} placeholder={t("staff.manage.doc.name")} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
      <input className={INPUT_CLS} placeholder={t("staff.manage.doc.specialty")} value={form.specialty} onChange={(e) => setForm({ ...form, specialty: e.target.value })} />
      <input className={INPUT_CLS} placeholder={t("staff.manage.doc.license")} value={form.license_number} onChange={(e) => setForm({ ...form, license_number: e.target.value })} />
      <select className={INPUT_CLS} value={form.department_id} onChange={(e) => setForm({ ...form, department_id: e.target.value })}>
        <option value="">{t("staff.manage.doc.select_dept")}</option>
        {departments.map((d) => (
          <option key={d.id} value={d.id}>{d.name}</option>
        ))}
      </select>
      <input className={INPUT_CLS} placeholder={t("staff.manage.doc.email")} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
      <input className={INPUT_CLS} placeholder={t("staff.manage.doc.phone")} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
      <div className="flex gap-2 sm:col-span-2 lg:col-span-3">
        <button type="submit" disabled={submitting} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all hover:shadow-md hover:bg-teal-700 active:scale-[0.98] disabled:opacity-50">{submitting ? t("staff.manage.submitting") : t("staff.manage.submit")}</button>
        <button type="button" onClick={onCancel} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition-all hover:shadow-md hover:bg-slate-100 active:scale-[0.98]">{t("staff.manage.cancel")}</button>
      </div>
      {error && (
        <p className="sm:col-span-2 lg:col-span-3 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-600 ring-1 ring-red-600/20">{error}</p>
      )}
    </form>
  );
}

function SlotForm({ onSuccess, onCancel }: { onSuccess: (s: any) => void; onCancel: () => void }) {
  const { t } = useTranslation();
  const [form, setForm] = useState({ doctor_id: "", start_time: "", end_time: "" });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const slot = await staffApi.createSlot({
        doctor_id: Number(form.doctor_id),
        start_time: form.start_time,
        end_time: form.end_time,
      });
      onSuccess(slot);
    } catch (err: any) {
      setError(err.message || t("staff.manage.error"));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-3">
      <input className={INPUT_CLS} placeholder={t("staff.manage.slot.doctor_id")} type="number" value={form.doctor_id} onChange={(e) => setForm({ ...form, doctor_id: e.target.value })} required />
      <input className={INPUT_CLS} placeholder={t("staff.manage.slot.start")} type="datetime-local" value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} required />
      <input className={INPUT_CLS} placeholder={t("staff.manage.slot.end")} type="datetime-local" value={form.end_time} onChange={(e) => setForm({ ...form, end_time: e.target.value })} required />
      <div className="flex gap-2 sm:col-span-3">
        <button type="submit" disabled={submitting} className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-all hover:shadow-md hover:bg-teal-700 active:scale-[0.98] disabled:opacity-50">{submitting ? t("staff.manage.submitting") : t("staff.manage.submit")}</button>
        <button type="button" onClick={onCancel} className="rounded-xl border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 shadow-sm transition-all hover:shadow-md hover:bg-slate-100 active:scale-[0.98]">{t("staff.manage.cancel")}</button>
      </div>
      {error && (
        <p className="sm:col-span-3 rounded-xl bg-red-50 px-3 py-2 text-xs text-red-600 ring-1 ring-red-600/20">{error}</p>
      )}
    </form>
  );
}

export default function ManagePage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("departments");
  const [showForm, setShowForm] = useState(false);
  const [departments, setDepartments] = useState<any[]>([]);
  const [doctors, setDoctors] = useState<any[]>([]);
  const [slots, setSlots] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      staffApi.getDepartments().catch(() => []),
      staffApi.getDoctors().catch(() => []),
      staffApi.getSlots().catch(() => []),
    ])
      .then(([d, doc, s]) => {
        setDepartments(d);
        setDoctors(doc);
        setSlots(s);
      })
      .finally(() => setLoading(false));
  }, []);

  function handleTabChange(key: Tab) {
    setTab(key);
    setShowForm(false);
  }

  const addLabel = showForm ? t("staff.manage.cancel") : t("staff.manage.add." + tab);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="mx-auto max-w-6xl px-4 py-8"
    >
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50">
          <Wrench weight="fill" className="h-5 w-5 text-blue-600" />
        </div>
        <div>
          <h1 className="font-heading text-xl font-bold text-slate-900">{t("staff.manage.title")}</h1>
          <p className="text-sm text-slate-500">{t("staff.manage.subtitle")}</p>
        </div>
      </div>

      <div className="mb-4 flex gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        {TABS.map((item) => (
          <button
            key={item.key}
            onClick={() => handleTabChange(item.key)}
            className={classNames(
              "rounded-xl px-4 py-2 text-sm font-medium transition-all shadow-sm",
              tab === item.key
                ? "bg-teal-600 text-white shadow-md"
                : "text-slate-600 hover:bg-slate-100 hover:shadow-md active:scale-[0.98]"
            )}
          >
            {t(item.labelKey)}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <div key={i} className="skeleton h-14 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <div className="rounded-2xl border border-slate-200/80 bg-white shadow-sm ring-1 ring-slate-900/5">
          <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50/80 px-4 py-3">
            <h2 className="text-sm font-semibold text-slate-700">{t(TABS.find((x) => x.key === tab)!.labelKey)}</h2>
            <button
              onClick={() => setShowForm(!showForm)}
              className="rounded-xl bg-teal-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition-all hover:shadow-md hover:bg-teal-700 active:scale-[0.98]"
            >
              {addLabel}
            </button>
          </div>

          {showForm && (
            <div className="border-b border-slate-100 bg-slate-50/50 px-4 py-4">
              {tab === "departments" && (
                <DepartmentForm
                  onSuccess={(dept) => { setDepartments((prev) => [...prev, dept]); setShowForm(false); }}
                  onCancel={() => setShowForm(false)}
                />
              )}
              {tab === "doctors" && (
                <DoctorForm
                  departments={departments}
                  onSuccess={(doc) => { setDoctors((prev) => [...prev, doc]); setShowForm(false); }}
                  onCancel={() => setShowForm(false)}
                />
              )}
              {tab === "slots" && (
                <SlotForm
                  onSuccess={(slot) => { setSlots((prev) => [...prev, slot]); setShowForm(false); }}
                  onCancel={() => setShowForm(false)}
                />
              )}
            </div>
          )}

          <div className="overflow-x-auto">
            {tab === "departments" && <DepartmentsTable data={departments} />}
            {tab === "doctors" && <DoctorsTable data={doctors} />}
            {tab === "slots" && <SlotsTable data={slots} />}
          </div>
        </div>
      )}
    </motion.div>
  );
}
