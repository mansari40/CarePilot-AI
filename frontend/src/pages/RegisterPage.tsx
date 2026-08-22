import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import LanguageSelector from "../components/LanguageSelector";

export default function RegisterPage() {
  const { t } = useTranslation();
  const { register } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [lang, setLang] = useState("en");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await register(fullName, email, password, lang);
      window.location.href = "/";
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t("register.error_exists"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm">
      <h1 className="mb-6 text-center text-xl font-semibold text-slate-800">
        {t("register.title")}
      </h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <input
          type="text"
          placeholder={t("register.full_name")}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          required
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
        />
        <input
          type="email"
          placeholder={t("register.email")}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
        />
        <input
          type="password"
          placeholder={t("register.password")}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
        />
        <LanguageSelector value={lang} onChange={setLang} />
        {error && <p className="text-xs text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? "…" : t("register.submit")}
        </button>
      </form>
      <p className="mt-4 text-center text-xs text-slate-500">
        {t("register.has_account")}{" "}
        <a href="/login" className="text-teal-600 hover:underline">
          {t("register.login_link")}
        </a>
      </p>
    </div>
  );
}
