import { useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, useInView } from "framer-motion";
import { useTranslation } from "react-i18next";
import { useAuth } from "../context/AuthContext";
import Footer from "../components/Footer";
import {
  FirstAid,
  ChatCircle,
  MagnifyingGlass,
  CalendarPlus,
  FileText,
  Bell,
  ShieldCheck,
  CalendarCheck,
  Receipt,
  Globe,
  ArrowRight,
} from "phosphor-react";

function FadeIn({
  children,
  delay = 0,
  className,
}: {
  children: React.ReactNode;
  delay?: number;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: "-60px" });

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 24 }}
      animate={isInView ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
      transition={{ duration: 0.5, delay, ease: "easeOut" }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

export default function HomePage() {
  const { t } = useTranslation();
  const { user } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (user?.role === "staff") {
      navigate("/workflows", { replace: true });
    }
  }, [user, navigate]);

  if (user?.role === "staff") return null;

  const steps = [
    {
      icon: ChatCircle,
      title: t("home.step1_title"),
      description: t("home.step1_desc"),
    },
    {
      icon: MagnifyingGlass,
      title: t("home.step2_title"),
      description: t("home.step2_desc"),
    },
    {
      icon: CalendarPlus,
      title: t("home.step3_title"),
      description: t("home.step3_desc"),
    },
    {
      icon: FileText,
      title: t("home.step4_title"),
      description: t("home.step4_desc"),
    },
    {
      icon: Bell,
      title: t("home.step5_title"),
      description: t("home.step5_desc"),
    },
    {
      icon: ShieldCheck,
      title: t("home.step6_title"),
      description: t("home.step6_desc"),
    },
  ];

  const features = [
    {
      icon: CalendarCheck,
      color: "bg-blue-50 text-blue-600",
      title: t("home.feature_booking_title"),
      description: t("home.feature_booking_desc"),
    },
    {
      icon: FileText,
      color: "bg-emerald-50 text-emerald-600",
      title: t("home.feature_docs_title"),
      description: t("home.feature_docs_desc"),
    },
    {
      icon: ShieldCheck,
      color: "bg-violet-50 text-violet-600",
      title: t("home.feature_insurance_title"),
      description: t("home.feature_insurance_desc"),
    },
    {
      icon: Receipt,
      color: "bg-orange-50 text-orange-600",
      title: t("home.feature_billing_title"),
      description: t("home.feature_billing_desc"),
    },
    {
      icon: Bell,
      color: "bg-amber-50 text-amber-600",
      title: t("home.feature_reminders_title"),
      description: t("home.feature_reminders_desc"),
    },
    {
      icon: Globe,
      color: "bg-cyan-50 text-cyan-600",
      title: t("home.feature_multilingual_title"),
      description: t("home.feature_multilingual_desc"),
    },
  ];

  return (
    <>
    <div className="space-y-24 py-16">
      {/* Hero */}
      <section className="bg-gradient-to-br from-blue-50/80 via-white to-slate-50">
        <div className="mx-auto max-w-4xl px-4 text-center sm:px-6 lg:px-8">
          <FadeIn>
            <span className="inline-flex items-center gap-2 rounded-full bg-blue-50 px-4 py-1.5 text-sm font-medium text-blue-600 ring-1 ring-blue-600/10">
              <FirstAid className="h-4 w-4" />
              {t("home.badge")}
            </span>
          </FadeIn>

          <FadeIn delay={0.1}>
            <h1 className="mt-6 font-heading text-4xl font-bold tracking-tight text-slate-900 sm:text-5xl">
              {t("home.hero_title")}
            </h1>
          </FadeIn>

          <FadeIn delay={0.2}>
            <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-600">
              {t("home.hero_description")}
            </p>
          </FadeIn>

          <FadeIn delay={0.3}>
            <div className="mt-8 flex items-center justify-center gap-4">
              {user ? (
                <>
                  <Link
                    to="/request"
                    className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md active:scale-[0.98]"
                  >
                    {t("home.cta_request")}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <a
                    href="#how-it-works"
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:shadow-md active:scale-[0.98]"
                  >
                    {t("home.cta_how")}
                  </a>
                </>
              ) : (
                <>
                  <Link
                    to="/register"
                    className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md active:scale-[0.98]"
                  >
                    {t("home.cta_started")}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <a
                    href="#how-it-works"
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:shadow-md active:scale-[0.98]"
                  >
                    {t("home.cta_learn")}
                  </a>
                </>
              )}
            </div>
          </FadeIn>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <FadeIn>
            <div className="text-center">
              <h2 className="font-heading text-3xl font-bold tracking-tight text-slate-900">
                {t("home.how_title")}
              </h2>
              <p className="mt-3 text-lg text-slate-500">
                {t("home.how_subtitle")}
              </p>
            </div>
          </FadeIn>

          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {steps.map((step, i) => (
              <FadeIn key={step.title} delay={i * 0.08}>
                <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm ring-1 ring-slate-900/5">
                  <div className="flex items-center gap-4">
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-blue-50 text-sm font-bold text-blue-600">
                      {i + 1}
                    </div>
                    <step.icon className="h-6 w-6 text-blue-500" />
                  </div>
                  <h3 className="mt-4 font-heading text-base font-semibold text-slate-900">
                    {step.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-500">
                    {step.description}
                  </p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* What CarePilot Handles */}
      <section className="px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-6xl">
          <FadeIn>
            <div className="text-center">
              <h2 className="font-heading text-3xl font-bold tracking-tight text-slate-900">
                {t("home.features_title")}
              </h2>
              <p className="mt-3 text-lg text-slate-500">
                {t("home.features_subtitle")}
              </p>
            </div>
          </FadeIn>

          <div className="mt-12 grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {features.map((feature, i) => (
              <FadeIn key={feature.title} delay={i * 0.08}>
                <div className="rounded-2xl border border-slate-200/80 bg-white p-6 shadow-sm ring-1 ring-slate-900/5">
                  <div
                    className={`flex h-12 w-12 items-center justify-center rounded-xl ${feature.color}`}
                  >
                    <feature.icon className="h-6 w-6" />
                  </div>
                  <h3 className="mt-4 font-heading text-base font-semibold text-slate-900">
                    {feature.title}
                  </h3>
                  <p className="mt-2 text-sm leading-relaxed text-slate-500">
                    {feature.description}
                  </p>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="px-4 sm:px-6 lg:px-8">
        <div className="mx-auto max-w-4xl rounded-3xl bg-blue-50 px-6 py-16 text-center sm:px-12">
          <FadeIn>
            <h2 className="font-heading text-3xl font-bold tracking-tight text-slate-900">
              {t("home.cta_title")}
            </h2>
            <p className="mx-auto mt-4 max-w-xl text-lg text-slate-600">
              {t("home.cta_desc")}
            </p>
            <div className="mt-8 flex items-center justify-center gap-4">
              {user ? (
                <Link
                  to="/request"
                  className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md active:scale-[0.98]"
                >
                  {t("home.cta_request")}
                  <ArrowRight className="h-4 w-4" />
                </Link>
              ) : (
                <>
                  <Link
                    to="/register"
                    className="inline-flex items-center gap-2 rounded-xl bg-blue-600 px-6 py-3 text-sm font-semibold text-white shadow-sm transition-all hover:bg-blue-700 hover:shadow-md active:scale-[0.98]"
                  >
                    {t("home.cta_create")}
                    <ArrowRight className="h-4 w-4" />
                  </Link>
                  <Link
                    to="/login"
                    className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-6 py-3 text-sm font-semibold text-slate-700 shadow-sm transition-all hover:bg-slate-50 hover:shadow-md active:scale-[0.98]"
                  >
                    {t("home.cta_signin")}
                  </Link>
                </>
              )}
            </div>
          </FadeIn>
        </div>
      </section>
    </div>
    <Footer />
    </>
  );
}
