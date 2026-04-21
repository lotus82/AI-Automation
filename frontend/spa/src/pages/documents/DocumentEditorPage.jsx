import { ArrowLeft, ChevronDown, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import api from "../../api/client.js";
import { useAuthStore } from "../../store/authStore.js";
import { PAGE_SHELL, PAGE_TEXT } from "../../styles/pageLayout.js";

function formatApiDetail(d) {
  if (d == null) return "";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    return d
      .map((item) => (typeof item === "string" ? item : item?.msg ? String(item.msg) : JSON.stringify(item)))
      .filter(Boolean)
      .join("; ");
  }
  if (typeof d === "object") return d.message ? String(d.message) : JSON.stringify(d);
  return String(d);
}

const inputClass =
  "mt-1 block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none";

function flattenTree(nodes, depth = 0, acc = []) {
  if (!Array.isArray(nodes)) return acc;
  for (const n of nodes) {
    if (!n) continue;
    acc.push({ node: n, depth });
    if (n.children?.length) flattenTree(n.children, depth + 1, acc);
  }
  return acc;
}

/** Все id узлов, у которых есть дети — для «Развернуть всё». */
function collectExpandableIds(nodes, acc = new Set()) {
  if (!Array.isArray(nodes)) return acc;
  for (const n of nodes) {
    if (!n?.id) continue;
    if (n.children?.length) {
      acc.add(n.id);
      collectExpandableIds(n.children, acc);
    }
  }
  return acc;
}

function NodeTreeItem({ node, depth, expanded, toggle, selectedId, onSelect }) {
  const hasKids = Array.isArray(node.children) && node.children.length > 0;
  const isOpen = expanded.has(node.id);
  const isSel = selectedId === node.id;
  const pad = 8 + depth * 14;

  return (
    <div>
      <div
        className={`flex items-center gap-1 border-b border-slate-800/80 py-1.5 pr-2 text-sm ${
          isSel ? "bg-emerald-900/25 text-emerald-100" : "text-slate-200 hover:bg-slate-800/50"
        }`}
        style={{ paddingLeft: pad }}
      >
        {hasKids ? (
          <button
            type="button"
            aria-expanded={isOpen}
            onClick={() => toggle(node.id)}
            className="shrink-0 rounded p-0.5 text-slate-400 hover:bg-slate-700 hover:text-white"
          >
            {isOpen ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
          </button>
        ) : (
          <span className="inline-block w-5 shrink-0" />
        )}
        <button
          type="button"
          onClick={() => onSelect(node)}
          className="min-w-0 flex-1 truncate text-left font-medium"
        >
          <span className="text-[11px] uppercase text-slate-500">{node.node_type}</span>{" "}
          {node.title || "—"}
        </button>
      </div>
      {hasKids && isOpen
        ? node.children.map((ch) => (
            <NodeTreeItem
              key={ch.id}
              node={ch}
              depth={depth + 1}
              expanded={expanded}
              toggle={toggle}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))
        : null}
    </div>
  );
}

export function DocumentEditorPage() {
  const { id: documentId } = useParams();
  const user = useAuthStore((s) => s.user);
  const role = user?.role;
  const canAccess = role === "super_admin" || role === "org_admin" || role === "director";

  const [docMeta, setDocMeta] = useState(null);
  const [tree, setTree] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());
  const [form, setForm] = useState({ title: "", content: "", order_index: 0 });
  const [saving, setSaving] = useState(false);

  const loadAll = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError("");
    try {
      const [docRes, treeRes] = await Promise.all([
        api.get(`/documents/${documentId}`),
        api.get(`/documents/${documentId}/nodes`, { params: { nested: true } }),
      ]);
      setDocMeta(docRes.data);
      const t = Array.isArray(treeRes.data) ? treeRes.data : [];
      setTree(t);
      setExpanded(() => {
        const next = new Set();
        for (const b of t) {
          if (b?.id) next.add(b.id);
        }
        return next;
      });
    } catch (e) {
      setError(formatApiDetail(e?.response?.data?.detail) || e?.message || String(e));
      setDocMeta(null);
      setTree([]);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    if (canAccess && documentId) loadAll();
  }, [canAccess, documentId, loadAll]);

  const flat = useMemo(() => flattenTree(tree), [tree]);

  const onSelect = useCallback((node) => {
    setSelected(node);
    setForm({
      title: node.title || "",
      content: node.content || "",
      order_index: Number(node.order_index) || 0,
    });
  }, []);

  const toggle = useCallback((id) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const collapseAllTree = useCallback(() => {
    setExpanded(new Set());
  }, []);

  const expandAllTree = useCallback(() => {
    setExpanded(collectExpandableIds(tree));
  }, [tree]);

  const onSave = async (e) => {
    e.preventDefault();
    if (!selected?.id || !documentId) return;
    setSaving(true);
    setError("");
    try {
      const { data } = await api.put(`/documents/${documentId}/nodes/${selected.id}`, {
        title: form.title.trim(),
        content: form.content,
        order_index: Math.max(0, Number(form.order_index) || 0),
      });
      setSelected(data);
      setTree((prev) => patchNodeInTree(prev, data));
    } catch (err) {
      setError(formatApiDetail(err?.response?.data?.detail) || err?.message || String(err));
    } finally {
      setSaving(false);
    }
  };

  if (!user) return null;
  if (!canAccess) return <Navigate to="/scenarios/qa-analytics" replace />;
  if (!documentId) return <Navigate to="/documents" replace />;

  return (
    <div className={`${PAGE_SHELL} ${PAGE_TEXT} px-4 py-6 sm:px-6`}>
      <header className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            to="/documents"
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800/70 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-700"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            К списку
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-xl font-semibold text-white">
              {loading ? "Загрузка…" : docMeta?.title || "Документ"}
            </h1>
            <p className="text-sm text-slate-400">Дерево узлов и правка текста</p>
          </div>
        </div>
      </header>

      {error ? (
        <div className="mb-4 rounded-lg border border-red-600/40 bg-red-600/10 p-3 text-sm text-red-200">{error}</div>
      ) : null}

      <div className="grid min-h-[480px] gap-4 lg:grid-cols-2">
        <div className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/40">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
            <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
              Структура ({flat.length} узлов)
            </div>
            {!loading && tree.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                <button
                  type="button"
                  onClick={collapseAllTree}
                  className="rounded-md border border-slate-600 bg-slate-800/80 px-2 py-1 text-[11px] font-medium text-slate-200 hover:bg-slate-700"
                >
                  Свернуть всё
                </button>
                <button
                  type="button"
                  onClick={expandAllTree}
                  className="rounded-md border border-slate-600 bg-slate-800/80 px-2 py-1 text-[11px] font-medium text-slate-200 hover:bg-slate-700"
                >
                  Развернуть всё
                </button>
              </div>
            ) : null}
          </div>
          <div className="flex-1 overflow-y-auto p-1">
            {loading ? (
              <div className="p-4 text-sm text-slate-500">Загрузка дерева…</div>
            ) : tree.length === 0 ? (
              <div className="p-4 text-sm text-slate-500">
                Узлов нет. Загрузите .txt на странице списка документов.
              </div>
            ) : (
              tree.map((n) => (
                <NodeTreeItem
                  key={n.id}
                  node={n}
                  depth={0}
                  expanded={expanded}
                  toggle={toggle}
                  selectedId={selected?.id}
                  onSelect={onSelect}
                />
              ))
            )}
          </div>
        </div>

        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
          {!selected ? (
            <p className="text-sm text-slate-500">Выберите узел слева.</p>
          ) : (
            <form onSubmit={onSave} className="space-y-4">
              <div className="text-xs text-slate-500">
                Тип: <span className="text-slate-300">{selected.node_type}</span>
              </div>
              <label className="block text-xs font-medium text-slate-300">
                Заголовок
                <input
                  type="text"
                  value={form.title}
                  onChange={(e) => setForm((p) => ({ ...p, title: e.target.value }))}
                  className={inputClass}
                  required
                  maxLength={512}
                />
              </label>
              <label className="block text-xs font-medium text-slate-300">
                Порядок (order_index)
                <input
                  type="number"
                  min={0}
                  max={10000000}
                  value={form.order_index}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, order_index: Math.max(0, Number(e.target.value) || 0) }))
                  }
                  className={inputClass}
                />
              </label>
              <label className="block text-xs font-medium text-slate-300">
                Содержимое
                <textarea
                  value={form.content}
                  onChange={(e) => setForm((p) => ({ ...p, content: e.target.value }))}
                  className={`${inputClass} min-h-[280px] font-mono text-[13px]`}
                  maxLength={500000}
                  placeholder="Текст стиха или абзаца"
                />
              </label>
              <button
                type="submit"
                disabled={saving}
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-500 disabled:opacity-60"
              >
                {saving ? "Сохранение…" : "Сохранить узел"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}

function patchNodeInTree(nodes, updated) {
  if (!Array.isArray(nodes)) return nodes;
  return nodes.map((n) => {
    if (n.id === updated.id) {
      return {
        ...n,
        title: updated.title,
        content: updated.content,
        order_index: updated.order_index,
      };
    }
    if (n.children?.length) {
      return { ...n, children: patchNodeInTree(n.children, updated) };
    }
    return n;
  });
}
