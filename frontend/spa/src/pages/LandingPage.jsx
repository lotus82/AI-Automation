import { Link } from "react-router-dom";
import {
  BarChart3,
  Bot,
  GraduationCap,
  MessageSquare,
  Mic,
  Plug,
  Shield,
  Sparkles,
  TrendingUp,
} from "lucide-react";

const features = [
  {
    icon: BarChart3,
    title: "QA-аналитика и ОКК",
    text: "Реестр звонков и чатов, оценка диалогов, рекомендации по методикам BANT и MEDDIC.",
  },
  {
    icon: GraduationCap,
    title: "ИИ-тренер",
    text: "Сценарии и голосовой тренажёр: отработка возражений и разбор сессий с ИИ-клиентом.",
  },
  {
    icon: TrendingUp,
    title: "Лидогенерация и телефония",
    text: "Исходящие кампании, интеграция с Asterisk и голосовой агент для первой линии.",
  },
  {
    icon: MessageSquare,
    title: "Мессенджеры",
    text: "MAX, Telegram и единая память диалогов с мониторингом сессий в реальном времени.",
  },
  {
    icon: Plug,
    title: "Интеграции",
    text: "Битрикс24, конструктор внешних API и настройка каналов без лишней рутины.",
  },
  {
    icon: Mic,
    title: "Голос и телефония",
    text: "Потоковое распознавание и синтез, тест голосового агента из панели.",
  },
];

export function LandingPage() {
  return (
    <div className="min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-slate-100">
      <header className="border-b border-slate-800/80 bg-slate-950/70 backdrop-blur-md">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4 sm:px-6">
          <div className="flex items-center gap-2">
            <Sparkles className="h-8 w-8 text-emerald-400" strokeWidth={1.75} aria-hidden />
            <span className="text-lg font-semibold tracking-tight text-white">Sales AI</span>
          </div>
          <Link
            to="/login"
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-emerald-900/30 transition hover:bg-emerald-500"
          >
            Войти
          </Link>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_80%_50%_at_50%_-20%,rgba(16,185,129,0.18),transparent)]" />
        <div className="relative mx-auto max-w-6xl px-4 py-16 sm:px-6 sm:py-24">
          <p className="mb-3 text-center text-sm font-medium uppercase tracking-widest text-emerald-400/90">
            Платформа для продаж с ИИ
          </p>
          <h1 className="mx-auto max-w-4xl text-center text-4xl font-bold leading-tight text-white sm:text-5xl md:text-6xl">
            Обучайте команду, контролируйте качество и подключайте каналы в одном месте
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-center text-lg text-slate-400">
            Корпоративный портал с разграничением по организациям и ролям: главный администратор выдаёт доступ
            компаниям, внутри компании — администратор, директор и сотрудники с гибкими правами на разделы.
          </p>
          <div className="mt-10 flex flex-wrap items-center justify-center gap-4">
            <Link
              to="/login"
              className="inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-8 py-3.5 text-base font-semibold text-white shadow-xl shadow-emerald-900/40 transition hover:bg-emerald-500"
            >
              <Shield className="h-5 w-5" aria-hidden />
              Войти в панель
            </Link>
            <span className="text-sm text-slate-500">Свободной регистрации нет — доступ выдаёт администратор.</span>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-6xl border-t border-slate-800/80 px-4 py-16 sm:px-6">
        <div className="mb-10 text-center">
          <h2 className="text-2xl font-bold text-white sm:text-3xl">Возможности платформы</h2>
          <p className="mt-2 text-slate-400">Краткий обзор модулей, доступных после входа (по правам вашей роли).</p>
        </div>
        <ul className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {features.map(({ icon: Icon, title, text }) => (
            <li
              key={title}
              className="rounded-2xl border border-slate-700/60 bg-slate-900/40 p-6 shadow-lg backdrop-blur-sm transition hover:border-emerald-500/30"
            >
              <Icon className="mb-4 h-10 w-10 text-emerald-400" strokeWidth={1.5} aria-hidden />
              <h3 className="text-lg font-semibold text-white">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="border-t border-slate-800/80 bg-slate-900/30 py-12">
        <div className="mx-auto max-w-6xl px-4 text-center sm:px-6">
          <Bot className="mx-auto mb-4 h-12 w-12 text-slate-500" strokeWidth={1.25} aria-hidden />
          <p className="text-sm text-slate-500">
            © {new Date().getFullYear()} Sales AI · Внутренняя корпоративная система
          </p>
        </div>
      </section>
    </div>
  );
}
