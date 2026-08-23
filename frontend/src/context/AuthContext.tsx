import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from "react";
import i18n from "../i18n";

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
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (full_name: string, email: string, password: string, preferred_language: string) => Promise<void>;
  logout: () => void;
  patchProfile: (data: Record<string, unknown>) => Promise<void>;
}

const AuthContext = createContext<AuthCtx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("carepilot_token"));
  const [loading, setLoading] = useState(true);

  const fetchProfile = useCallback(async (t: string) => {
    try {
      const res = await fetch("/api/auth/me", { headers: { Authorization: `Bearer ${t}` } });
      if (res.ok) {
        setUser(await res.json());
      } else {
        setToken(null);
        localStorage.removeItem("carepilot_token");
        setUser(null);
      }
    } catch {
      setToken(null);
      localStorage.removeItem("carepilot_token");
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (token) {
      fetchProfile(token);
    } else {
      setLoading(false);
    }
  }, [token, fetchProfile]);

  async function login(email: string, password: string) {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error(i18n.t("login.error_invalid"));
    const data = await res.json();
    localStorage.setItem("carepilot_token", data.access_token);
    setToken(data.access_token);
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
      throw new Error(d.detail || i18n.t("register.error_failed"));
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
    if (!res.ok) throw new Error(i18n.t("profile.error_patch"));
    setUser(await res.json());
  }

  return (
    <AuthContext.Provider value={{ user, token, loading, login, register, logout, patchProfile }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be inside AuthProvider");
  return ctx;
}
