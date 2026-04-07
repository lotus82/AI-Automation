import { useCallback, useId, useRef, useState } from "react";
import api from "../api/client.js";

/**
 * Телефония и автообзвон: загрузка CSV/XLSX в очередь и запуск Celery-кампании.
 */
export function TelephonyPage() {
  const formId = useId();
  const fileInputRef = useRef(null);

  const [fileName, setFileName] = useState("Файл не выбран");
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploading, setUploading] = useState(false);

  const [campaignMsg, setCampaignMsg] = useState("");
  const [campaignSending, setCampaignSending] = useState(false);

  const syncFileName = useCallback(() => {
    const input = fileInputRef.current;
    const f = input?.files?.[0];
    setFileName(f ? f.name : "Файл не выбран");
  }, []);

  const handleFileChange = () => {
    syncFileName();
    setUploadMsg("");
  };

  const handleUploadSubmit = async (e) => {
    e.preventDefault();
    const input = fileInputRef.current;
    const file = input?.files?.[0];
    if (!file) {
      setUploadMsg("Выберите файл.");
      return;
    }

    const fd = new FormData();
    fd.append("file", file);

    setUploading(true);
    setUploadMsg("Загрузка…");
    try {
      const { data } = await api.post("/dialer/queue/upload", fd);
      const n = data?.inserted != null ? data.inserted : "?";
      setUploadMsg(`Добавлено номеров: ${n}`);
      if (input) input.value = "";
      syncFileName();
    } catch (err) {
      const raw =
        err?.response?.data?.detail != null
          ? typeof err.response.data.detail === "string"
            ? err.response.data.detail
            : JSON.stringify(err.response.data.detail)
          : err?.response?.data != null
            ? JSON.stringify(err.response.data)
            : err?.message || "Ошибка";
      setUploadMsg(`Ошибка: ${raw}`);
    } finally {
      setUploading(false);
    }
  };

  const handleCampaignStart = async () => {
    setCampaignSending(true);
    setCampaignMsg("Отправка…");
    try {
      const { data } = await api.post("/dialer/campaign/start");
      setCampaignMsg(`Статус: ${data?.status ?? "ok"}`);
    } catch (err) {
      const raw =
        err?.response?.data?.detail != null
          ? typeof err.response.data.detail === "string"
            ? err.response.data.detail
            : JSON.stringify(err.response.data.detail)
          : err?.message || "Ошибка";
      setCampaignMsg(`Ошибка: ${raw}`);
    } finally {
      setCampaignSending(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-white">Телефония и автообзвон</h1>
        <p className="mt-2 text-sm text-slate-400">
          Загрузите номера в очередь <code className="rounded bg-slate-800 px-1.5 py-0.5 text-emerald-300">dialer_queue</code>
          , затем запустите кампанию — воркер Celery вызовет SIP-адаптер (пока заглушка). Входящие/события от АТС — см.{" "}
          <code className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-300">POST /api/telephony/inbound</code> и{" "}
          <code className="rounded bg-slate-800 px-1.5 py-0.5 text-slate-300">/api/telephony/event</code> в README.
        </p>
      </div>

      <section>
        <h2 className="mb-2 text-lg font-semibold text-slate-200">Загрузка номеров</h2>
        <p className="mb-4 text-sm text-slate-400">
          Файл <strong className="text-slate-300">CSV</strong> или <strong className="text-slate-300">XLSX</strong>:
          номера в <strong className="text-slate-300">первой колонке</strong> (первая строка может быть заголовком —
          некорректные строки отфильтруются).
        </p>

        <form
          className="max-w-lg space-y-4 rounded-2xl border border-slate-700/80 bg-slate-900/50 p-5 shadow-lg backdrop-blur-sm"
          onSubmit={(e) => void handleUploadSubmit(e)}
        >
          <div>
            <span className="mb-2 block text-xs font-medium text-slate-400">Файл CSV или XLSX</span>
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={fileInputRef}
                id={`${formId}-phones-file`}
                className="sr-only"
                type="file"
                accept=".csv,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
                required
                disabled={uploading}
                onChange={handleFileChange}
                aria-label="Файл CSV или XLSX"
              />
              <label
                htmlFor={`${formId}-phones-file`}
                className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm font-medium text-slate-200 hover:bg-slate-700 disabled:pointer-events-none disabled:opacity-50"
              >
                Выбрать файл
              </label>
              <span className="text-sm text-slate-500">{fileName}</span>
            </div>
          </div>
          <div>
            <button
              type="submit"
              className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
              disabled={uploading}
            >
              Загрузить в очередь
            </button>
          </div>
          {uploadMsg ? (
            <p
              className={`text-sm ${uploadMsg.startsWith("Ошибка") ? "text-red-400" : "text-slate-400"}`}
              role="status"
            >
              {uploadMsg}
            </p>
          ) : null}
        </form>
      </section>

      <section>
        <h2 className="mb-2 text-lg font-semibold text-slate-200">Запуск кампании</h2>
        <p className="mb-4 text-sm text-slate-400">
          Ставит задачу <code className="rounded bg-slate-800 px-1.5 py-0.5 text-amber-200/90">run_outbound_campaign_task</code>{" "}
          в Celery (нужен запущенный worker).
        </p>
        <button
          type="button"
          className="inline-flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white shadow hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={campaignSending}
          onClick={() => void handleCampaignStart()}
        >
          Начать обзвон (Celery)
        </button>
        {campaignMsg ? (
          <p
            className={`mt-4 text-sm ${campaignMsg.startsWith("Ошибка") ? "text-red-400" : "text-slate-400"}`}
            role="status"
          >
            {campaignMsg}
          </p>
        ) : null}
      </section>
    </div>
  );
}
