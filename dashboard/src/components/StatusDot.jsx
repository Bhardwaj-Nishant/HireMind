const COLORS = {
  green: "var(--status-green)",
  orange: "var(--status-orange)",
  red: "var(--status-red)",
  blue: "var(--status-blue)",
  gray: "var(--status-gray)",
};

export function scoreColor(score) {
  if (score >= 70) return "green";
  if (score >= 40) return "orange";
  return "red";
}

export function StatusDot({ color = "gray", size = 8 }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: size,
        height: size,
        borderRadius: "50%",
        background: COLORS[color] || COLORS.gray,
        flexShrink: 0,
      }}
    />
  );
}