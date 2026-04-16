import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import {
  BookOpen,
  ChevronDown,
  ClipboardList,
  HeartPulse,
  ListChecks,
  Loader2,
  LogOut,
} from "lucide-react";
import patientMisClient from "../api/patientMisClient.js";
import { PatientAuthGuard } from "../components/mis/PatientAuthGuard.jsx";
import {
  clearPatientSession,
  getStoredPatientId,
  setPatientSession,
} from "../utils/patientMisAuth.js";

const card =
  "rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm shadow-slate-200/50 sm:p-5";

function formatDate(d) {
  if (!d) return "—";
  try {
    return new Date(d).toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
  } catch {
    return d;
  }
}

function birthDateInputValue(iso) {
  if (!iso) return "";
  const s = String(iso);
  return s.length >= 10 ? s.slice(0, 10) : s;
}

function formatPatientPatchError(err) {
  const det = err?.response?.data?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) return det.map((x) => (typeof x === "object" && x != null ? x.msg ?? x : x)).join("; ");
  return err?.message ?? "Ошибка сохранения";
}

function PatientMaxRegistrationForm({ draft, onSuccess }) {
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [confirmDoctor, setConfirmDoctor] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    const fn = fullName.trim();
    if (!fn) {
      setMsg("Укажите ФИО.");
      return;
    }
    const ph = phone.trim();
    if (!ph) {
      setMsg("Укажите телефон.");
      return;
    }
    if (!confirmDoctor) {
      setMsg("Подтвердите привязку к лечащему врачу.");
      return;
    }
    setBusy(true);
    setMsg("");
    try {
      const { data } = await patientMisClient.post("/mis/auth/max/register", {
        organization_id: draft.organizationId,
        init_data: draft.initData,
        full_name: fn,
        phone: ph,
        confirm_doctor: true,
      });
      if (data.access_token && data.patient_id) {
        setPatientSession(data.access_token, data.patient_id, data.organization_id);
        onSuccess(String(data.patient_id));
        return;
      }
      setMsg("Не удалось завершить регистрацию.");
    } catch (err) {
      const det = err?.response?.data?.detail;
      setMsg(
        Array.isArray(det)
          ? det.map((x) => x?.msg ?? x).join("; ")
          : typeof det === "string"
            ? det
            : err?.message || "Ошибка",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={card}>
      <h1 className="text-lg font-semibold text-slate-900">Регистрация</h1>
      <p className="mt-1 text-sm text-slate-600">
        Заполните данные для привязки аккаунта MAX к карте у выбранного врача.
      </p>
      <form onSubmit={submit} className="mt-4 space-y-3">
        <label className="block text-xs font-medium text-slate-600">
          ФИО
          <input
            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            autoComplete="name"
            required
          />
        </label>
        <label className="block text-xs font-medium text-slate-600">
          Телефон
          <input
            type="tel"
            className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
            value={phone}
            onChange={(e) => setPhone(e.target.value)}
            autoComplete="tel"
            placeholder="+7…"
            required
          />
        </label>
        <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-sm text-slate-800">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
            checked={confirmDoctor}
            onChange={(e) => setConfirmDoctor(e.target.checked)}
          />
          <span>Подтверждаю привязку к лечащему врачу из приглашения в MAX</span>
        </label>
        {msg ? <p className="text-sm text-red-700">{msg}</p> : null}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white shadow-md shadow-teal-600/25 disabled:opacity-50"
        >
          {busy ? "Сохранение…" : "Зарегистрироваться"}
        </button>
      </form>
    </div>
  );
}

function PatientCabinetContent({ patientId, maxSession, onLogout }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState("");
  const [dDate, setDDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [dMetric, setDMetric] = useState("");
  const [dValue, setDValue] = useState("");
  const [dBusy, setDBusy] = useState(false);
  const [dMsg, setDMsg] = useState("");

  const [profileFullName, setProfileFullName] = useState("");
  const [profileBirth, setProfileBirth] = useState("");
  const [profilePhone, setProfilePhone] = useState("");
  const [profileHeight, setProfileHeight] = useState("");
  const [profileWeight, setProfileWeight] = useState("");
  const [profileBusy, setProfileBusy] = useState(false);
  const [profileSaveMsg, setProfileSaveMsg] = useState("");
  const [profileErr, setProfileErr] = useState("");

  const [surveysOpen, setSurveysOpen] = useState(false);

  const load = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    setErr("");
    try {
      const res = await fetch(`/api/public/mis/patient/${encodeURIComponent(patientId)}`);
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(typeof j?.detail === "string" ? j.detail : `Ошибка ${res.status}`);
      }
      setData(await res.json());
    } catch (e) {
      setErr(e?.message ?? String(e));
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [patientId]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    const p = data?.patient;
    if (!p) return;
    setProfileFullName(p.full_name || "");
    setProfileBirth(birthDateInputValue(p.birth_date));
    setProfilePhone(p.phone || "");
    setProfileHeight(p.height != null && p.height !== "" ? String(p.height) : "");
    setProfileWeight(p.weight != null && p.weight !== "" ? String(p.weight) : "");
    setProfileSaveMsg("");
    setProfileErr("");
  }, [data]);

  const recentExams = useMemo(() => {
    const entries = data?.entries ?? [];
    return entries.filter((e) => e.type === "exam").slice(0, 8);
  }, [data?.entries]);

  const doctorQuestionnaires = useMemo(() => {
    const entries = data?.entries ?? [];
    return entries
      .filter((e) => e.type === "survey" && e.data?.source === "mis_questionnaire_invite")
      .slice()
      .sort((a, b) => {
        const da = new Date(a.entry_date || 0).getTime();
        const db = new Date(b.entry_date || 0).getTime();
        return db - da;
      })
      .slice(0, 12);
  }, [data?.entries]);

  const saveProfile = async (e) => {
    e.preventDefault();
    if (!maxSession) return;
    const fn = profileFullName.trim();
    if (!fn) {
      setProfileErr("Укажите ФИО.");
      setProfileSaveMsg("");
      return;
    }
    let heightVal = null;
    let weightVal = null;
    if (profileHeight.trim() !== "") {
      heightVal = parseFloat(String(profileHeight).replace(",", "."));
      if (!Number.isFinite(heightVal)) {
        setProfileErr("Укажите рост числом (см).");
        setProfileSaveMsg("");
        return;
      }
    }
    if (profileWeight.trim() !== "") {
      weightVal = parseFloat(String(profileWeight).replace(",", "."));
      if (!Number.isFinite(weightVal)) {
        setProfileErr("Укажите вес числом (кг).");
        setProfileSaveMsg("");
        return;
      }
    }

    setProfileBusy(true);
    setProfileErr("");
    setProfileSaveMsg("");
    try {
      await patientMisClient.patch("/mis/patient-session/me", {
        full_name: fn,
        phone: profilePhone.trim() || null,
        birth_date: profileBirth.trim() || null,
        height: heightVal,
        weight: weightVal,
      });
      setProfileSaveMsg("Данные сохранены.");
      await load();
    } catch (err) {
      setProfileErr(formatPatientPatchError(err));
    } finally {
      setProfileBusy(false);
    }
  };

  const submitDiary = async (e) => {
    e.preventDefault();
    if (!patientId) return;
    const metric = dMetric.trim();
    const value = dValue.trim();
    if (!metric || !value) {
      setDMsg("Укажите показатель и значение.");
      return;
    }
    setDBusy(true);
    setDMsg("");
    try {
      const res = await fetch(`/api/public/mis/patient/${encodeURIComponent(patientId)}/diary`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entry_date: dDate, metric, value }),
      });
      if (!res.ok) {
        const j = await res.json().catch(() => ({}));
        throw new Error(typeof j?.detail === "string" ? j.detail : `Ошибка ${res.status}`);
      }
      setDMetric("");
      setDValue("");
      setDMsg("Запись отправлена врачу.");
      await load();
    } catch (e) {
      setDMsg(e?.message ?? String(e));
    } finally {
      setDBusy(false);
    }
  };

  if (loading) {
    return (
      <div className={`${card} flex items-center justify-center gap-2 py-16 text-slate-500`}>
        <Loader2 className="h-6 w-6 animate-spin text-teal-600" aria-hidden />
        Загрузка…
      </div>
    );
  }

  if (err) {
    return (
      <div className={`${card} border-red-200 bg-red-50/80 text-red-800`}>
        <p className="font-medium">Не удалось открыть карту</p>
        <p className="mt-1 text-sm">{err}</p>
        {maxSession ? (
          <button
            type="button"
            className="mt-3 text-sm font-medium text-teal-800 underline"
            onClick={onLogout}
          >
            Выйти и войти снова
          </button>
        ) : null}
      </div>
    );
  }

  const p = data?.patient;

  return (
    <div className="space-y-4 pb-24 sm:space-y-6 sm:pb-12">
      <section className={card}>
        <h1 className="text-lg font-semibold text-slate-900">Мои данные</h1>
        {maxSession ? (
          <>
            <p className="mt-1 text-xs text-slate-500">
              ФИО, дата рождения, телефон, рост и вес видны лечащему врачу. Диагноз и план лечения меняются только врачом.
            </p>
            <form className="mt-4 space-y-3" onSubmit={saveProfile}>
              <label className="block text-xs font-medium text-slate-600">
                ФИО
                <input
                  required
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
                  value={profileFullName}
                  onChange={(e) => setProfileFullName(e.target.value)}
                  autoComplete="name"
                />
              </label>
              <label className="block text-xs font-medium text-slate-600">
                Дата рождения
                <input
                  type="date"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
                  value={profileBirth}
                  onChange={(e) => setProfileBirth(e.target.value)}
                />
              </label>
              <label className="block text-xs font-medium text-slate-600">
                Телефон
                <input
                  type="tel"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
                  value={profilePhone}
                  onChange={(e) => setProfilePhone(e.target.value)}
                  autoComplete="tel"
                  placeholder="+7…"
                />
              </label>
              <div className="grid gap-3 sm:grid-cols-2">
                <label className="block text-xs font-medium text-slate-600">
                  Рост (см)
                  <input
                    type="number"
                    step="0.1"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
                    value={profileHeight}
                    onChange={(e) => setProfileHeight(e.target.value)}
                    placeholder="например 175"
                  />
                </label>
                <label className="block text-xs font-medium text-slate-600">
                  Вес (кг)
                  <input
                    type="number"
                    step="0.1"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
                    value={profileWeight}
                    onChange={(e) => setProfileWeight(e.target.value)}
                    placeholder="например 72"
                  />
                </label>
              </div>
              {profileErr ? <p className="text-sm text-red-700">{profileErr}</p> : null}
              {profileSaveMsg ? <p className="text-sm text-teal-800">{profileSaveMsg}</p> : null}
              <button
                type="submit"
                disabled={profileBusy}
                className="w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white shadow-md shadow-teal-600/25 disabled:opacity-50 sm:w-auto sm:px-8"
              >
                {profileBusy ? "Сохранение…" : "Сохранить изменения"}
              </button>
            </form>
            <button
              type="button"
              className="mt-4 hidden text-sm font-medium text-teal-700 underline sm:inline"
              onClick={onLogout}
            >
              Выйти
            </button>
          </>
        ) : (
          <>
            <p className="mt-1 text-sm text-slate-600">
              <span className="font-medium text-slate-800">{p?.full_name}</span>
            </p>
            <p className="mt-2 text-sm text-slate-600">
              Дата рождения: {formatDate(p?.birth_date)} · Тел.: {p?.phone || "—"}
            </p>
            <p className="mt-2 text-sm text-slate-600">
              Рост: {p?.height != null && p?.height !== "" ? `${p.height} см` : "—"} · Вес:{" "}
              {p?.weight != null && p?.weight !== "" ? `${p.weight} кг` : "—"}
            </p>
            <p className="mt-3 rounded-xl border border-amber-100 bg-amber-50/80 px-3 py-2 text-xs text-amber-900">
              Чтобы редактировать данные, откройте кабинет через мини-приложение MAX (вход по аккаунту мессенджера).
            </p>
          </>
        )}
      </section>

      <section className={card}>
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <ClipboardList className="h-5 w-5 shrink-0 text-teal-600" strokeWidth={1.75} aria-hidden />
          Последние обследования
        </h2>
        {recentExams.length === 0 ? (
          <p className="mt-3 text-sm text-slate-500">Пока нет записей обследований.</p>
        ) : (
          <ul className="mt-3 space-y-3">
            {recentExams.map((e) => (
              <li key={e.id} className="rounded-xl border border-slate-100 bg-slate-50/80 p-3 text-sm">
                <div className="flex flex-wrap justify-between gap-2 text-slate-700">
                  <span className="font-medium">{formatDate(e.entry_date)}</span>
                  <span className="rounded-full bg-teal-100 px-2 py-0.5 text-xs font-medium text-teal-800">
                    Обследование
                  </span>
                </div>
                {(e.conclusion || "").trim() ? (
                  <p className="mt-2 text-slate-700">{e.conclusion}</p>
                ) : null}
                {e.data && Object.keys(e.data).length > 0 ? (
                  <pre className="mt-2 max-h-40 overflow-auto rounded-lg bg-white p-2 text-xs text-slate-600 ring-1 ring-slate-100">
                    {JSON.stringify(e.data, null, 2)}
                  </pre>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className={card}>
        <button
          type="button"
          className="flex w-full items-center justify-between gap-2 text-left"
          onClick={() => setSurveysOpen((o) => !o)}
          aria-expanded={surveysOpen}
        >
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <ListChecks className="h-5 w-5 shrink-0 text-teal-600" strokeWidth={1.75} aria-hidden />
            Опросники от врача
          </h2>
          <span className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
            {doctorQuestionnaires.length ? `${doctorQuestionnaires.length} запис.` : "нет записей"}
            <ChevronDown
              className={`h-5 w-5 shrink-0 text-slate-400 transition-transform ${surveysOpen ? "rotate-180" : ""}`}
              aria-hidden
            />
          </span>
        </button>
        {surveysOpen ? (
          <>
            <p className="mt-2 text-xs text-slate-500">
              Здесь отображаются опросы, на которые вас направил лечащий врач через личные сообщения.
            </p>
            {doctorQuestionnaires.length === 0 ? (
              <p className="mt-3 text-sm text-slate-500">Пока нет завершённых опросов по приглашению врача.</p>
            ) : (
              <ul className="mt-3 space-y-3">
                {doctorQuestionnaires.map((e) => (
                  <li key={e.id} className="rounded-xl border border-teal-100 bg-teal-50/50 p-3 text-sm">
                    <div className="flex flex-wrap justify-between gap-2 text-slate-800">
                      <span className="font-medium">
                        {(e.data?.questionnaire_title && String(e.data.questionnaire_title).trim()) || "Опросник"}
                      </span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-teal-800 ring-1 ring-teal-100">
                        {formatDate(e.entry_date)}
                      </span>
                    </div>
                    {(e.conclusion || "").trim() ? (
                      <p className="mt-2 whitespace-pre-wrap text-slate-700">{e.conclusion}</p>
                    ) : (
                      <p className="mt-2 text-slate-500">Заключение пока не добавлено.</p>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </>
        ) : null}
      </section>

      <section className={card}>
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <HeartPulse className="h-5 w-5 shrink-0 text-teal-600" strokeWidth={1.75} aria-hidden />
          Дневник здоровья
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Передайте показатели лечащему врачу (давление, самочувствие и т.д.).
        </p>
        <form onSubmit={submitDiary} className="mt-4 space-y-3">
          <label className="block text-xs font-medium text-slate-600">
            Дата
            <input
              type="date"
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
              value={dDate}
              onChange={(e) => setDDate(e.target.value)}
              required
            />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Показатель
            <input
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
              placeholder="Например: артериальное давление"
              value={dMetric}
              onChange={(e) => setDMetric(e.target.value)}
            />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            Значение
            <input
              className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-base text-slate-900 outline-none ring-teal-500/30 focus:ring-2"
              placeholder="Например: 120/80"
              value={dValue}
              onChange={(e) => setDValue(e.target.value)}
            />
          </label>
          {dMsg ? <p className="text-sm text-teal-800">{dMsg}</p> : null}
          <button
            type="submit"
            disabled={dBusy}
            className="w-full rounded-xl bg-teal-600 py-3 text-sm font-semibold text-white shadow-md shadow-teal-600/25 disabled:opacity-50"
          >
            {dBusy ? "Отправка…" : "Отправить врачу"}
          </button>
        </form>
      </section>

      <section className={card}>
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <BookOpen className="h-5 w-5 shrink-0 text-teal-600" strokeWidth={1.75} aria-hidden />
          Полезные материалы
        </h2>
        <ul className="mt-3 list-inside list-disc space-y-2 text-sm text-slate-700">
          <li>Соблюдайте назначенный режим лечения и дозировки препаратов.</li>
          <li>При ухудшении самочувствия обратитесь к врачу или вызовите скорую помощь (103).</li>
          <li>
            Официальные рекомендации:{" "}
            <a
              href="https://www.rosminzdrav.ru/"
              className="font-medium text-teal-700 underline decoration-teal-300 underline-offset-2"
              target="_blank"
              rel="noopener noreferrer"
            >
              Минздрав России
            </a>
          </li>
        </ul>
      </section>

      {maxSession ? (
        <nav
          className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200/90 bg-white/95 px-4 py-3 shadow-[0_-4px_20px_rgba(15,23,42,0.06)] backdrop-blur-md sm:hidden"
          style={{ paddingBottom: "max(0.75rem, env(safe-area-inset-bottom, 0px))" }}
        >
          <button
            type="button"
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-slate-200 py-3 text-sm font-semibold text-slate-800 active:bg-slate-50"
            onClick={onLogout}
          >
            <LogOut className="h-5 w-5" aria-hidden />
            Выйти
          </button>
        </nav>
      ) : null}
    </div>
  );
}

export function PatientMISPage() {
  const { id: routePatientId } = useParams();
  const legacyId = routePatientId || "";

  const [maxPatientId, setMaxPatientId] = useState("");
  const [regDraft, setRegDraft] = useState(null);

  const handleLogout = useCallback(() => {
    clearPatientSession();
    setMaxPatientId("");
    setRegDraft(null);
    if (typeof window !== "undefined") {
      window.location.assign("/public/mis/patient");
    }
  }, []);

  const effectivePatientId = legacyId || maxPatientId || getStoredPatientId();

  if (legacyId) {
    return <PatientCabinetContent patientId={legacyId} maxSession={false} />;
  }

  return (
    <PatientAuthGuard
      onAuthenticated={(pid) => {
        setMaxPatientId(pid);
        setRegDraft(null);
      }}
      onRegistrationRequired={(d) => {
        setRegDraft(d);
        setMaxPatientId("");
      }}
    >
      {regDraft ? (
        <PatientMaxRegistrationForm
          draft={regDraft}
          onSuccess={(pid) => {
            setMaxPatientId(pid);
            setRegDraft(null);
          }}
        />
      ) : effectivePatientId ? (
        <PatientCabinetContent
          patientId={effectivePatientId}
          maxSession
          onLogout={handleLogout}
        />
      ) : null}
    </PatientAuthGuard>
  );
}
