import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import LanguageDetector from "i18next-browser-languagedetector";

import en from "./en.json";
import es from "./es.json";
import fr from "./fr.json";
import prs from "./prs.json";
import ps from "./ps.json";

const RTL_LANGUAGES = ["prs", "ps", "ar", "fa", "ur", "he"];

function setDirection(lang: string) {
  const dir = RTL_LANGUAGES.includes(lang) ? "rtl" : "ltr";
  document.documentElement.dir = dir;
  document.documentElement.lang = lang;
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      es: { translation: es },
      fr: { translation: fr },
      prs: { translation: prs },
      ps: { translation: ps },
    },
    fallbackLng: "en",
    interpolation: { escapeValue: false },
    detection: {
      order: ["localStorage", "navigator"],
      lookupLocalStorage: "carepilot_lang",
    },
  });

// Set initial direction
setDirection(i18n.language || "en");

// Update direction on language change
i18n.on("languageChanged", (lang) => {
  setDirection(lang);
});

export default i18n;
