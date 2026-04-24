import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  ChevronDown,
  Loader2,
  MessageCircle,
  Search,
  Send,
  Save,
  Sparkles,
  Stethoscope,
  Trash2,
  X,
} from "lucide-react";
import QRCode from "react-qr-code";
import api from "../api/client.js";
import { IconCopyButton, IconQrButton } from "../components/ui/IconActionButtons.jsx";
import { SK } from "../constants/systemSettingsKeys.js";
import { useAuthStore } from "../store/authStore.js";
import { mapFromList } from "../utils/systemSettingsForm.js";
import { BTN_SAVE, BTN_SAVE_COMPACT, ICON_BTN, PAGE_H1, PAGE_TEXT, PAGE_TITLE_ICON } from "../styles/pageLayout.js";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

function formatApiDetail(err) {
  const det = err?.response?.data?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) return det.map((x) => x?.msg ?? x).join("; ");
  if (det != null) return JSON.stringify(det);
  return err?.message ?? String(err);
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

/** Логин бота в MAX (как в настройках): `@id…_bot` → сегмент пути `id…_bot`. */
function maxBotPathSlugFromSetting(raw) {
  const s = (raw || "").trim();
  if (!s) return "";
  return s.replace(/^@+/, "").replace(/^\/+/, "").trim();
}

/** UUID организации/врача для deep link MAX: snake_case или camelCase с бэкенда. */
function misDeepLinkIds(patient, user, isMisAdmin, settingsOrganizationId) {
  const p = patient;
  let org = p?.organization_id ?? p?.organizationId ?? null;
  let doc = p?.doctor_id ?? p?.doctorId ?? null;
  if (!org) {
    org = user?.organization_id ?? user?.organizationId ?? settingsOrganizationId ?? null;
  }
  if (!doc && !isMisAdmin) {
    doc = user?.medical_doctor_id ?? user?.medicalDoctorId ?? null;
  }
  return { org, doc };
}

export function DoctorMISPage() {
  const { patientId } = useParams();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const settingsOrganizationId = useAuthStore((s) => s.settingsOrganizationId);
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
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [aiBusy, setAiBusy] = useState(false);
  const [aiText, setAiText] = useState("");

  const [maxChatId, setMaxChatId] = useState("");
  const [maxBusy, setMaxBusy] = useState(false);
  const [maxMsg, setMaxMsg] = useState("");

  const [qnrList, setQnrList] = useState([]);
  const [qnrListLoading, setQnrListLoading] = useState(false);
  const [qnrSelectedId, setQnrSelectedId] = useState("");
  const [qnrBusy, setQnrBusy] = useState(false);
  const [qnrMsg, setQnrMsg] = useState("");

  const [entriesOpen, setEntriesOpen] = useState(false);

  const [npName, setNpName] = useState("");
  const [npPhone, setNpPhone] = useState("");
  const [npBirth, setNpBirth] = useState("");
  const [npBusy, setNpBusy] = useState(false);
  const [npMsg, setNpMsg] = useState("");
  /** Записи medical_doctors (поле id — для doctor_id при создании пациента админом). */
  const [misDoctors, setMisDoctors] = useState([]);
  const [npDoctorId, setNpDoctorId] = useState("");

  const [patientUrlCopied, setPatientUrlCopied] = useState(false);
  const [misStartCopied, setMisStartCopied] = useState(false);
  const [phoneCopied, setPhoneCopied] = useState(false);

  const [miniChatDraft, setMiniChatDraft] = useState("");
  const [miniChatSaving, setMiniChatSaving] = useState(false);
  useEffect(() => {
    setMiniChatDraft((user?.miniapp_chat_id || "").trim());
  }, [user?.miniapp_chat_id]);
  const [qrModalOpen, setQrModalOpen] = useState(false);
  const [patientCardQrOpen, setPatientCardQrOpen] = useState(false);
  const patientUrlCopyTimer = useRef(null);
  const misStartCopyTimer = useRef(null);
  const phoneCopyTimer = useRef(null);

  /** Упоминание бота (интеграции MAX → MAX_BOT_USERNAME), для ссылок max.ru / max:// */
  const [maxBotUsernameSetting, setMaxBotUsernameSetting] = useState("");

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

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get("/settings");
        const map = mapFromList(data);
        const v = map[SK.MAX_BOT_USERNAME]?.value;
        if (!cancelled) setMaxBotUsernameSetting(v != null ? String(v) : "");
      } catch {
        if (!cancelled) setMaxBotUsernameSetting("");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

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
        const mc = p.max_chat_id;
        if (mc != null && String(mc).trim() !== "") {
          setMaxChatId(String(mc).trim());
        } else {
          setMaxChatId("");
        }
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
      setQnrMsg("");
      setQrModalOpen(false);
      setPatientCardQrOpen(false);
      setEntriesOpen(false);
    }
  }, [patientId, loadDetail]);

  useEffect(() => {
    if (!patientId) {
      setQnrList([]);
      setQnrSelectedId("");
      return;
    }
    let cancelled = false;
    (async () => {
      setQnrListLoading(true);
      try {
        const { data } = await api.get("/questionnaires");
        const arr = Array.isArray(data) ? data : [];
        if (!cancelled) {
          setQnrList(arr);
          setQnrSelectedId((prev) =>
            prev && arr.some((x) => String(x.id) === prev) ? prev : "",
          );
        }
      } catch {
        if (!cancelled) {
          setQnrList([]);
          setQnrSelectedId("");
        }
      } finally {
        if (!cancelled) setQnrListLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [patientId]);

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

  const deletePatient = async () => {
    if (!patientId) return;
    const name = detail?.patient?.full_name || "пациента";
    if (
      !window.confirm(
        `Удалить карту «${name}» и все связанные записи (обследования, опросники)? Действие необратимо.`,
      )
    ) {
      return;
    }
    setDeleteBusy(true);
    setDetailErr("");
    try {
      const delUrl = isMisAdmin
        ? `/mis/admin/patients/${patientId}`
        : `/mis/doctor/patients/${patientId}`;
      await api.delete(delUrl);
      navigate("/mis/clinic");
    } catch (e) {
      setDetailErr(formatApiDetail(e));
    } finally {
      setDeleteBusy(false);
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

  const sendQuestionnaireLink = async () => {
    if (!patientId) return;
    if (!qnrSelectedId) {
      setQnrMsg("Выберите опросник организации.");
      return;
    }
    setQnrBusy(true);
    setQnrMsg("");
    try {
      const sendUrl = isMisAdmin
        ? `/mis/admin/patients/${patientId}/send-questionnaire`
        : `/mis/doctor/patients/${patientId}/send-questionnaire`;
      await api.post(sendUrl, {
        questionnaire_id: qnrSelectedId,
      });
      setQnrMsg("Ссылка на опросник отправлена в MAX.");
    } catch (e) {
      setQnrMsg(formatApiDetail(e));
    } finally {
      setQnrBusy(false);
    }
  };

  const copyPatientPublicUrl = useCallback(() => {
    if (!patientId) return;
    const url =
      typeof window !== "undefined"
        ? `${window.location.origin}/public/mis/patient/${patientId}`
        : "";
    if (!url) return;
    navigator.clipboard
      ?.writeText(url)
      .then(() => {
        if (patientUrlCopyTimer.current) clearTimeout(patientUrlCopyTimer.current);
        setPatientUrlCopied(true);
        patientUrlCopyTimer.current = setTimeout(() => {
          setPatientUrlCopied(false);
          patientUrlCopyTimer.current = null;
        }, 2000);
      })
      .catch(() => {});
  }, [patientId]);

  /** Для списка МИС (админ): врач из выбора или единственный в организации. */
  const adminListDoctorId = useMemo(() => {
    if (!isMisAdmin) return "";
    if (npDoctorId) return npDoctorId;
    if (misDoctors.length === 1) return String(misDoctors[0].id);
    return "";
  }, [isMisAdmin, npDoctorId, misDoctors]);

  const misMaxStartPayload = useMemo(() => {
    const patient = patientId ? detail?.patient : null;
    const { org: o0, doc: d0 } = misDeepLinkIds(patient, user, isMisAdmin, settingsOrganizationId);
    let org = o0;
    let doc = d0;
    if (!doc && isMisAdmin && !patientId && adminListDoctorId) {
      doc = adminListDoctorId;
    }
    if (!org || !doc) return "";
    return `reg_org_${String(org).toLowerCase()}_doc_${String(doc).toLowerCase()}`;
  }, [
    patientId,
    detail?.patient,
    user,
    isMisAdmin,
    settingsOrganizationId,
    adminListDoctorId,
  ]);

  const misMaxStartCommand = useMemo(
    () => (misMaxStartPayload ? `/start ${misMaxStartPayload}` : ""),
    [misMaxStartPayload],
  );

  const maxBotPathSlug = useMemo(
    () => maxBotPathSlugFromSetting(maxBotUsernameSetting),
    [maxBotUsernameSetting],
  );

  /** Открытие профиля бота в браузере / перехват в приложении MAX. */
  const misMaxBotLinkHttps = useMemo(() => {
    if (!maxBotPathSlug || !misMaxStartPayload) return "";
    return `https://max.ru/${maxBotPathSlug}?start=${encodeURIComponent(misMaxStartPayload)}`;
  }, [maxBotPathSlug, misMaxStartPayload]);

  /** Явное открытие в приложении MAX (QR и универсальные сценарии). */
  const misMaxBotLinkApp = useMemo(() => {
    if (!maxBotPathSlug || !misMaxStartPayload) return "";
    return `max://max.ru/${maxBotPathSlug}?start=${encodeURIComponent(misMaxStartPayload)}`;
  }, [maxBotPathSlug, misMaxStartPayload]);

  const misMaxRegistrationQrValue = useMemo(
    () => misMaxBotLinkApp || misMaxStartCommand,
    [misMaxBotLinkApp, misMaxStartCommand],
  );

  const patientCardPublicUrl = useMemo(() => {
    if (!patientId) return "";
    if (typeof window === "undefined") return `/public/mis/patient/${patientId}`;
    return `${window.location.origin}/public/mis/patient/${patientId}`;
  }, [patientId]);

  const misMaxLinkToCopy = useMemo(
    () => misMaxBotLinkHttps || misMaxStartCommand,
    [misMaxBotLinkHttps, misMaxStartCommand],
  );

  const copyMisMaxStart = useCallback(() => {
    if (!misMaxLinkToCopy) return;
    navigator.clipboard
      ?.writeText(misMaxLinkToCopy)
      .then(() => {
        if (misStartCopyTimer.current) clearTimeout(misStartCopyTimer.current);
        setMisStartCopied(true);
        misStartCopyTimer.current = setTimeout(() => {
          setMisStartCopied(false);
          misStartCopyTimer.current = null;
        }, 2000);
      })
      .catch(() => {});
  }, [misMaxLinkToCopy]);

  const copyPhone = useCallback(() => {
    const phone = detail?.patient?.phone;
    if (!phone) return;
    navigator.clipboard
      ?.writeText(phone)
      .then(() => {
        if (phoneCopyTimer.current) clearTimeout(phoneCopyTimer.current);
        setPhoneCopied(true);
        phoneCopyTimer.current = setTimeout(() => {
          setPhoneCopied(false);
          phoneCopyTimer.current = null;
        }, 2000);
      })
      .catch(() => {});
  }, [detail?.patient?.phone]);

  useEffect(() => {
    return () => {
      if (patientUrlCopyTimer.current) clearTimeout(patientUrlCopyTimer.current);
      if (misStartCopyTimer.current) clearTimeout(misStartCopyTimer.current);
      if (phoneCopyTimer.current) clearTimeout(phoneCopyTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!qrModalOpen && !patientCardQrOpen) return;
    const onKey = (e) => {
      if (e.key !== "Escape") return;
      setQrModalOpen(false);
      setPatientCardQrOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [qrModalOpen, patientCardQrOpen]);

  const saveMiniappChatId = async () => {
    setMiniChatSaving(true);
    try {
      await api.patch("/auth/me/miniapp-chat", {
        miniapp_chat_id: miniChatDraft.trim() ? miniChatDraft.trim() : null,
      });
      const { data } = await api.get("/auth/me");
      setUser(data);
    } catch (e) {
      window.alert(formatApiDetail(e));
    } finally {
      setMiniChatSaving(false);
    }
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
      if (data?.id) navigate(`/mis/clinic/patients/${data.id}`);
      else await loadList();
    } catch (err) {
      setNpMsg(formatApiDetail(err));
    } finally {
      setNpBusy(false);
    }
  };

  const p = detail?.patient;
  const entries = detail?.entries ?? [];

  return (
    <div className={shell}>
      {!patientId ? (
        <div className="mx-auto max-w-5xl px-4 pt-6">
          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="flex items-center gap-2 text-2xl font-bold tracking-tight text-slate-900">
                <Stethoscope className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
                {isMisAdmin ? "МИС — пациенты организации" : "МИС — мои пациенты"}
              </h1>
              <p className="mt-1 text-sm text-slate-600">
                {isMisAdmin
                  ? "Как администратор вы видите всех пациентов организации. Новую карту закрепите за выбранным врачом МИС."
                  : "Светлый интерфейс для работы с картами пациентов."}
              </p>
            </div>
          </div>

          {misMaxStartCommand ? (
            <section className={`${card} mb-4`}>
              <h2 className="text-base font-semibold text-slate-900">Регистрация пациентов через MAX</h2>
              <p className="mt-1 text-xs text-slate-600">
                Ссылка и QR ведут на профиль бота в MAX (как{" "}
                <a
                  href="https://max.ru/"
                  className="font-medium text-violet-800 underline decoration-violet-300"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  max.ru/id…_bot
                </a>
                ). Имя в пути берётся из «Упоминание бота в группе MAX» (<strong>MAX_BOT_USERNAME</strong>) в разделе
                Интеграции. Параметр <code className="rounded bg-slate-100 px-1 font-mono text-[10px]">start</code> —
                привязка к этому врачу.
              </p>
              {!maxBotPathSlug ? (
                <p className="mt-2 rounded-lg border border-amber-100 bg-amber-50/80 px-3 py-2 text-xs text-amber-900">
                  Укажите <strong>MAX_BOT_USERNAME</strong> в «Интеграции» → MAX, чтобы показать ссылку{" "}
                  <code className="font-mono">https://max.ru/…</code> и QR с открытием приложения. Пока доступна только
                  команда для чата.
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-violet-100 bg-violet-50/60 px-3 py-2 text-xs text-slate-700">
                <span className="min-w-0 flex-1 break-all text-[11px] sm:text-xs">
                  {misMaxBotLinkHttps ? (
                    <a
                      href={misMaxBotLinkHttps}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-violet-900 underline decoration-violet-300"
                    >
                      {misMaxBotLinkHttps}
                    </a>
                  ) : (
                    <span className="font-mono text-slate-800">{misMaxStartCommand}</span>
                  )}
                </span>
                <IconCopyButton
                  variant="light"
                  title={misMaxBotLinkHttps ? "Скопировать ссылку" : "Скопировать команду"}
                  copied={misStartCopied}
                  className="focus-visible:ring-violet-500/50"
                  onClick={copyMisMaxStart}
                />
                <IconQrButton
                  variant="light"
                  title="Показать QR-код"
                  className="focus-visible:ring-violet-500/50"
                  onClick={() => setQrModalOpen(true)}
                />
              </div>
              {misMaxBotLinkHttps && misMaxStartCommand ? (
                <p className="mt-2 text-[11px] leading-snug text-slate-500">
                  Если чат не подхватил стартовый параметр, отправьте боту:{" "}
                  <code className="rounded bg-white px-1 font-mono text-[10px] text-slate-700">{misMaxStartCommand}</code>
                </p>
              ) : null}
            </section>
          ) : isMisAdmin && misDoctors.length > 1 && !npDoctorId ? (
            <section className={`${card} mb-4 border-violet-100 bg-violet-50/40`}>
              <p className="text-xs text-slate-700">
                Чтобы показать команду{" "}
                <code className="rounded bg-white px-1 font-mono text-[11px]">/start reg_org_…_doc_…</code>, выберите
                врача МИС в блоке «Новый пациент».
              </p>
            </section>
          ) : null}

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

          {user?.organization_id ? (
            <section className={`${card} mb-4`}>
              <h2 className="text-base font-semibold text-slate-900">Mini App (MAX): ваш chat_id</h2>
              <p className="mt-1 text-xs text-slate-600">
                Укажите тот же <strong className="font-medium">chat_id</strong>, что в Web App мессенджера — тогда в Mini
                App МИС-сайта вы будете определяться как <strong className="font-medium">врач</strong> и увидите страницу
                «Пациенты» (если она добавлена в меню конструктора). Совпадение идёт с этим полем в вашем профиле
                портала.
              </p>
              <div className="mt-3 flex flex-wrap items-end gap-2">
                <label className="min-w-[200px] flex-1 text-xs font-medium text-slate-600">
                  MAX chat_id
                  <input
                    type="text"
                    value={miniChatDraft}
                    onChange={(e) => setMiniChatDraft(e.target.value)}
                    maxLength={64}
                    placeholder="например, из отладки Web App"
                    className="mt-1 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900"
                  />
                </label>
                <button
                  type="button"
                  disabled={miniChatSaving}
                  onClick={saveMiniappChatId}
                  className={`${BTN_SAVE_COMPACT} rounded-xl px-4 py-2.5`}
                >
                  <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                  {miniChatSaving ? "Сохранение…" : "Сохранить"}
                </button>
              </div>
            </section>
          ) : null}

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
                  to={`/mis/clinic/patients/${p.id}`}
                  className={`${card} block transition hover:border-teal-300 hover:shadow-md hover:shadow-teal-500/10`}
                >
                  <div className="font-semibold text-slate-900">{p.full_name}</div>
                  <div className="mt-1 text-xs text-slate-500">Тел.: {p.phone || "—"}</div>
                  <div className="mt-2 text-xs text-slate-400">Обновлено: {formatDateTimeRu(p.updated_at)}</div>
                </Link>
              ))}
            </div>
          )}

          {!listLoading && filtered.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-500">Пациенты не найдены.</p>
          ) : null}
        </div>
      ) : (
      <div className="mx-auto max-w-4xl px-4 pt-6">
        <button
          type="button"
          onClick={() => navigate("/mis/clinic")}
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
                {formatDateTimeRu(p.birth_date)} · {p.gender || "пол не указан"} · тел. {p.phone || "—"}
              </p>
              <p className="mt-2 text-xs text-slate-500">
                <span className="font-medium text-slate-600">ID карты (для ссылки):</span>{" "}
                <code className="rounded bg-slate-100 px-1 font-mono text-slate-800">{patientId}</code>
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-teal-100 bg-teal-50/60 px-3 py-2 text-xs text-slate-700">
                <span className="min-w-0 flex-1 break-all font-mono text-[11px] sm:text-xs">
                  {patientCardPublicUrl || `…/public/mis/patient/${patientId}`}
                </span>
                <IconCopyButton
                  variant="light"
                  title="Копировать ссылку пациенту"
                  copied={patientUrlCopied}
                  className="focus-visible:ring-teal-500/50"
                  onClick={copyPatientPublicUrl}
                />
                <IconQrButton
                  variant="light"
                  title="QR-код ссылки на карту"
                  className="focus-visible:ring-teal-500/50"
                  disabled={!patientCardPublicUrl}
                  onClick={() => patientCardPublicUrl && setPatientCardQrOpen(true)}
                />
              </div>
              {misMaxStartCommand ? (
                <div className="mt-3">
                  <p className="text-xs font-medium text-slate-600">Регистрация в MAX по этому врачу</p>
                  <p className="mt-0.5 text-[11px] text-slate-500">
                    Ссылка на бота из <strong>MAX_BOT_USERNAME</strong>; QR кодирует <code className="font-mono">max://max.ru/…</code> для
                    открытия приложения.
                  </p>
                  {!maxBotPathSlug ? (
                    <p className="mt-2 rounded-lg border border-amber-100 bg-amber-50/80 px-2 py-1.5 text-[11px] text-amber-900">
                      Заполните MAX_BOT_USERNAME в Интеграции → MAX для ссылки на профиль бота.
                    </p>
                  ) : null}
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 rounded-xl border border-violet-100 bg-violet-50/60 px-3 py-2 text-xs text-slate-700">
                    <span className="min-w-0 flex-1 break-all text-[11px] sm:text-xs">
                      {misMaxBotLinkHttps ? (
                        <a
                          href={misMaxBotLinkHttps}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-violet-900 underline decoration-violet-300"
                        >
                          {misMaxBotLinkHttps}
                        </a>
                      ) : (
                        <span className="font-mono text-slate-800">{misMaxStartCommand}</span>
                      )}
                    </span>
                    <IconCopyButton
                      variant="light"
                      title={misMaxBotLinkHttps ? "Скопировать ссылку" : "Скопировать команду"}
                      copied={misStartCopied}
                      className="focus-visible:ring-violet-500/50"
                      onClick={copyMisMaxStart}
                    />
                    <IconQrButton
                      variant="light"
                      title="Показать QR-код"
                      className="focus-visible:ring-violet-500/50"
                      onClick={() => setQrModalOpen(true)}
                    />
                  </div>
                  {misMaxBotLinkHttps && misMaxStartCommand ? (
                    <p className="mt-2 text-[11px] text-slate-500">
                      Вручную в чате:{" "}
                      <code className="rounded bg-slate-100 px-1 font-mono text-[10px] text-slate-700">{misMaxStartCommand}</code>
                    </p>
                  ) : null}
                </div>
              ) : null}
              <div className="mt-4 flex flex-wrap items-center justify-end gap-2 border-t border-slate-100 pt-4">
                <button
                  type="button"
                  disabled={deleteBusy}
                  onClick={deletePatient}
                  className="inline-flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-medium text-red-800 shadow-sm hover:bg-red-100 disabled:opacity-50"
                >
                  <Trash2 className="h-4 w-4 shrink-0" aria-hidden />
                  {deleteBusy ? "Удаление…" : "Удалить карту пациента"}
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
                  className={`${BTN_SAVE} rounded-xl`}
                >
                  <Save className={ICON_BTN} strokeWidth={2} aria-hidden />
                  {saveBusy ? "Сохранение…" : "Сохранить карту"}
                </button>
                {saveMsg ? <span className="text-sm text-slate-600">{saveMsg}</span> : null}
              </div>
            </section>

            <section className={card}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-2 text-left"
                onClick={() => setEntriesOpen((v) => !v)}
                aria-expanded={entriesOpen}
              >
                <h2 className="text-base font-semibold text-slate-900">История обследований и записей</h2>
                <span className="flex shrink-0 items-center gap-2 text-xs text-slate-500">
                  {entries.length ? `${entries.length} запис.` : "пусто"}
                  <ChevronDown
                    className={`h-5 w-5 text-slate-400 transition-transform ${entriesOpen ? "rotate-180" : ""}`}
                    aria-hidden
                  />
                </span>
              </button>
              {entriesOpen ? (
                <>
                  <ul className="mt-3 space-y-3">
                    {entries.map((e) => (
                      <li key={e.id} className="rounded-xl border border-slate-100 bg-slate-50/90 p-3 text-sm">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-medium text-slate-800">{formatDateTimeRu(e.entry_date)}</span>
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
                </>
              ) : null}
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
                ). Нужен настроенный <strong>MAX_BOT_TOKEN</strong>. Поле <strong>chat_id</strong> ниже подставляется из карты
                пациента после регистрации через бота в MAX; при необходимости его можно изменить вручную для отправки сводки.
              </p>
              <div className="mt-3 flex flex-wrap gap-2">
                <IconCopyButton
                  variant="light"
                  title="Скопировать телефон пациента"
                  copied={phoneCopied}
                  disabled={!detail?.patient?.phone}
                  className="focus-visible:ring-teal-500/50"
                  onClick={copyPhone}
                />
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

              <div className="mt-6 border-t border-slate-100 pt-5">
                <h3 className="text-sm font-semibold text-slate-900">Опросник по ссылке</h3>
                <p className="mt-1 text-xs text-slate-600">
                  Выберите опросник организации — ссылка с защищённым приглашением уйдёт в чат пациента с ботом (тот же{" "}
                  <strong>MAX chat_id</strong>, что сохранён в карте после регистрации в MAX). Ответы и заключение ИИ сохранятся в
                  этой карте.
                </p>
                <div className="mt-3 flex flex-wrap items-end gap-2">
                  <label className="min-w-[12rem] text-xs font-medium text-slate-600">
                    Опросник
                    <select
                      className="mt-1 w-full max-w-md rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 disabled:opacity-60"
                      value={qnrSelectedId}
                      disabled={qnrListLoading || qnrList.length === 0}
                      onChange={(e) => setQnrSelectedId(e.target.value)}
                    >
                      <option value="">
                        {qnrListLoading ? "Загрузка…" : qnrList.length === 0 ? "Нет опросников в организации" : "— выберите —"}
                      </option>
                      {qnrList.map((q) => (
                        <option key={q.id} value={q.id}>
                          {q.title || "Без названия"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    disabled={qnrBusy || qnrListLoading || !qnrSelectedId}
                    onClick={sendQuestionnaireLink}
                    className="inline-flex items-center gap-2 rounded-xl border border-teal-600 bg-white px-4 py-2 text-sm font-semibold text-teal-800 hover:bg-teal-50 disabled:opacity-50"
                  >
                    {qnrBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                    Отправить ссылку на опросник
                  </button>
                </div>
                {qnrMsg ? <p className="mt-2 text-sm text-slate-700">{qnrMsg}</p> : null}
              </div>
            </section>
          </div>
        ) : null}
      </div>
      )}

      {patientCardQrOpen && patientCardPublicUrl ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-[2px]"
          role="presentation"
          onClick={() => setPatientCardQrOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="patient-card-qr-title"
            className="relative max-h-[90vh] w-full max-w-sm overflow-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="absolute right-3 top-3 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              title="Закрыть"
              aria-label="Закрыть"
              onClick={() => setPatientCardQrOpen(false)}
            >
              <X className="h-5 w-5" aria-hidden />
            </button>
            <h2 id="patient-card-qr-title" className="pr-10 text-base font-semibold text-slate-900">
              QR: ссылка на карту пациента
            </h2>
            <p className="mt-1 text-xs text-slate-600">Публичная страница личного кабинета по этой ссылке.</p>
            <div className="mt-4 flex justify-center rounded-xl bg-white p-3 ring-1 ring-slate-100">
              <QRCode value={patientCardPublicUrl} size={220} level="M" />
            </div>
            <p className="mt-4 break-all font-mono text-[11px] leading-snug text-slate-700">{patientCardPublicUrl}</p>
          </div>
        </div>
      ) : null}

      {qrModalOpen && misMaxRegistrationQrValue ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-[2px]"
          role="presentation"
          onClick={() => setQrModalOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="mis-qr-title"
            className="relative max-h-[90vh] w-full max-w-sm overflow-auto rounded-2xl border border-slate-200 bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              type="button"
              className="absolute right-3 top-3 rounded-lg p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              title="Закрыть"
              aria-label="Закрыть"
              onClick={() => setQrModalOpen(false)}
            >
              <X className="h-5 w-5" aria-hidden />
            </button>
            <h2 id="mis-qr-title" className="pr-10 text-base font-semibold text-slate-900">
              QR: открыть бота в MAX
            </h2>
            <p className="mt-1 text-xs text-slate-600">
              {misMaxBotLinkApp
                ? "В QR закодирована ссылка max://max.ru/… — при сканировании камерой обычно открывается приложение MAX."
                : "Отсканируйте и отправьте боту команду из текста ниже."}
            </p>
            <div className="mt-4 flex justify-center rounded-xl bg-white p-3 ring-1 ring-slate-100">
              <QRCode value={misMaxRegistrationQrValue} size={220} level="M" />
            </div>
            {misMaxBotLinkHttps ? (
              <p className="mt-4 text-xs text-slate-600">
                Открыть в браузере:{" "}
                <a
                  href={misMaxBotLinkHttps}
                  className="break-all font-mono text-[11px] font-medium text-violet-800 underline"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {misMaxBotLinkHttps}
                </a>
              </p>
            ) : null}
            {misMaxBotLinkApp ? (
              <p className="mt-2 break-all font-mono text-[10px] leading-snug text-slate-500">{misMaxBotLinkApp}</p>
            ) : null}
            {misMaxStartCommand ? (
              <p className="mt-3 break-all font-mono text-[11px] leading-snug text-slate-700">{misMaxStartCommand}</p>
            ) : null}
          </div>
        </div>
      ) : null}
    </div>
  );
}
