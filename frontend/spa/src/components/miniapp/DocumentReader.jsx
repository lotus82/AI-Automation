import axios from "axios";
import { Button, Flex, Panel, Spinner, Typography } from "@maxhub/max-ui";
import { ChevronDown, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

/**
 * Читалка для Mini App: дерево книг/глав, стихи выбранной главы.
 * Данные: GET /api/public/documents/{documentId}
 */
export function DocumentReader({ documentId, pageTitle, introHtml, themeColor }) {
  const accent = themeColor && /^#[0-9a-fA-F]{3,8}$/.test(themeColor.trim()) ? themeColor.trim() : "#4f46e5";
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [bundle, setBundle] = useState(null);
  const [tocOpen, setTocOpen] = useState(false);
  const [activeChapter, setActiveChapter] = useState(null);
  /** Аккордеон оглавления: одна раскрытая книга, одна «открытая» глава внутри неё */
  const [tocExpandedBookId, setTocExpandedBookId] = useState(null);
  const [tocExpandedChapterId, setTocExpandedChapterId] = useState(null);

  const load = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError(null);
    try {
      const { data } = await axios.get(`/api/public/documents/${documentId}`);
      setBundle(data);
      const tree = data?.tree || [];
      const firstCh = findFirstChapter(tree);
      setActiveChapter(firstCh);
    } catch (e) {
      const d = e?.response?.data?.detail;
      setError(typeof d === "string" ? d : e?.message || "Ошибка загрузки");
      setBundle(null);
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  useEffect(() => {
    load();
  }, [load]);

  const verses = useMemo(() => {
    if (!activeChapter?.children?.length) return [];
    return activeChapter.children.filter((n) => n && (n.node_type === "verse" || n.node_type === "text"));
  }, [activeChapter]);

  if (loading) {
    return (
      <Flex direction="column" align="center" gap={12} style={{ padding: 32 }}>
        <Spinner />
        <Typography.Body>Загрузка текста…</Typography.Body>
      </Flex>
    );
  }

  if (error) {
    return (
      <div style={{ padding: 16 }}>
        <Typography.Body style={{ color: "#b91c1c" }}>{error}</Typography.Body>
        <Button style={{ marginTop: 12 }} onClick={load}>
          Повторить
        </Button>
      </div>
    );
  }

  const docTitle = bundle?.document?.title || pageTitle || "Документ";

  return (
    <div style={{ position: "relative", minHeight: "100%" }}>
      <div style={{ padding: "12px 16px 8px", borderBottom: "1px solid #e5e7eb" }}>
        <Flex justify="space-between" align="center" gap={8}>
          <Typography.Title style={{ margin: 0, fontSize: 18, lineHeight: 1.3 }}>{docTitle}</Typography.Title>
          <Button
            size="s"
            mode="secondary"
            onClick={() => {
              setTocExpandedBookId(null);
              setTocExpandedChapterId(null);
              setTocOpen(true);
            }}
          >
            Оглавление
          </Button>
        </Flex>
      </div>

      {introHtml ? (
        <div
          className="miniapp-page-content"
          style={{ padding: "12px 16px", fontSize: 14, color: "#4b5563", lineHeight: 1.5 }}
          dangerouslySetInnerHTML={{ __html: introHtml }}
        />
      ) : null}

      {activeChapter ? (
        <div style={{ padding: "8px 16px 24px" }}>
          <Typography.Title style={{ fontSize: 17, margin: "0 0 12px", color: "#111827" }}>
            {activeChapter.title}
          </Typography.Title>
          {verses.length === 0 ? (
            <Typography.Body style={{ color: "#6b7280" }}>В этой главе нет стихов.</Typography.Body>
          ) : (
            <Flex direction="column" gap={10}>
              {verses.map((v) => {
                const num =
                  v.node_type === "verse" && v.title ? String(v.title).replace(/^Стих\s+/i, "").trim() : "";
                return (
                  <p
                    key={v.id}
                    style={{
                      fontSize: 17,
                      lineHeight: 1.65,
                      color: "#1f2937",
                      margin: 0,
                    }}
                  >
                    {v.node_type === "verse" ? (
                      <>
                        <span style={{ fontWeight: 700, color: accent, marginRight: 8, fontSize: 15 }}>{num}</span>
                        {v.content || ""}
                      </>
                    ) : (
                      v.content || v.title
                    )}
                  </p>
                );
              })}
            </Flex>
          )}
        </div>
      ) : (
        <div style={{ padding: 24, textAlign: "center" }}>
          <Typography.Body style={{ color: "#6b7280" }}>Выберите главу в оглавлении.</Typography.Body>
        </div>
      )}

      {tocOpen ? (
        <div
          role="presentation"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 50,
            background: "rgba(15, 23, 42, 0.45)",
          }}
          onClick={() => setTocOpen(false)}
        >
          <Panel
            role="dialog"
            aria-label="Оглавление"
            onClick={(e) => e.stopPropagation()}
            style={{
              position: "absolute",
              top: 0,
              right: 0,
              bottom: 0,
              width: "min(100%, 360px)",
              maxWidth: "100vw",
              overflowY: "auto",
              boxShadow: "-4px 0 24px rgba(0,0,0,0.12)",
              borderRadius: 0,
            }}
          >
            <div style={{ padding: "12px 12px 8px", borderBottom: "1px solid #e5e7eb" }}>
              <Flex justify="space-between" align="center">
                <Typography.Title style={{ margin: 0, fontSize: 16 }}>Оглавление</Typography.Title>
                <Button size="s" mode="ghost" onClick={() => setTocOpen(false)}>
                  Закрыть
                </Button>
              </Flex>
            </div>
            <div style={{ padding: "8px 0 16px" }}>
              <TocTree
                nodes={bundle?.tree || []}
                expandedBookId={tocExpandedBookId}
                expandedChapterId={tocExpandedChapterId}
                activeChapterId={activeChapter?.id || null}
                accent={accent}
                onToggleBook={(bookId) => {
                  setTocExpandedBookId((prev) => (prev === bookId ? null : bookId));
                  setTocExpandedChapterId(null);
                }}
                onPickChapter={(ch) => {
                  setTocExpandedChapterId(ch.id);
                  setActiveChapter(ch);
                  setTocOpen(false);
                }}
              />
            </div>
          </Panel>
        </div>
      ) : null}
    </div>
  );
}

function findFirstChapter(tree) {
  for (const book of tree || []) {
    for (const ch of book.children || []) {
      if (ch.node_type === "chapter") return ch;
    }
  }
  return null;
}

function TocTree({
  nodes,
  expandedBookId,
  expandedChapterId,
  activeChapterId,
  accent,
  onToggleBook,
  onPickChapter,
}) {
  const list = nodes || [];
  return (
    <Flex direction="column" gap={0}>
      {list.map((book) => {
        const bookOpen = expandedBookId === book.id;
        const chapters = (book.children || []).filter((n) => n.node_type === "chapter");
        return (
          <div key={book.id} style={{ marginBottom: 4, borderBottom: "1px solid #f3f4f6" }}>
            <button
              type="button"
              onClick={() => onToggleBook(book.id)}
              style={{
                display: "flex",
                width: "100%",
                alignItems: "center",
                gap: 8,
                padding: "10px 12px 10px 14px",
                border: "none",
                background: bookOpen ? "#f0fdf4" : "#f9fafb",
                fontWeight: 600,
                fontSize: 14,
                color: "#374151",
                cursor: "pointer",
                textAlign: "left",
              }}
            >
              <span style={{ display: "flex", color: accent, flexShrink: 0 }} aria-hidden>
                {bookOpen ? <ChevronDown size={18} strokeWidth={2} /> : <ChevronRight size={18} strokeWidth={2} />}
              </span>
              <span style={{ flex: 1, minWidth: 0 }}>{book.title}</span>
            </button>
            {bookOpen ? (
              <Flex direction="column" gap={0} style={{ background: "#fff" }}>
                {chapters.map((ch) => {
                  const chOpen = expandedChapterId === ch.id;
                  const isActive = activeChapterId === ch.id;
                  const compact = expandedChapterId != null && !chOpen;
                  return (
                    <button
                      key={ch.id}
                      type="button"
                      onClick={() => onPickChapter(ch)}
                      style={{
                        display: "flex",
                        width: "100%",
                        alignItems: "center",
                        gap: 6,
                        textAlign: "left",
                        padding: compact ? "6px 14px 6px 36px" : "10px 14px 10px 36px",
                        border: "none",
                        borderTop: "1px solid #f3f4f6",
                        background: chOpen || isActive ? "rgba(79, 70, 229, 0.06)" : "#fff",
                        fontSize: compact ? 13 : 15,
                        fontWeight: chOpen || isActive ? 600 : 500,
                        color: compact ? "#6b7280" : "#111827",
                        cursor: "pointer",
                        lineHeight: compact ? 1.25 : 1.35,
                        WebkitTapHighlightColor: "transparent",
                      }}
                    >
                      <span style={{ color: accent, fontWeight: 700, flexShrink: 0, fontSize: compact ? 12 : 13 }}>
                        {chOpen || isActive ? "▾" : "›"}
                      </span>
                      <span style={{ flex: 1, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
                        {ch.title}
                      </span>
                    </button>
                  );
                })}
              </Flex>
            ) : null}
          </div>
        );
      })}
    </Flex>
  );
}
