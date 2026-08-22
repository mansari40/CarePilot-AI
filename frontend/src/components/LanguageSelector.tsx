import { useTranslation } from "react-i18next";

export default function LanguageSelector({
  value,
  onChange,
}: {
  value: string;
  onChange: (lang: string) => void;
}) {
  const { t } = useTranslation();
  const LANGS = ["en", "es", "fr", "ar", "hi", "ur"] as const;

  return (
    <div>
      <label className="mb-1 block text-sm font-medium text-slate-700">
        {t("register.language")}
      </label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-500 focus:outline-none"
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
