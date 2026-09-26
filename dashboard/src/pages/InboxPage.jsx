import { useEffect, useState } from "react";
import { api } from "../api";
import { Badge } from "../components/Badge";
import { StatusDot } from "../components/StatusDot";

export function InboxPage() {
  const [flags, setFlags] = useState(null);
  const [error, setError] = useState(null);
  const [showReviewed, setShowReviewed] = useState(false);
  const [refreshing, setRefreshing] = useState(false);

  function load() {
    setError(null);
    api
      .getInbox(showReviewed ? {} : { reviewed: false })
      .then(setFlags)
      .catch((err) => setError(err.message));
  }

  useEffect(load, [showReviewed]);

  async function markReviewed(id) {
    await api.updateInboxFlag(id, true);
    load();
  }

  async function handleRefresh() {
    setRefreshing(true);
    setError(null);
    try {
      await api.refreshInbox();
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div style={{ maxWidth: "var(--page-width)", margin: "0 auto", padding: "var(--space-8) var(--page-margin)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "var(--space-6)" }}>
        <h1>Inbox</h1>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <button
            onClick={() => setShowReviewed((v) => !v)}
            style={{
              padding: "6px var(--space-3)",
              borderRadius: "var(--radius-pill)",
              fontSize: 13,
              fontWeight: 500,
              background: showReviewed ? "var(--bg-recessed)" : "transparent",
              color: showReviewed ? "var(--text-primary)" : "var(--text-muted)",
            }}
          >
            {showReviewed ? "Showing all" : "Showing unreviewed"}
          </button>
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{
              boxShadow: "var(--shadow-border)",
              padding: "6px var(--space-3)",
              borderRadius: "var(--radius-pill)",
              fontSize: 13,
              fontWeight: 500,
              color: "var(--text-primary)",
              opacity: refreshing ? 0.6 : 1,
            }}
          >
            {refreshing ? "Checking…" : "Refresh"}
          </button>
        </div>
      </div>

      {error && (
        <p style={{ color: "var(--status-red)" }}>
          {error.includes("502")
            ? `Couldn't refresh inbox (${error}). Check Gmail OAuth setup on gateway-service.`
            : `Couldn't reach gateway-service (${error}). Is it running at the configured API URL?`}
        </p>
      )}

      {!error && flags === null && <p>Loading inbox…</p>}

      {!error && flags && flags.length === 0 && (
        <p>Nothing here. Click Refresh to check for new mail.</p>
      )}

      {flags && flags.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {flags.map((f) => (
            <div
              key={f.id}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "var(--space-4)",
                padding: "var(--space-4)",
                borderRadius: "var(--radius-default)",
              }}
            >
              <StatusDot color={f.importance === "important" ? "orange" : "gray"} size={10} />

              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{f.subject || "(no subject)"}</div>
                <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>{f.sender}</div>
                {f.reasoning && (
                  <div style={{ fontSize: 13, color: "var(--text-secondary)", marginTop: 4 }}>{f.reasoning}</div>
                )}
              </div>

              <Badge dotColor={f.importance === "important" ? "orange" : "gray"}>{f.importance}</Badge>

              {!f.reviewed && (
                <button
                  onClick={() => markReviewed(f.id)}
                  style={{ boxShadow: "var(--shadow-border)", padding: "4px 10px", fontWeight: 500 }}
                >
                  Mark reviewed
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}