import { Badge } from "./Badge";
import { StatusDot, scoreColor } from "./StatusDot";

const STATUS_COLOR = { pending: "blue", applied: "green", dismissed: "gray" };

export function MatchRow({ match, onSelect, onStatusChange }) {
  return (
    <div
      onClick={() => onSelect(match)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === "Enter" && onSelect(match)}
      style={{
        display: "flex",
        alignItems: "center",
        gap: "var(--space-4)",
        padding: "var(--space-4) var(--space-4)",
        borderRadius: "var(--radius-default)",
        cursor: "pointer",
        transition: "background 120ms var(--ease-swift)",
      }}
      onMouseEnter={(e) => (e.currentTarget.style.background = "var(--bg-hover)")}
      onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
    >
      <StatusDot color={scoreColor(match.score)} size={10} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>
          {match.job.title}
        </div>
        <div style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 2 }}>
          {match.job.company}
          {match.job.location ? ` · ${match.job.location}` : ""}
        </div>
      </div>

      <div className="mono" style={{ fontSize: 13, color: "var(--text-secondary)", width: 40, textAlign: "right" }}>
        {Math.round(match.score)}
      </div>

      <Badge dotColor={STATUS_COLOR[match.status]}>{match.status}</Badge>

      <a
        href={match.job.apply_url}
        target="_blank"
        rel="noreferrer"
        onClick={(e) => e.stopPropagation()}
        style={{ fontSize: 13, fontWeight: 500 }}
      >
        Open ↗
      </a>

      {match.status === "pending" && (
        <div style={{ display: "flex", gap: "var(--space-2)" }}>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onStatusChange(match.id, "applied");
            }}
            style={{ boxShadow: "var(--shadow-border)", padding: "4px 10px", fontWeight: 500 }}
          >
            Applied
          </button>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onStatusChange(match.id, "dismissed");
            }}
            style={{ boxShadow: "var(--shadow-border)", padding: "4px 10px" }}
          >
            Dismiss
          </button>
        </div>
      )}
    </div>
  );
}