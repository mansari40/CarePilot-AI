import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import LanguageSelector from "../components/LanguageSelector";

export default function ProfilePage() {
  const { t, i18n } = useTranslation();
  const { user, patchProfile } = useAuth();
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [lang, setLang] = useState("en");
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (user) {
      setFullName(user.full_name);
      setLang(user.preferred_language || "en");
    }
  }, [user]);

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setSaved(false);
    try {
      await patchProfile({ full_name: fullName, phone, preferred_language: lang });
      i18n.changeLanguage(lang);
      localStorage.setItem("carepilot_lang", lang);
      document.documentElement.dir = ["ar", "ur"].includes(lang) ? "rtl" : "ltr";
      setSaved(true);
    } finally {
      setLoading(false);
    }
  }

  if (!user) return null;

  return (
    <div className="mx-auto mt-16 max-w-sm">
      <h1 className="mb-6 text-center text-xl font-semibold text-slate-800">
        {t("profile.title")}
      </h1>
      <form onSubmit={handleSave} className="flex flex-col gap-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("profile.full_name")}
          </label>
          <input
            type="text"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("profile.email")}
          </label>
          <input
            type="email"
            value={user.email}
            disabled
            className="w-full rounded border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-500"
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">
            {t("profile.phone")}
          </label>
          <input
            type="text"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            placeholder="+1 555-123-4567"
            className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
          />
        </div>
        <LanguageSelector value={lang} onChange={setLang} />
        {saved && <p className="text-xs text-green-600">{t("profile.saved")}</p>}
        <button
          type="submit"
          disabled={loading}
          className="rounded bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-700 disabled:opacity-50"
        >
          {loading ? "…" : t("profile.save")}
        </button>
      </form>
    </div>
  );
}
