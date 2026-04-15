import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Loader2,
  MessageCircle,
  Search,
  Send,
  Sparkles,
  Stethoscope,
} from "lucide-react";
import api from "../api/client.js";
import { useAuthStore } from "../store/authStore.js";

function formatApiDetail(err) {
  const det = err?.response?.data?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) return det.map((x) => x?.msg ?? x).join("; ");
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString("ru-RU");
  } catch {
    return iso;
  }
}

/** Рост в см, вес в кг → ИМТ */
function computeBmi(heightCm, weightKg) {
  const h = parseFloat(String(heightCm));
  const w = parseFloat(String(weightKg));
  if (!Number.isFinite(h) || !Number.isFinite(w) || h <= 0 || w <= 0) return null;
  const m = h / 100;
  if (m <= 0) return null;
  const bmi = w / (m * m);
  return Math.round(bmi * 10) / 10;
}

const shell = "min-h-full bg-[#f4f8fb] text-slate-800 pb-10";
const card = "rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm shadow-slate-200/40";

const AI_ANALYSIS_QUESTION =
  "Проанализируй историю болезни и обследований пациента. Дай структурированные рекомендации для врача " +
  "(обобщение данных, на что обратить внимание, идеи для дифференциальной диагностики). " +
  "Не ставь окончательный диагноз и не заменяй очный осмотр. Ответ на русском.";

export function DoctorMISPage() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  /** Админ организации / супер-админ: МИС без личного профиля врача (отдельные API /mis/admin/...). */
  const isMisAdmin = user?.role === "org_admin" || user?.role === "super_admin";

  const [list, setList] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listErr, setListErr] = useState("");
  const [q, setQ] = useState("");

  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailErr, setDetailErr] = useState("");

  const [diag, setDiag] = useState("");
  const [plan, setPlan] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [saveBusy, setSaveBusy] = useState(false);
  const [saveMsg, setSaveMsg] = useState("");

  const [aiBusy, setAiBusy] = useState(false);
  const [aiText, setAiText] = useState("");

  const [maxChatId, setMaxChatId] = useState("");
  const [maxBusy, setMaxBusy] = useState(false);
  const [maxMsg, setMaxMsg] = useState("");

  const [npName, setNpName] = useState("");
  const [npPhone, setNpPhone] = useState("");
  const [npBirth, setNpBirth] = useState("");
  const [npBusy, setNpBusy] = useState(false);
  const [npMsg, setNpMsg] = useState("");
  /** Записи medical_doctors (поле id — для doctor_id при создании пациента админом). */
  const [misDoctors, setMisDoctors] = useState([]);
  const [npDoctorId, setNpDoctorId] = useState("");

  const loadList = useCallback(async () => {
    setListErr("");
    setListLoading(true);
    try {
      const path = isMisAdmin ? "/mis/admin/patients" : "/mis/doctor/patients";
      const { data } = await api.get(path);
      setList(data ?? []);
    } catch (e) {
      setListErr(formatApiDetail(e));
    } finally {
      setListLoading(false);
    }
  }, [isMisAdmin]);

  const loadMisDoctors = useCallback(async () => {
    if (!isMisAdmin) {
      setMisDoctors([]);
      setNpDoctorId("");
      return;
    }
    try {
      const { data } = await api.get("/mis/admin/doctors");
      const arr = Array.isArray(data) ? data : [];
      setMisDoctors(arr);
      setNpDoctorId((prev) => {
        if (prev && arr.some((d) => String(d.id) === prev)) return prev;
        if (arr.length === 1) return String(arr[0].id);
        return "";
      });
    } catch {
      setMisDoctors([]);
    }
  }, [isMisAdmin]);

  useEffect(() => {
    if (!patientId) {
      loadList();
      loadMisDoctors();
    }
  }, [patientId, loadList, loadMisDoctors]);

  const loadDetail = useCallback(async () => {
    if (!patientId) return;
    setDetailErr("");
    setDetailLoading(true);
    try {
      const path = isMisAdmin
        ? `/mis/admin/patients/${patientId}`
        : `/mis/doctor/patients/${patientId}`;
      const { data } = await api.get(path);
      setDetail(data);
      const p = data?.patient;
      if (p) {
        setDiag(p.current_diagnosis ?? "");
        setPlan(p.treatment_plan ?? "");
        setHeight(p.height != null ? String(p.height) : "");
        setWeight(p.weight != null ? String(p.weight) : "");
      }
    } catch (e) {
      setDetailErr(formatApiDetail(e));
      setDetail(null);
    } finally {
      setDetailLoading(false);
    }
  }, [patientId, isMisAdmin]);

  useEffect(() => {
    if (patientId) {
      loadDetail();
      setAiText("");
      setMaxMsg("");
    }
  }, [patientId, loadDetail]);

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return list;
    return list.filter((p) => (p.full_name || "").toLowerCase().includes(s));
  }, [list, q]);

  const bmi = useMemo(() => computeBmi(height, weight), [height, weight]);

  const saveCard = async () => {
    if (!patientId) return;
    setSaveBusy(true);
    setSaveMsg("");
    try {
      const patchUrl = isMisAdmin
        ? `/mis/admin/patients/${patientId}`
        : `/mis/doctor/patients/${patientId}`;
      await api.patch(patchUrl, {
        current_diagnosis: diag.trim(),
        treatment_plan: plan.trim(),
        height: height.trim() === "" ? null : parseFloat(height.replace(",", ".")),
        weight: weight.trim() === "" ? null : parseFloat(weight.replace(",", ".")),
      });
      setSaveMsg("Сохранено.");
      await loadDetail();
    } catch (e) {
      setSaveMsg(formatApiDetail(e));
    } finally {
      setSaveBusy(false);
    }
  };

  const runAi = async () => {
    if (!patientId) return;
    setAiBusy(true);
    setAiText("");
    try {
      const aiUrl = isMisAdmin ? "/mis/admin/ai-consult" : "/mis/doctor/ai-consult";
      const { data } = await api.post(aiUrl, {
        patient_id: patientId,
        question: AI_ANALYSIS_QUESTION,
      });
      setAiText(data?.answer ?? "");
    } catch (e) {
      setAiText(`Ошибка: ${formatApiDetail(e)}`);
    } finally {
      setAiBusy(false);
    }
  };

  const sendMax = async () => {
    if (!patientId) return;
    const id = parseInt(String(maxChatId).trim(), 10);
    if (!Number.isFinite(id)) {
      setMaxMsg("Укажите числовой chat_id чата MAX.");
      return;
    }
    setMaxBusy(true);
    setMaxMsg("");
    try {
      const sendUrl = isMisAdmin
        ? `/mis/admin/patients/${patientId}/send-max`
        : `/mis/doctor/patients/${patientId}/send-max`;
      await api.post(sendUrl, { max_chat_id: id });
      setMaxMsg("Сводка отправлена в MAX.");
    } catch (e) {
      setMaxMsg(formatApiDetail(e));
    } finally {
      setMaxBusy(false);
    }
  };

  const copyPhone = () => {
    const phone = detail?.patient?.phone;
    if (!phone) return;
    navigator.clipboard?.writeText(phone).catch(() => {});
  };

  const createPatient = async (e) => {
    e.preventDefault();
    const full_name = npName.trim();
    if (!full_name) {
      setNpMsg("Укажите ФИО.");
      return;
    }
    if (isMisAdmin && !npDoctorId) {
      setNpMsg("Выберите врача МИС, за которым закрепляется карта.");
      return;
    }
    setNpBusy(true);
    setNpMsg("");
    try {
      const { data } = isMisAdmin
        ? await api.post("/mis/admin/patients", {
            doctor_id: npDoctorId,
            full_name,
            phone: npPhone.trim(),
            birth_date: npBirth.trim() || null,
          })
        : await api.post("/mis/doctor/patients", {
            full_name,
            phone: npPhone.trim(),
            birth_date: npBirth.trim() || null,
          });
      setNpName("");
      setNpPhone("");
      setNpBirth("");
      if (data?.id) navigate(`/mis/patients/${data.id}`);
      else await loadList();
    } catch (err) {
      setNpMsg(formatApiDetail(err));
    } finally {
      setNpBusy(false);
    }
  };

  if (!patientId) {
    return (
      <div className={shell}>
        <div className="mx-auto max-w-5xl px-4 pt-6">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-slate-900">
                <Stethoscope className="h-8 w-8 text-teal-600" strokeWidth={1.5} aria-hidden />
                {isMisAdmin ? "МИС — пациенты организации" : "МИС — мои пациенты"}
              </h1>
              <p className="mt-1 text-sm text-slate-600">
                {isMisAdmin
                  ? "Как администратор вы видите всех пациентов организации. Новую карту закрепите за выбранным врачом МИС."
                  : "Светлый интерфейс для работы с картами пациентов."}
              </p>
            </div>
          </div>

          {listErr ? (
            <div className={`${card} mb-4 border-amber-200 bg-amber-50 text-amber-900`}>{listErr}</div>
          ) : null}

          <section className={`${card} mb-4`}>
            <h2 className="text-base font-semibold text-slate-900">Новый пациент</h2>
            <p className="mt-1 text-xs text-slate-600">
              Пациент не «регистрируется» сам: карту создаёт врач или администратор. После создания откройте карту — там
              будет ссылка для пациента без входа в панель.
            </p>
            {isMisAdmin ? (
              <div className="mt-3">
                <label className="block text-xs font-medium text-slate-600">
                  Врач МИС (закрепление карты)
                  <select
                    required
                    className="mt-1 w-full max-w-md rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                    value={npDoctorId}
                    onChange={(e) => setNpDoctorId(e.target.value)}
                  >
                    <option value="">— выберите врача —</option>
                    {misDoctors.map((d) => (
                      <option key={d.id} value={d.id}>
                        {(d.display_name || d.qualification || "Врач").trim() || "Врач"}{" "}
                        {d.qualification && d.display_name ? `· ${d.qualification}` : ""}
                      </option>
                    ))}
                  </select>
                </label>
                {misDoctors.length === 0 ? (
                  <p className="mt-2 text-xs text-amber-800">
                    В организации пока нет врачей МИС. В разделе «Пользователи» создайте пользователя и нажмите «Назначить
                    врачом». Убедитесь, что на сервере обновлён бэкенд (нужен метод GET /api/mis/admin/doctors).
                  </p>
                ) : null}
              </div>
            ) : null}
            <form className="mt-3 flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-end" onSubmit={createPatient}>
              <label className="block min-w-[12rem] flex-1 text-xs font-medium text-slate-600">
                ФИО
                <input
                  required
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                  value={npName}
                  onChange={(e) => setNpName(e.target.value)}
                  placeholder="Иванов Иван Иванович"
                />
              </label>
              <label className="block w-full text-xs font-medium text-slate-600 sm:w-40">
                Телефон
                <input
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                  value={npPhone}
                  onChange={(e) => setNpPhone(e.target.value)}
                  placeholder="+7…"
                />
              </label>
              <label className="block w-full text-xs font-medium text-slate-600 sm:w-40">
                Дата рождения
                <input
                  type="date"
                  className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                  value={npBirth}
                  onChange={(e) => setNpBirth(e.target.value)}
                />
              </label>
              <button
                type="submit"
                disabled={npBusy}
                className="rounded-xl bg-teal-600 px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
              >
                {npBusy ? "Создание…" : "Создать и открыть карту"}
              </button>
            </form>
            {npMsg ? <p className="mt-2 text-sm text-red-600">{npMsg}</p> : null}
          </section>

          <div className={`${card} mb-4`}>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <Search className="h-4 w-4 shrink-0 text-slate-400" aria-hidden />
              <input
                className="w-full rounded-xl border border-slate-200 bg-slate-50/80 px-3 py-2 text-slate-900 outline-none ring-teal-500/20 focus:ring-2"
                placeholder="Поиск по ФИО…"
                value={q}
                onChange={(e) => setQ(e.target.value)}
              />
            </label>
          </div>

          {listLoading ? (
            <div className={`${card} flex items-center justify-center gap-2 py-16 text-slate-500`}>
              <Loader2 className="h-6 w-6 animate-spin text-teal-600" />
              Загрузка…
            </div>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {filtered.map((p) => (
                <Link
                  key={p.id}
                  to={`/mis/patients/${p.id}`}
                  className={`${card} block transition hover:border-teal-300 hover:shadow-md hover:shadow-teal-500/10`}
                >
                  <div className="font-semibold text-slate-900">{p.full_name}</div>
                  <div className="mt-1 text-xs text-slate-500">Тел.: {p.phone || "—"}</div>
                  <div className="mt-2 text-xs text-slate-400">Обновлено: {formatDate(p.updated_at)}</div>
                </Link>
              ))}
            </div>
          )}

          {!listLoading && filtered.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-500">Пациенты не найдены.</p>
          ) : null}
        </div>
      </div>
    );
  }

  const p = detail?.patient;
  const entries = detail?.entries ?? [];

  return (
    <div className={shell}>
      <div className="mx-auto max-w-4xl px-4 pt-6">
        <button
          type="button"
          onClick={() => navigate("/mis")}
          className="mb-4 inline-flex items-center gap-2 text-sm font-medium text-teal-700 hover:text-teal-900"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden />
          К списку пациентов
        </button>

        {detailLoading && !p ? (
          <div className={`${card} flex items-center justify-center gap-2 py-16`}>
            <Loader2 className="h-6 w-6 animate-spin text-teal-600" />
          </div>
        ) : null}

        {detailErr ? (
          <div className={`${card} mb-4 border-red-200 bg-red-50 text-red-800`}>{detailErr}</div>
        ) : null}

        {p ? (
          <div className="space-y-4">
            <header className={card}>
              <h1 className="text-xl font-bold text-slate-900">{p.full_name}</h1>
              <p className="mt-1 text-sm text-slate-600">
                {formatDate(p.birth_date)} · {p.gender || "пол не указан"} · тел. {p.phone || "—"}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                <span className="font-medium text-slate-600">ID карты (для ссылки):</span>{" "}
                <code className="rounded bg-slate-100 px-1 font-mono text-slate-800">{patientId}</code>
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-teal-100 bg-teal-50/60 px-3 py-2 text-xs text-slate-700">
                <span className="min-w-0 flex-1 break-all font-mono text-[11px] sm:text-xs">
                  {typeof window !== "undefined"
                    ? `${window.location.origin}/public/mis/patient/${patientId}`
                    : `/public/mis/patient/${patientId}`}
                </span>
                <button
                  type="button"
                  className="shrink-0 rounded-lg bg-teal-600 px-2 py-1 text-xs font-medium text-white hover:bg-teal-500"
                  onClick={() => {
                    const url =
                      typeof window !== "undefined"
                        ? `${window.location.origin}/public/mis/patient/${patientId}`
                        : "";
                    if (url) navigator.clipboard?.writeText(url).catch(() => {});
                  }}
                >
                  Копировать ссылку пациенту
                </button>
              </div>
            </header>

            <section className={card}>
              <h2 className="text-base font-semibold text-slate-900">Антропометрия</h2>
              <div className="mt-3 grid gap-3 sm:grid-cols-3">
                <label className="text-xs font-medium text-slate-600">
                  Рост (см)
                  <input
                    type="number"
                    step="0.1"
                    className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                    value={height}
                    onChange={(e) => setHeight(e.target.value)}
                  />
                </label>
                <label className="text-xs font-medium text-slate-600">
                  Вес (кг)
                  <input
                    type="number"
                    step="0.1"
                    className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                    value={weight}
                    onChange={(e) => setWeight(e.target.value)}
                  />
                </label>
                <div className="flex flex-col justify-end">
                  <div className="rounded-xl border border-teal-100 bg-teal-50/80 px-3 py-2 text-center">
                    <div className="text-xs text-teal-800">ИМТ</div>
                    <div className="text-lg font-bold text-teal-900">{bmi != null ? bmi : "—"}</div>
                  </div>
                </div>
              </div>
            </section>

            <section className={card}>
              <h2 className="text-base font-semibold text-slate-900">Диагноз и лечение</h2>
              <label className="mt-3 block text-xs font-medium text-slate-600">
                Текущий диагноз
                <textarea
                  className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                  rows={3}
                  value={diag}
                  onChange={(e) => setDiag(e.target.value)}
                />
              </label>
              <label className="mt-3 block text-xs font-medium text-slate-600">
                План лечения
                <textarea
                  className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"
                  rows={4}
                  value={plan}
                  onChange={(e) => setPlan(e.target.value)}
                />
              </label>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button
                  type="button"
                  disabled={saveBusy}
                  onClick={saveCard}
                  className="rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
                >
                  {saveBusy ? "Сохранение…" : "Сохранить карту"}
                </button>
                {saveMsg ? <span className="text-sm text-slate-600">{saveMsg}</span> : null}
              </div>
            </section>

            <section className={card}>
              <h2 className="text-base font-semibold text-slate-900">История обследований и записей</h2>
              <ul className="mt-3 space-y-3">
                {entries.map((e) => (
                  <li key={e.id} className="rounded-xl border border-slate-100 bg-slate-50/90 p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium text-slate-800">{formatDate(e.entry_date)}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                          e.type === "exam" ? "bg-blue-100 text-blue-800" : "bg-violet-100 text-violet-800"
                        }`}
                      >
                        {e.type === "exam" ? "Обследование" : "Опрос / дневник"}
                      </span>
                    </div>
                    {e.data && Object.keys(e.data).length > 0 ? (
                      <pre className="mt-2 max-h-48 overflow-auto rounded-lg bg-white p-2 text-xs text-slate-700 ring-1 ring-slate-100">
                        {JSON.stringify(e.data, null, 2)}
                      </pre>
                    ) : null}
                    {(e.conclusion || "").trim() ? (
                      <p className="mt-2 text-slate-700">
                        <span className="font-medium text-slate-600">Заключение: </span>
                        {e.conclusion}
                      </p>
                    ) : null}
                    {(e.recommendations || "").trim() ? (
                      <p className="mt-1 text-slate-700">
                        <span className="font-medium text-slate-600">Рекомендации: </span>
                        {e.recommendations}
                      </p>
                    ) : null}
                  </li>
                ))}
              </ul>
              {entries.length === 0 ? <p className="mt-2 text-sm text-slate-500">Записей пока нет.</p> : null}
            </section>

            <section className={`${card} border-teal-200/80 bg-gradient-to-br from-white to-teal-50/40`}>
              <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <Sparkles className="h-5 w-5 text-teal-600" aria-hidden />
                Консультация ИИ
              </h2>
              <p className="mt-1 text-xs text-slate-600">
                Анализ через настроенный LLM (DeepSeek / OpenAI). Не заменяет клиническое решение.
              </p>
              <button
                type="button"
                disabled={aiBusy}
                onClick={runAi}
                className="mt-3 inline-flex items-center gap-2 rounded-xl bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white shadow-sm disabled:opacity-50"
              >
                {aiBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                Проанализировать историю болезни
              </button>
              {aiText ? (
                <div className="mt-4 rounded-xl border border-slate-200 bg-white p-3 text-sm leading-relaxed text-slate-800 whitespace-pre-wrap">
                  {aiText}
                </div>
              ) : null}
            </section>

            <section className={card}>
              <h2 className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <MessageCircle className="h-5 w-5 text-teal-600" aria-hidden />
                Мессенджер MAX
              </h2>
              <p className="mt-1 text-xs text-slate-600">
                Отправка сводки в чат через бэкенд (<code className="rounded bg-slate-100 px-1">MaxMessengerClient</code>
                ). Нужен настроенный <strong>MAX_BOT_TOKEN</strong> и числовой <strong>chat_id</strong> получателя.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={copyPhone}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700"
                >
                  Скопировать телефон пациента
                </button>
                <a
                  href="https://web.max.ru/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-xl border border-teal-200 bg-teal-50 px-3 py-2 text-sm font-medium text-teal-800"
                >
                  Открыть MAX Web
                </a>
              </div>
              <div className="mt-4 flex flex-wrap items-end gap-2">
                <label className="text-xs font-medium text-slate-600">
                  MAX chat_id
                  <input
                    className="mt-1 w-40 rounded-xl border border-slate-200 px-3 py-2 text-sm"
                    placeholder="например 12345"
                    value={maxChatId}
                    onChange={(e) => setMaxChatId(e.target.value)}
                  />
                </label>
                <button
                  type="button"
                  disabled={maxBusy}
                  onClick={sendMax}
                  className="inline-flex items-center gap-2 rounded-xl bg-teal-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
                >
                  {maxBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                  Отправить сводку в MAX
                </button>
              </div>
              {maxMsg ? <p className="mt-2 text-sm text-slate-700">{maxMsg}</p> : null}
            </section>
          </div>
        ) : null}
      </div>
    </div>
  );
}
