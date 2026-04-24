import { BookOpen, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import api from "../api/client.js";
import { PAGE_H1, PAGE_HEADER, PAGE_SECTION_ICON, PAGE_TEXT, PAGE_TITLE_ICON } from "../styles/pageLayout.js";
import { IconDeleteButton } from "../components/ui/IconActionButtons.jsx";
import { formatDateTimeRu } from "../utils/dateTimeFormat.js";

function formatApiDetail(err) {
  const body = err?.response?.data;
  const status = err?.response?.status;
  const det = body?.detail;
  if (typeof det === "string") return det;
  if (Array.isArray(det)) {
    return det
      .map((x) => (typeof x === "object" && x != null ? x.msg ?? x : x))
      .join("; ");
  }
  if (det != null) return JSON.stringify(det);
  if (status) return `Ошибка ${status}`;
  return err?.message ?? String(err);
}

export function KnowledgePage() {
  const fileInputRef = useRef(null);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [description, setDescription] = useState("");
  const [uploadMsg, setUploadMsg] = useState("");
  const [uploadMsgKind, setUploadMsgKind] = useState(null);
  const [uploading, setUploading] = useState(false);

  const [items, setItems] = useState([]);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState(false);

  const fileNamesLabel =
    selectedFiles.length === 0
      ? "Файлы не выбраны"
      : selectedFiles.map((f) => f.name).join(", ");

  const loadList = useCallback(async () => {
    setListLoading(true);
    setListError(false);
    try {
      const { data } = await api.get("/knowledge/items");
      setItems(Array.isArray(data) ? data : []);
    } catch (e) {
      console.error(e);
      setItems([]);
      setListError(true);
    } finally {
      setListLoading(false);
    }
  }, []);

  useEffect(() => {
    loadList();
  }, [loadList]);

  const onFilesChange = (e) => {
    setSelectedFiles(Array.from(e.target.files || []));
  };

  const onUploadSubmit = async (ev) => {
    ev.preventDefault();
    if (!selectedFiles.length) {
      setUploadMsg("Выберите файлы.");
      setUploadMsgKind("err");
      return;
    }
    const fd = new FormData();
    selectedFiles.forEach((f) => {
      fd.append("files", f);
    });
    const desc = description.trim();
    if (desc) fd.append("description", desc);

    setUploading(true);
    setUploadMsg("Загрузка и индексация…");
    setUploadMsgKind(null);
    try {
      const { data } = await api.post("/knowledge/upload", fd);
      setUploadMsg(
        `Добавлено фрагментов: ${data?.created_count ?? 0}.`,
      );
      setUploadMsgKind("ok");
      setSelectedFiles([]);
      setDescription("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await loadList();
    } catch (e) {
      setUploadMsg(formatApiDetail(e) || "Ошибка загрузки");
      setUploadMsgKind("err");
    } finally {
      setUploading(false);
    }
  };

  const onDelete = async (id) => {
    if (!window.confirm("Удалить этот фрагмент из базы знаний?")) return;
    try {
      await api.delete(`/knowledge/items/${encodeURIComponent(id)}`);
      setItems((prev) => prev.filter((r) => String(r.id) !== String(id)));
    } catch (e) {
      const st = e?.response?.status;
      if (st === 404) {
        window.alert("Уже удалено");
        await loadList();
        return;
      }
      window.alert(e?.message || "Ошибка удаления");
    }
  };

  const inputClass =
    "w-full rounded-lg border border-slate-600 bg-slate-900/80 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-500";
  const labelClass = "mb-1 block text-sm font-medium text-slate-200";
  const panelClass =
    "mb-8 rounded-xl border border-slate-700/80 bg-slate-800/40 p-5 shadow-sm";
  const btnPrimary =
    "inline-flex items-center gap-2 rounded-lg bg-sky-600 px-4 py-2.5 text-sm font-medium text-white shadow hover:bg-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-400 disabled:opacity-50";
  const btnSecondary =
    "inline-flex cursor-pointer items-center gap-2 rounded-lg border border-slate-600 bg-slate-800 px-4 py-2.5 text-sm text-slate-200 hover:bg-slate-700";
  const uploadMsgClass =
    uploadMsgKind === "err"
      ? "text-red-400"
      : uploadMsgKind === "ok"
        ? "text-emerald-400"
        : "text-slate-400";

  const accept =
    ".txt,.xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/plain";

  return (
    <div className="w-full min-w-0 text-slate-100">
      <header className={PAGE_HEADER}>
        <BookOpen className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
        <h1 className={PAGE_H1}>База знаний</h1>
      </header>

      <section className={panelClass} aria-labelledby="kn-upload-title">
        <h2
          id="kn-upload-title"
          className="mb-4 flex items-center gap-2 text-lg font-semibold text-slate-100"
        >
          <Upload className={PAGE_SECTION_ICON} strokeWidth={1.5} aria-hidden />
          Загрузка файлов
        </h2>
        <form className="space-y-4" onSubmit={onUploadSubmit}>
          <div>
            <span className={labelClass}>Файлы (.txt, .xlsx)</span>
            <div className="flex flex-wrap items-center gap-3">
              <input
                ref={fileInputRef}
                id="knowledge-files"
                name="files"
                type="file"
                accept={accept}
                multiple
                required
                className="sr-only"
                onChange={onFilesChange}
              />
              <label htmlFor="knowledge-files" className={btnSecondary}>
                📁 Выбрать файлы
              </label>
              <span
                id="knowledge-file-names"
                className="min-w-0 flex-1 text-sm text-slate-400"
              >
                {fileNamesLabel}
              </span>
            </div>
          </div>
          <div>
            <label className={labelClass} htmlFor="knowledge-description">
              Описание
            </label>
            <textarea
              id="knowledge-description"
              className={`${inputClass} resize-y`}
              rows={2}
              placeholder="Кратко: откуда документ, для каких вопросов использовать (попадёт в контекст RAG вместе с текстом)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
          <div>
            <button
              type="submit"
              className={btnPrimary}
              id="btn-knowledge-upload"
              disabled={uploading}
            >
              ☁ Загрузить в базу
            </button>
          </div>
        </form>
        <p
          id="knowledge-upload-msg"
          className={`mt-3 min-h-[1.25rem] text-sm ${uploadMsgClass}`}
          aria-live="polite"
        >
          {uploadMsg}
        </p>
      </section>

      <h2 className="mb-3 text-lg font-semibold text-slate-100">
        📋 Загруженные фрагменты
      </h2>
      <div className="overflow-x-auto rounded-xl border border-slate-700/80 bg-slate-800/40 p-4">
        {listLoading ? (
          <p className="text-slate-400">Загрузка…</p>
        ) : listError ? (
          <p className="text-red-400">Не удалось загрузить список.</p>
        ) : items.length === 0 ? (
          <p className="text-slate-500">
            Пока нет записей. Загрузите .txt или .xlsx выше.
          </p>
        ) : (
          <table className="w-full min-w-[640px] border-collapse text-left text-sm">
            <thead>
              <tr className="border-b border-slate-600 text-xs uppercase tracking-wide text-slate-400">
                <th className="px-2 py-2 font-medium">Заголовок</th>
                <th className="px-2 py-2 font-medium">Описание</th>
                <th className="px-2 py-2 font-medium">Фрагмент</th>
                <th className="px-2 py-2 font-medium">Вектор</th>
                <th className="px-2 py-2 font-medium">Дата</th>
                <th className="px-2 py-2 font-medium" aria-label="Действия" />
              </tr>
            </thead>
            <tbody>
              {items.map((r) => {
                const id = String(r.id);
                return (
                  <tr
                    key={id}
                    className="border-b border-slate-700/80 hover:bg-slate-800/60"
                    data-id={id}
                  >
                    <td className="max-w-[12rem] px-2 py-2 align-top font-medium text-slate-100">
                      {r.title}
                    </td>
                    <td className="max-w-[10rem] px-2 py-2 align-top text-slate-300">
                      {r.description || "—"}
                    </td>
                    <td className="max-w-md px-2 py-2 align-top font-mono text-xs text-slate-400">
                      {r.content_preview}
                    </td>
                    <td className="px-2 py-2 align-top">
                      {r.has_embedding ? (
                        <span className="inline-block rounded-full bg-emerald-950/60 px-2 py-0.5 text-xs text-emerald-300">
                          есть
                        </span>
                      ) : (
                        <span className="inline-block rounded-full bg-amber-950/60 px-2 py-0.5 text-xs text-amber-200">
                          нет
                        </span>
                      )}
                    </td>
                    <td className="whitespace-nowrap px-2 py-2 align-top text-slate-400">
                      {formatDateTimeRu(r.created_at)}
                    </td>
                    <td className="px-2 py-2 align-top">
                      <IconDeleteButton title="Удалить фрагмент" onClick={() => onDelete(id)} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
