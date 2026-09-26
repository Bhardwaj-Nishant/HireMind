import { useEffect, useState } from "react";
import { api } from "../api";
import { Badge } from "./Badge";

const DRAFT_LABELS = {
  resume: "Tailored resume",
  cover_letter: "Cover letter",
  recruiter_email: "Recruiter email",
};

export function DraftPanel({ match, onClose, onGoToDrafts }) {
  const [drafts, setDrafts] = useState(null);
  const [activeType, setActiveType] = useState(null);
  const [error, setError] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [pushing, setPushing] = useState(false);

  function load() {
    setError(null);
    api
      .getDrafts(match.id)
      .then((data) => {
        setDrafts(data);
        setActiveType((prev) => prev ?? data[0]?.draft_type ?? null);
      })
      .catch((err) => setError(err.message));
  }

  useEffect(() => {
    setDrafts(null);
    setActiveType(null);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [match.id]);

  async function handleGenerate() {
    setGenerating(true);
    setError(null);
    try {
      const updated = await api.generateDrafts(match.id);
      setDrafts(updated);
      setActiveType((prev) => prev ?? updated[0]?.draft_type ?? null);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  }

  async function handlePushToGmail(draftId) {
    setPushing(true);
    setError(null);
    try {
      await api.pushDraftToGmail(draftId);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setPushing(false);
    }
  }

  const active = drafts?.find((d) => d.draft_type === activeType);
  const hasAnyDrafts = drafts && drafts.length > 0;
  const hasAllTypes = drafts && drafts.length >= 3;

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.2)",
        display: "flex",
        justifyContent: "flex-end",
        zIndex: 20,
      }}
      onClick={onClose}
    >
      <div
        onClick={(e) => e.stopPropagation()}
        style={{
          width: "min(560px, 100%)",
          height: "100%",
          background: "var(--bg-elevated)",
          boxShadow: "var(--shadow-large)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        <div style={{ padding: "var(--space-6)", borderBottom: "var(--shadow-border)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
            <div>
              <h3>{match.job.title}</h3>
              <p style={{ marginTop: 4 }}>{match.job.company}</p>
            </div>
            <button onClick={onClose} style={{ fontSize: 20, color: "var(--text-muted)" }}>
              ×
            </button>
          </div>

          {match.reasoning && (
            <p style={{ marginTop: "var(--space-4)", fontSize: 13, lineHeight: 1.6 }}>{match.reasoning}</p>
          )}

          {!hasAllTypes && (
            <button
              onClick={handleGenerate}
              disabled={generating}
              style={{
                marginTop: "var(--space-4)",
                boxShadow: "var(--shadow-border)",
                padding: "6px var(--space-3)",
                fontWeight: 500,
                color: "var(--text-primary)",
                opacity: generating ? 0.6 : 1,
              }}
            >
              {generating
                ? "Generating…"
                : hasAnyDrafts
                ? "Generate remaining drafts"
                : "Generate resume, cover letter & email"}
            </button>
          )}
        </div>

        {hasAnyDrafts && (
          <div style={{ padding: "0 var(--space-6)", display: "flex", gap: "var(--space-2)", marginTop: "var(--space-4)" }}>
            {drafts.map((d) => (
              <button
                key={d.draft_type}
                onClick={() => setActiveType(d.draft_type)}
                style={{
                  padding: "6px var(--space-3)",
                  borderRadius: "var(--radius-pill)",
                  fontWeight: 500,
                  fontSize: 13,
                  background: activeType === d.draft_type ? "var(--bg-recessed)" : "transparent",
                  color: activeType === d.draft_type ? "var(--text-primary)" : "var(--text-muted)",
                }}
              >
                {DRAFT_LABELS[d.draft_type] || d.draft_type}
              </button>
            ))}
          </div>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "var(--space-6)" }}>
          {error && <p style={{ color: "var(--status-red)" }}>{error}</p>}
          {!error && drafts && drafts.length === 0 && (
            <p>No drafts yet for this match — use the button above to generate them.</p>
          )}
          {active && (
            <>
              {active.draft_type === "recruiter_email" && (
                <div style={{ marginBottom: "var(--space-4)", display: "flex", alignItems: "center", gap: "var(--space-3)", flexWrap: "wrap" }}>
                  <Badge dotColor={active.gmail_draft_id ? "green" : "gray"}>
                    {active.gmail_draft_id ? "Pushed to Gmail drafts" : "Not yet pushed to Gmail"}
                  </Badge>
                  {match.job.recruiter_email && (
                    <span style={{ fontSize: 12, color: "var(--text-muted)" }}>To: {match.job.recruiter_email}</span>
                  )}
                  {!active.gmail_draft_id && (
                    <button
                      onClick={() => handlePushToGmail(active.id)}
                      disabled={pushing}
                      style={{
                        boxShadow: "var(--shadow-border)",
                        padding: "4px 10px",
                        fontWeight: 500,
                        color: "var(--text-primary)",
                        opacity: pushing ? 0.6 : 1,
                      }}
                    >
                      {pushing ? "Pushing…" : "Push to Gmail"}
                    </button>
                  )}
                  {active.gmail_draft_id && onGoToDrafts && (
                    <button
                      onClick={() => {
                        onGoToDrafts();
                        onClose();
                      }}
                      style={{ fontSize: 13, fontWeight: 500, color: "var(--accent)" }}
                    >
                      Go to Drafts →
                    </button>
                  )}
                </div>
              )}
              <pre
                style={{
                  whiteSpace: "pre-wrap",
                  fontFamily: "var(--font-sans)",
                  fontSize: 14,
                  lineHeight: 1.6,
                  color: "var(--text-primary)",
                }}
              >
                {active.content}
              </pre>
            </>
          )}
        </div>
      </div>
    </div>
  );
}