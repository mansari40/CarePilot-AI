import { useTranslation } from "react-i18next";

export default function LanguageSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (lang: string) => void;
}) {
  const { t } = useTranslation();
  const LANGS = ["en", "es", "fr", "prs", "ps"] as const;

  return (
    <div>
      <label className="mb-1.5 block text-sm font-medium text-slate-700">
        {t("register.language")}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-xl border border-slate-300 bg-slate-50/50 px-3 py-2.5 text-sm transition-colors focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
      >
        {LANGS.map((l) => (
          <option key={l} value={l}>
            {t(`languages.${l}`)}
          </option>
        ))}
      </select>
    </div>
  );
}
