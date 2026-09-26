import { useEffect, useState } from "react";
import { api } from "../api";
import { MatchRow } from "../components/MatchRow";
import { DraftPanel } from "../components/DraftPanel";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "applied", label: "Applied" },
  { key: "dismissed", label: "Dismissed" },
];

const SOURCES = [
  { key: "internshala", label: "Internshala" },
  { key: "unstop", label: "Unstop" },
  { key: "linkedin", label: "LinkedIn" },
];

const WORK_TYPES = [
  { key: "internship", label: "Internship" },
  { key: "job", label: "Full-time" },
];

const LOCATION_MODES = [
  { key: "any", label: "Any location" },
  { key: "remote", label: "Remote" },
  { key: "onsite", label: "Onsite" },
];

function SegmentedControl({ options, value, onChange }) {
  return (
    <div style={{ display: "flex", gap: 2, background: "var(--bg-recessed)", borderRadius: "var(--radius-pill)", padding: 2 }}>
      {options.map((o) => (
        <button
          key={o.key}
          onClick={() => onChange(o.key)}
          style={{
            padding: "4px var(--space-3)",
            borderRadius: "var(--radius-pill)",
            fontSize: 12,
            fontWeight: 500,
            background: value === o.key ? "var(--bg-elevated)" : "transparent",
            boxShadow: value === o.key ? "var(--shadow-border)" : "none",
            color: value === o.key ? "var(--text-primary)" : "var(--text-muted)",
          }}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function MatchesPage({ onGoToDrafts }) {
  const [matches, setMatches] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("pending");
  const [selected, setSelected] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState(null);
  const [workType, setWorkType] = useState("internship");
  const [locationMode, setLocationMode] = useState("any");
  const [source, setSource] = useState("internshala");

  function load() {
    setError(null);
    api
      .getMatches(filter === "all" ? {} : { status: filter })
      .then(setMatches)
      .catch((err) => setError(err.message));
  }

  useEffect(load, [filter]);

  async function handleRefresh() {
    setRefreshing(true);
    setError(null);
    try {
      // max_age_days defaults to 1 on the backend — only fetches postings
      // from the last day, so results stay fresh rather than accumulating
      // stale listings.
      await api.refreshMatches({ source, work_type: workType, location: locationMode });
      setLastRefreshed(new Date());
      load();
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }

  async function handleStatusChange(id, status) {
    await api.updateMatch(id, status);
    load();
  }

  return (
    <div style={{ maxWidth: "var(--page-width)", margin: "0 auto", padding: "var(--space-8) var(--page-margin)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: "var(--space-4)" }}>
        <h1>Matches</h1>
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          {FILTERS.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              style={{
                padding: "6px var(--space-3)",
                borderRadius: "var(--radius-pill)",
                fontSize: 13,
                fontWeight: 500,
                background: filter === f.key ? "var(--bg-recessed)" : "transparent",
                color: filter === f.key ? "var(--text-primary)" : "var(--text-muted)",
              }}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "var(--space-6)" }}>
        <div style={{ display: "flex", gap: "var(--space-3)" }}>
          <SegmentedControl options={SOURCES} value={source} onChange={setSource} />
          <SegmentedControl options={WORK_TYPES} value={workType} onChange={setWorkType} />
          <SegmentedControl options={LOCATION_MODES} value={locationMode} onChange={setLocationMode} />
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          style={{
            boxShadow: "var(--shadow-border)",
            padding: "6px var(--space-3)",
            fontWeight: 500,
            color: "var(--text-primary)",
            opacity: refreshing ? 0.6 : 1,
            whiteSpace: "nowrap",
          }}
        >
          {refreshing ? "Fetching…" : "Fetch more matches"}
        </button>
      </div>

      {lastRefreshed && !refreshing && (
        <p style={{ marginTop: -16, marginBottom: "var(--space-4)", fontSize: 12, color: "var(--text-muted)" }}>
          Last refreshed {lastRefreshed.toLocaleTimeString()} · showing postings from the last day only
        </p>
      )}

      {error && (
        <p style={{ color: "var(--status-red)" }}>
          {error.includes("429")
            ? `LinkedIn's hourly rate limit hasn't reset yet (${error}).`
            : error.includes("502")
            ? `Couldn't fetch new matches (${error}). Check FIRECRAWL_API_KEY / LLM provider keys on gateway-service.`
            : `Couldn't reach gateway-service (${error}). Is it running at the configured API URL?`}
        </p>
      )}

      {!error && matches === null && <p>Loading matches…</p>}

      {!error && matches && matches.length === 0 && (
        <p>
          No {filter !== "all" ? filter : ""} matches yet. Click "Fetch more matches" to scrape
          postings from the last day, or run ingestion and matching cycles manually.
        </p>
      )}

      {matches && matches.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {matches.map((m) => (
            <MatchRow key={m.id} match={m} onSelect={setSelected} onStatusChange={handleStatusChange} />
          ))}
        </div>
      )}

      {selected && <DraftPanel match={selected} onClose={() => setSelected(null)} onGoToDrafts={onGoToDrafts} />}
    </div>
  );
}