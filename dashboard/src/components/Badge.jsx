import { StatusDot } from "./StatusDot";

export function Badge({ dotColor, children }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "var(--space-2)",
        padding: "3px var(--space-3)",
        borderRadius: "var(--radius-pill)",
        background: "var(--bg-recessed)",
        fontSize: 12,
        fontWeight: 500,
        color: "var(--text-secondary)",
        whiteSpace: "nowrap",
      }}
    >
      {dotColor && <StatusDot color={dotColor} size={6} />}
      {children}
    </span>
  );
}