import { createContext, useContext, useState, useEffect, type ReactNode } from "react";

interface User {
  id: number;
  email: string;
  full_name: string;
  role: string;
  preferred_language?: string;
}

interface AuthCtx {
  user: User | null;
  token: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (full_name: string, email: string, password: string, preferred_language: string) => Promise<void>;
  logout: () => void;
  patchProfile: (data: Record<string, unknown>) => Promise<void>;
}

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("carepilot_token"));

  useEffect(() => {
    if (token) fetchProfile(token);
  }, []);

  async function fetchProfile(t: string) {
    const res = await fetch("/api/patients/me", { headers: { Authorization: `Bearer ${t}` } });
    if (res.ok) setUser(await res.json());
    else { setToken(null); localStorage.removeItem("carepilot_token"); }
  }

  async function login(email: string, password: string) {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error("Invalid credentials");
    const data = await res.json();
    setToken(data.access_token);
    localStorage.setItem("carepilot_token", data.access_token);
    await fetchProfile(data.access_token);
  }

  async function register(full_name: string, email: string, password: string, preferred_language: string) {
    const res = await fetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ full_name, email, password, role: "patient", preferred_language }),
    });
    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      throw new Error(d.detail || "Registration failed");
    }
    await login(email, password);
  }

  function logout() {
    setUser(null);
    setToken(null);
    localStorage.removeItem("carepilot_token");
  }

  async function patchProfile(data: Record<string, unknown>) {
    const res = await fetch("/api/patients/me", {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error("Patch failed");
    setUser(await res.json());
  }

  return (
    <AuthContext.Provider value={{ user, token, login, register, logout, patchProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
