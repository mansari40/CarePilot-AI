import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import { motion, AnimatePresence } from "framer-motion";
import {
  List,
  X,
  House,
  PaperPlaneRight,
  CalendarCheck,
  FolderOpen,
  Bell,
  ShieldCheck,
  Receipt,
  ArrowsClockwise,
  Wrench,
  WarningCircle,
  ClockCounterClockwise,
  ChartBar,
  SignOut,
  Globe,
  CaretDown,
  FirstAid,
} from "phosphor-react";
import { useLocation } from "react-router-dom";

const LANGS = ["en", "es", "fr", "prs", "ps"] as const;

const patientLinks = [
  { href: "/", labelKey: "nav.home", icon: House },
  { href: "/request", labelKey: "nav.request", icon: PaperPlaneRight },
  { href: "/appointments", labelKey: "nav.appointments", icon: CalendarCheck },
  { href: "/documents", labelKey: "nav.documents", icon: FolderOpen },
  { href: "/reminders", labelKey: "nav.reminders", icon: Bell },
  { href: "/insurance", labelKey: "nav.insurance", icon: ShieldCheck },
  { href: "/billing", labelKey: "nav.billing", icon: Receipt },
];

const staffLinks = [
  { href: "/", labelKey: "nav.home", icon: House },
  { href: "/workflows", labelKey: "nav.workflows", icon: ArrowsClockwise },
  { href: "/manage", labelKey: "nav.manage", icon: Wrench },
  { href: "/escalations", labelKey: "nav.escalations", icon: WarningCircle },
  { href: "/audit", labelKey: "nav.audit", icon: ClockCounterClockwise },
  { href: "/dashboard", labelKey: "nav.dashboard", icon: ChartBar },
];

export default function Navbar() {
  const { t, i18n } = useTranslation();
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [langOpen, setLangOpen] = useState(false);
  const location = useLocation();

  const isStaff = user?.role === "staff";
  const links = isStaff ? staffLinks : patientLinks;
  const brandColor = isStaff ? "text-indigo-700" : "text-blue-700";
  const activeBg = isStaff ? "bg-indigo-50 text-indigo-700" : "bg-blue-50 text-blue-700";
  const activeBorder = isStaff ? "border-indigo-600" : "border-blue-600";
  const hoverBg = isStaff ? "hover:bg-indigo-50/50" : "hover:bg-blue-50/50";

  function switchLang(lang: string) {
    i18n.changeLanguage(lang);
    localStorage.setItem("carepilot_lang", lang);
    setLangOpen(false);
  }

  return (
    <nav className="sticky top-0 z-50 border-b border-slate-200/80 bg-white/80 backdrop-blur-lg">
      <div className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:px-6">
        {/* Brand */}
        <a href="/" className="flex items-center gap-2">
          <FirstAid weight="fill" className={`h-6 w-6 ${brandColor}`} />
          <span className={`text-lg font-bold tracking-tight ${brandColor}`}>
            CarePilot
          </span>
        </a>

        {/* Desktop nav */}
        {user?.role && (
          <div className="hidden items-center gap-1 md:flex">
            {links.map((l) => {
              const Icon = l.icon;
              const isActive = location.pathname === l.href;
              return (
                <a
                  key={l.href}
                  href={l.href}
                  className={`flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-150 ${
                    isActive
                      ? `${activeBg} border-l-2 ${activeBorder} -ml-0.5 pl-3.5`
                      : `text-slate-600 ${hoverBg}`
                  }`}
                >
                  <Icon weight={isActive ? "fill" : "regular"} className="h-4 w-4" />
                  {t(l.labelKey)}
                </a>
              );
            })}
          </div>
        )}

        {/* Right side */}
        <div className="flex items-center gap-2">
          {/* Language selector */}
          <div className="relative">
            <button
              onClick={() => setLangOpen(!langOpen)}
              className="flex items-center gap-1 rounded-lg px-2.5 py-1.5 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-100"
            >
              <Globe className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{i18n.language.slice(0, 2).toUpperCase()}</span>
              <CaretDown className={`h-3 w-3 transition-transform ${langOpen ? "rotate-180" : ""}`} />
            </button>
            <AnimatePresence>
              {langOpen && (
                <motion.div
                  initial={{ opacity: 0, y: -4, scale: 0.95 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -4, scale: 0.95 }}
                  transition={{ duration: 0.15 }}
                  className="absolute right-0 top-full z-50 mt-1 w-36 overflow-hidden rounded-xl border border-slate-200 bg-white shadow-lg"
                >
                  {LANGS.map((l) => (
                    <button
                      key={l}
                      onClick={() => switchLang(l)}
                      className={`flex w-full items-center px-3 py-2 text-left text-sm transition-colors ${
                        i18n.language.startsWith(l)
                          ? `${activeBg} font-medium`
                          : "text-slate-600 hover:bg-slate-50"
                      }`}
                    >
                      {t(`languages.${l}`)}
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {user?.role ? (
            <>
              {/* Logout */}
              <button
                onClick={logout}
                className="flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600"
              >
                <SignOut className="h-4 w-4" />
                <span className="hidden sm:inline">{t("nav.logout")}</span>
              </button>

              {/* Mobile hamburger */}
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="rounded-lg p-1.5 text-slate-600 transition-colors hover:bg-slate-100 md:hidden"
                aria-label="Toggle menu"
              >
                {menuOpen ? <X className="h-5 w-5" /> : <List className="h-5 w-5" />}
              </button>
            </>
          ) : (
            <div className="flex items-center gap-1">
              <a href="/login" className="rounded-lg px-3 py-1.5 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-100">
                {t("nav.login")}
              </a>
              <a
                href="/register"
                className={`rounded-lg px-3 py-1.5 text-sm font-medium text-white transition-colors ${
                  isStaff ? "bg-indigo-600 hover:bg-indigo-700" : "bg-blue-600 hover:bg-blue-700"
                }`}
              >
                {t("nav.register")}
              </a>
            </div>
          )}
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {menuOpen && user && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-slate-100 md:hidden"
          >
            <div className="flex flex-col gap-1 px-4 py-3">
              {links.map((l) => {
                const Icon = l.icon;
                const isActive = location.pathname === l.href;
                return (
                  <a
                    key={l.href}
                    href={l.href}
                    onClick={() => setMenuOpen(false)}
                    className={`flex items-center gap-2 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${
                      isActive ? activeBg : `text-slate-600 ${hoverBg}`
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {t(l.labelKey)}
                  </a>
                );
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </nav>
  );
}
