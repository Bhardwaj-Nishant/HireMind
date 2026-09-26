import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { Badge } from "../components/Badge";

const DRAFT_LABELS = {
  resume: "Resume",
  cover_letter: "Cover letter",
  recruiter_email: "Recruiter email",
};
const DRAFT_ORDER = ["resume", "cover_letter", "recruiter_email"];

export function DraftsPage() {
  const [drafts, setDrafts] = useState(null);
  const [error, setError] = useState(null);
  const [expandedMatchId, setExpandedMatchId] = useState(null);
  const [activeType, setActiveType] = useState({}); // matchId -> draft_type
  const [pushingId, setPushingId] = useState(null);

  function load() {
    setError(null);
    api.getAllDrafts().then(setDrafts).catch((err) => setError(err.message));
  }

  useEffect(load, []);

  // Group flat draft list into one block per match/job, so resume + cover
  // letter + email for the same posting appear together instead of as
  // three separate entries.
  const groups = useMemo(() => {
    if (!drafts) return [];
    const byMatch = new Map();
    for (const d of drafts) {
      if (!byMatch.has(d.match_id)) {
        byMatch.set(d.match_id, {
          match_id: d.match_id,
          job_title: d.job_title,
          job_company: d.job_company,
          recruiter_email: d.recruiter_email,
          latest_created_at: d.created_at,
          items: [],
        });
      }
      const group = byMatch.get(d.match_id);
      group.items.push(d);
      if (d.created_at > group.latest_created_at) group.latest_created_at = d.created_at;
    }
    return [...byMatch.values()]
      .map((g) => ({ ...g, items: g.items.sort((a, b) => DRAFT_ORDER.indexOf(a.draft_type) - DRAFT_ORDER.indexOf(b.draft_type)) }))
      .sort((a, b) => (a.latest_created_at < b.latest_created_at ? 1 : -1));
  }, [drafts]);

  async function handlePush(draftId) {
    setPushingId(draftId);
    try {
      await api.pushDraftToGmail(draftId);
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setPushingId(null);
    }
  }

  return (
    <div style={{ maxWidth: "var(--page-width)", margin: "0 auto", padding: "var(--space-8) var(--page-margin)" }}>
      <h1 style={{ marginBottom: "var(--space-6)" }}>Drafts</h1>

      {error && (
        <p style={{ color: "var(--status-red)" }}>
          Couldn't reach gateway-service ({error}). Is it running at the configured API URL?
        </p>
      )}

      {!error && drafts === null && <p>Loading drafts…</p>}

      {!error && drafts && drafts.length === 0 && (
        <p>No drafts yet. Open a match and generate resume/cover letter/email drafts for it.</p>
      )}

      {groups.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {groups.map((g) => {
            const isOpen = expandedMatchId === g.match_id;
            const active =
              g.items.find((d) => d.draft_type === activeType[g.match_id]) || g.items[0];
            const emailDraft = g.items.find((d) => d.draft_type === "recruiter_email");

            return (
              <div key={g.match_id} style={{ borderBottom: "var(--shadow-border)" }}>
                <div
                  onClick={() => setExpandedMatchId(isOpen ? null : g.match_id)}
                  role="button"
                  tabIndex={0}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "var(--space-4)",
                    padding: "var(--space-4)",
                    cursor: "pointer",
                  }}
                >
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 14, fontWeight: 500 }}>{g.job_title}</div>
                    <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
                      {g.job_company}
                      {g.recruiter_email ? ` · ${g.recruiter_email}` : ""}
                    </div>
                  </div>

                  <div style={{ display: "flex", gap: "var(--space-2)" }}>
                    {g.items.map((d) => (
                      <Badge key={d.draft_type}>{DRAFT_LABELS[d.draft_type] || d.draft_type}</Badge>
                    ))}
                  </div>

                  {emailDraft && (
                    <Badge dotColor={emailDraft.gmail_draft_id ? "green" : "gray"}>
                      {emailDraft.gmail_draft_id ? "In Gmail" : "Not pushed"}
                    </Badge>
                  )}

                  <span style={{ color: "var(--text-muted)", fontSize: 13 }}>{isOpen ? "▲" : "▼"}</span>
                </div>

                {isOpen && (
                  <div style={{ padding: "0 var(--space-4) var(--space-6)" }}>
                    <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
                      {g.items.map((d) => (
                        <button
                          key={d.draft_type}
                          onClick={() => setActiveType((prev) => ({ ...prev, [g.match_id]: d.draft_type }))}
                          style={{
                            padding: "6px var(--space-3)",
                            borderRadius: "var(--radius-pill)",
                            fontWeight: 500,
                            fontSize: 13,
                            background: active.draft_type === d.draft_type ? "var(--bg-recessed)" : "transparent",
                            color: active.draft_type === d.draft_type ? "var(--text-primary)" : "var(--text-muted)",
                          }}
                        >
                          {DRAFT_LABELS[d.draft_type] || d.draft_type}
                        </button>
                      ))}
                    </div>

                    {active.draft_type === "recruiter_email" && !active.gmail_draft_id && (
                      <button
                        onClick={() => handlePush(active.id)}
                        disabled={pushingId === active.id}
                        style={{
                          boxShadow: "var(--shadow-border)",
                          padding: "4px 10px",
                          fontWeight: 500,
                          marginBottom: "var(--space-4)",
                          color: "var(--text-primary)",
                          opacity: pushingId === active.id ? 0.6 : 1,
                        }}
                      >
                        {pushingId === active.id ? "Pushing…" : "Push to Gmail"}
                      </button>
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
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}