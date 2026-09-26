import { useEffect, useState } from "react";
import { Header } from "./components/Header";
import { MatchesPage } from "./pages/MatchesPage";
import { DraftsPage } from "./pages/DraftsPage";
import { InboxPage } from "./pages/InboxPage";

function getInitialTheme() {
  const stored = localStorage.getItem("hiremind-theme");
  if (stored === "dark" || stored === "light") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export default function App() {
  const [tab, setTab] = useState("matches");
  const [theme, setTheme] = useState(getInitialTheme);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("hiremind-theme", theme);
  }, [theme]);

  function toggleTheme() {
    setTheme((t) => (t === "dark" ? "light" : "dark"));
  }

  return (
    <div style={{ minHeight: "100%" }}>
      <Header tab={tab} onTabChange={setTab} theme={theme} onToggleTheme={toggleTheme} />
      {tab === "matches" && <MatchesPage onGoToDrafts={() => setTab("drafts")} />}
      {tab === "drafts" && <DraftsPage />}
      {tab === "inbox" && <InboxPage />}
    </div>
  );
}