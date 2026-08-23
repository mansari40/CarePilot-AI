const BASE = "/api";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("carepilot_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...init?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Auth
export const authApi = {
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),
  register: (data: { email: string; password: string; full_name: string; role: string; preferred_language: string }) =>
    request<{ id: number; email: string; full_name: string; role: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify(data),
    }),
};

// Patient profile
export const patientApi = {
  getMe: () => request<any>("/patients/me"),
  patchMe: (data: Record<string, any>) =>
    request<any>("/patients/me", { method: "PATCH", body: JSON.stringify(data) }),
  getAppointments: () => request<any[]>("/patients/me/appointments"),
  getDocuments: () => request<any[]>("/patients/me/documents"),
  uploadDocument: async (file: File, documentType: string = "other"): Promise<any> => {
    const token = localStorage.getItem("carepilot_token");
    const form = new FormData();
    form.append("file", file);
    form.append("document_type", documentType);
    const res = await fetch(`${BASE}/patients/me/documents`, {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || `Upload failed (${res.status})`);
    }
    return res.json();
  },
  getReminders: () => request<any[]>("/patients/me/reminders"),
  getInsurance: () => request<any[]>("/patients/me/insurance"),
  getEligibility: () => request<any[]>("/patients/me/eligibility"),
  getBilling: () => request<any[]>("/patients/me/billing"),
  deleteDocument: (docId: number) =>
    request<void>(`/patients/me/documents/${docId}`, { method: "DELETE" }),
  cancelAppointment: (apptId: number) =>
    request<any>(`/patients/me/appointments/${apptId}/cancel`, { method: "POST" }),
};

// Workflows
export const workflowApi = {
  list: (limit = 50) => request<any[]>(`/workflows/?limit=${limit}`),
  get: (id: number) => request<any>(`/workflows/${id}`),
  run: (patient_id: number, request_text: string, document_id?: number) =>
    request<any>("/workflows/run", {
      method: "POST",
      body: JSON.stringify({ patient_id, request_text, document_id }),
    }),
  resume: (run_id: number, message: string, document_id?: number) =>
    request<any>(`/workflows/${run_id}/resume`, {
      method: "POST",
      body: JSON.stringify({ message, document_id }),
    }),
  hide: (run_id: number) =>
    request<any>(`/workflows/${run_id}/hide`, {
      method: "PATCH",
      body: JSON.stringify({ hidden: true }),
    }),
};

// Staff
export const staffApi = {
  getDepartments: () => request<any[]>("/staff/departments"),
  createDepartment: (data: any) =>
    request<any>("/staff/departments", { method: "POST", body: JSON.stringify(data) }),
  updateDepartment: (id: number, data: any) =>
    request<any>(`/staff/departments/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  getDoctors: () => request<any[]>("/staff/doctors"),
  createDoctor: (data: any) =>
    request<any>("/staff/doctors", { method: "POST", body: JSON.stringify(data) }),
  updateDoctor: (id: number, data: any) =>
    request<any>(`/staff/doctors/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
  getSlots: () => request<any[]>("/staff/slots"),
  createSlot: (data: any) =>
    request<any>("/staff/slots", { method: "POST", body: JSON.stringify(data) }),
};

// Escalations
export const escalationApi = {
  list: () => request<any[]>("/escalations/"),
  get: (id: number) => request<any>(`/escalations/${id}`),
  resolve: (id: number, resolution_notes: string) =>
    request<any>(`/escalations/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify({ resolution_notes }),
    }),
};

// Analytics
export const analyticsApi = {
  dashboard: () => request<any>("/analytics/dashboard"),
};

// Audit
export const auditApi = {
  list: (limit = 50) => request<any[]>(`/audit/?limit=${limit}`),
};
