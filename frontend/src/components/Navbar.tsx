import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";

const LANGS = ["en", "es", "fr", "ar", "hi", "ur"] as const;

export default function Navbar() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();

  function switchLang(lang: string) {
    i18n.changeLanguage(lang);
    localStorage.setItem("carepilot_lang", lang);
    document.documentElement.dir = ["ar", "ur"].includes(lang) ? "rtl" : "ltr";
  }

  return (
    <nav className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3 text-sm">
      <span className="font-semibold text-teal-700">{t("nav.home")}</span>
      <div className="flex items-center gap-4">
        <select
          value={i18n.language.slice(0, 2)}
          onChange={(e) => switchLang(e.target.value)}
          className="rounded border border-slate-300 bg-white px-2 py-1 text-xs"
          aria-label="Language selector"
        >
          {LANGS.map((l) => (
            <option key={l} value={l}>
              {t(`languages.${l}`)}
            </option>
          ))}
        </select>
        {user ? (
          <>
            {user.role === "staff" && (
              <a href="/dashboard" className="text-slate-600 hover:text-teal-600">
                {t("nav.dashboard")}
              </a>
            )}
            <a href="/profile" className="text-slate-600 hover:text-teal-600">
              {t("nav.profile")}
            </a>
            <button onClick={logout} className="text-slate-600 hover:text-red-600">
              {t("nav.logout")}
            </button>
          </>
        ) : (
          <>
            <a href="/login" className="text-slate-600 hover:text-teal-600">
              {t("nav.login")}
            </a>
            <a href="/register" className="text-slate-600 hover:text-teal-600">
              {t("nav.register")}
            </a>
          </>
        )}
      </div>
    </nav>
  );
}
