import { ExternalLink, FileCode2 } from "lucide-react";
import { PAGE_H1, PAGE_HEADER, PAGE_TEXT, PAGE_TITLE_ICON } from "../styles/pageLayout.js";

const DOCS_HREF = "/docs";

/**
 * Встроенный Swagger UI (OpenAPI) бэкенда: тот же путь, что и у FastAPI `docs_url="/docs"`.
 * На VPS nginx должен проксировать `/docs`, `/openapi.json`, `/redoc` на приложение (как `/api`).
 */
export function SwaggerPage() {
  return (
    <div className={`flex min-h-0 min-w-0 flex-col gap-4 ${PAGE_TEXT}`}>
      <header className={PAGE_HEADER}>
        <FileCode2 className={PAGE_TITLE_ICON} strokeWidth={1.5} aria-hidden />
        <h1 className={PAGE_H1}>Swagger (OpenAPI)</h1>
      </header>
      <p className="max-w-3xl text-sm text-slate-400">
        Интерактивная документация и вызовы API. Схема:{" "}
        <a className="text-emerald-400 underline hover:text-emerald-300" href="/openapi.json">
          /openapi.json
        </a>
        . Альтернатива:{" "}
        <a className="text-emerald-400 underline hover:text-emerald-300" href="/redoc">
          ReDoc
        </a>
        .
      </p>
      <p className="text-xs text-slate-500">
        Для авторизованных запросов в «Try it out» укажите токен: схема <code className="text-slate-400">HTTPBearer</code>{" "}
        (тот же JWT, что и в панели).
      </p>
      <a
        href={DOCS_HREF}
        target="_blank"
        rel="noreferrer"
        className="inline-flex w-fit items-center gap-2 rounded-lg border border-slate-600 bg-slate-800/60 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800"
      >
        <ExternalLink className="h-4 w-4 shrink-0" aria-hidden />
        Открыть /docs в новой вкладке
      </a>
      <div className="min-h-0 w-full min-w-0 flex-1">
        <iframe
          title="OpenAPI (Swagger UI)"
          src={DOCS_HREF}
          className="h-[min(78vh,56rem)] w-full min-h-[32rem] rounded-xl border border-slate-800 bg-slate-950"
          sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
        />
      </div>
    </div>
  );
}
