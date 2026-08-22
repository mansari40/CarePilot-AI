import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend,
  LineChart, Line, CartesianGrid,
} from "recharts";
import { useAuth } from "../context/AuthContext";

const COLORS = ["#0d9488", "#06b6d4", "#8b5cf6", "#f59e0b", "#ef4444", "#64748b", "#10b981"];

interface Dashboard {
  appointments_by_department: { department: string; count: number }[];
  appointments_by_status: { status: string; count: number }[];
  avg_request_to_booking: { average_seconds: number; sample_count: number };
  document_completion: {
    total_appointments: number;
    appointments_with_documents: number;
    completion_rate_pct: number;
    total_documents: number;
    duplicate_documents: number;
    duplicate_rate_pct: number;
  };
  escalation_stats: {
    total: number;
    open: number;
    resolved: number;
    avg_resolution_seconds: number;
    by_severity: { severity: string; count: number }[];
  };
  insurance_eligibility_outcomes: { status: string; count: number }[];
  busiest_doctors: { doctor: string; department: string; appointment_count: number }[];
  busiest_days: { day: string; count: number }[];
}

export default function DashboardPage() {
  const { t } = useTranslation();
  const { token } = useAuth();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/analytics/dashboard", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => {
        if (res.status === 403) throw new Error("forbidden");
        if (!res.ok) throw new Error("error");
        return res.json();
      })
      .then(setData)
      .catch((e) => setError(e.message === "forbidden" ? "forbidden" : "error"))
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="mt-16 text-center text-slate-500">{t("dashboard.loading")}</p>;
  if (error === "forbidden") return <p className="mt-16 text-center text-red-600">{t("dashboard.access_denied")}</p>;
  if (!data) return <p className="mt-16 text-center text-red-600">{t("dashboard.no_data")}</p>;

  const deptData = data.appointments_by_department.map((d) => ({ name: d.department, value: d.count }));
  const statusData = data.appointments_by_status.map((d) => ({ name: d.status, value: d.count }));
  const severityData = data.escalation_stats.by_severity.map((d) => ({ name: d.severity, value: d.count }));
  const insuranceData = data.insurance_eligibility_outcomes.map((d) => ({ name: d.status, value: d.count }));
  const dayData = data.busiest_days.map((d) => ({ name: d.day?.slice(0, 10) ?? "?", count: d.count }));

  function Card({ title, children }: { title: string; children: React.ReactNode }) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-3 text-sm font-semibold text-slate-700">{title}</h3>
        {children}
      </div>
    );
  }

  function Empty() {
    return <p className="text-xs text-slate-400 italic">{t("dashboard.no_data")}</p>;
  }

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <h1 className="mb-6 text-xl font-bold text-slate-800">{t("dashboard.title")}</h1>

      {/* KPI row */}
      <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
        <KpiCard label={t("dashboard.total_appts")} value={data.document_completion.total_appointments} />
        <KpiCard label={t("dashboard.with_docs")} value={data.document_completion.appointments_with_documents} />
        <KpiCard label={t("dashboard.escalations")} value={data.escalation_stats.total} />
        <KpiCard label={t("dashboard.avg_booking")} value={`${Math.round(data.avg_request_to_booking.average_seconds)}s`} sub={`${data.avg_request_to_booking.sample_count} ${t("dashboard.samples")}`} />
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        {/* Appointments by Department */}
        <Card title={t("dashboard.appt_by_dept")}>
          {deptData.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={deptData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#0d9488" radius={[4, 4, 0, 0]} animationDuration={800} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Appointments by Status */}
        <Card title={t("dashboard.appt_by_status")}>
          {statusData.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={statusData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={(p) => `${p.name ?? ""} ${((p.percent ?? 0) * 100).toFixed(0)}%`} animationDuration={800}>
                  {statusData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Insurance Eligibility */}
        <Card title={t("dashboard.insurance_outcomes")}>
          {insuranceData.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={insuranceData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Bar dataKey="value" fill="#8b5cf6" radius={[4, 4, 0, 0]} animationDuration={800} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Escalation Severity */}
        <Card title={t("dashboard.escalations")}>
          {severityData.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={severityData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={80} label={(p) => `${p.name ?? ""} ${((p.percent ?? 0) * 100).toFixed(0)}%`} animationDuration={800}>
                  {severityData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Legend />
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Busiest Days */}
        <Card title={t("dashboard.busiest_days")}>
          {dayData.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={dayData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis allowDecimals={false} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Line type="monotone" dataKey="count" stroke="#06b6d4" strokeWidth={2} dot={{ r: 4 }} animationDuration={800} />
              </LineChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>

        {/* Busiest Doctors */}
        <Card title={t("dashboard.busiest_doctors")}>
          {data.busiest_doctors.length ? (
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={data.busiest_doctors.map((d) => ({ name: d.doctor, value: d.appointment_count }))} layout="vertical" margin={{ top: 5, right: 10, left: 60, bottom: 5 }}>
                <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                <YAxis type="category" dataKey="name" tick={{ fontSize: 10 }} width={80} />
                <Tooltip />
                <Bar dataKey="value" fill="#f59e0b" radius={[0, 4, 4, 0]} animationDuration={800} />
              </BarChart>
            </ResponsiveContainer>
          ) : <Empty />}
        </Card>
      </div>

      {/* Document completion footer */}
      <div className="mt-6 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <h3 className="mb-2 text-sm font-semibold text-slate-700">{t("dashboard.doc_completion")}</h3>
        <div className="flex gap-8 text-sm text-slate-600">
          <span>{t("dashboard.total_appts")}: <strong>{data.document_completion.total_appointments}</strong></span>
          <span>{t("dashboard.with_docs")}: <strong>{data.document_completion.appointments_with_documents}</strong></span>
          <span>{t("dashboard.rate")}: <strong>{data.document_completion.completion_rate_pct}%</strong></span>
          <span>Duplicates: <strong>{data.document_completion.duplicate_documents}</strong> ({data.document_completion.duplicate_rate_pct}%)</span>
        </div>
      </div>
    </div>
  );
}

function KpiCard({ label, value, sub }: { label: string; value: string | number; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-xl font-bold text-teal-700">{value}</p>
      {sub && <p className="text-xs text-slate-400">{sub}</p>}
    </div>
  );
}
