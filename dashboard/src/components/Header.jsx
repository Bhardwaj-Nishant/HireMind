const TABS = [
  { key: "matches", label: "Matches" },
  { key: "drafts", label: "Drafts" },
  { key: "inbox", label: "Inbox" },
];

export function Header({ tab, onTabChange, theme, onToggleTheme }) {
  return (
    <header
      style={{
        height: "var(--header-height)",
        boxShadow: "var(--shadow-border)",
        background: "var(--bg-elevated)",
        position: "sticky",
        top: 0,
        zIndex: 10,
      }}
    >
      <div
        style={{
          maxWidth: "var(--page-width)",
          margin: "0 auto",
          height: "100%",
          padding: `0 var(--page-margin)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <h1 style={{ fontSize: 16, letterSpacing: "-0.32px" }}>HireMind</h1>
        <nav style={{ display: "flex", gap: "var(--space-8)" }}>
          {TABS.map((t) => (
            <button
              key={t.key}
              onClick={() => onTabChange(t.key)}
              style={{
                padding: "6px 2px",
                fontWeight: 500,
                color: tab === t.key ? "var(--text-primary)" : "var(--text-muted)",
                borderBottom: tab === t.key ? "2px solid var(--accent)" : "2px solid transparent",
                borderRadius: 0,
              }}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <button
          onClick={onToggleTheme}
          aria-label="Toggle dark mode"
          style={{
            width: 32,
            height: 32,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            boxShadow: "var(--shadow-border)",
            fontSize: 15,
          }}
        >
          {theme === "dark" ? "☀" : "☾"}
        </button>
      </div>
    </header>
  );
}