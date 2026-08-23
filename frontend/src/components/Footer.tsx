import { useTranslation } from "react-i18next";

export default function Footer() {
  const { t } = useTranslation();

  return (
    <footer className="border-t border-slate-200/80 bg-white">
      <div className="mx-auto max-w-7xl px-4 py-6 sm:px-6">
        <p className="text-justify text-xs leading-relaxed text-slate-400">
          {t("footer.disclaimer")}
        </p>
        <p className="mt-3 text-xs text-slate-400">
          &copy; 2026{" "}
          <a
            href="https://www.linkedin.com/in/mustafa-ansari-135b73353/"
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-500 transition-colors hover:text-blue-700 hover:underline"
          >
            Mustafa Ansari
          </a>
        </p>
      </div>
    </footer>
  );
}
