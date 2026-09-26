# dashboard

React + Vite frontend for HireMind. Talks only to `gateway-service`
(see VITE_API_URL) — no direct DB or LLM access from the browser.

Visual system follows the Vercel Geist design brief: achromatic base
(near-black/white/gray), a single blue accent, shadows used as borders,
status conveyed only via small colored dots (never colored backgrounds),
4px spacing scale. See `src/styles/tokens.css` for all design tokens.

Note: uses system font fallbacks for Geist Sans/Mono rather than the
actual Geist font files (not fetched here). Swap in the real Geist font
via `@font-face` in tokens.css if you want pixel-exact typography later.

## Structure
- `src/styles/tokens.css` — design tokens (colors, spacing, radius, shadows)
- `src/styles/global.css` — resets, base typography
- `src/api.js`            — fetch wrapper for gateway-service
- `src/components/`       — Header, MatchRow, DraftPanel, Badge, StatusDot
- `src/pages/`            — MatchesPage, InboxPage
- `src/App.jsx`           — tab switcher between the two pages

## Run
    cd dashboard
    npm install
    cp .env.example .env    # adjust VITE_API_URL if gateway-service runs elsewhere
    npm run dev

Then open http://localhost:5173 — make sure gateway-service is running
first (py run_gateway.py from the repo root) or the pages will show a
"couldn't reach gateway-service" message.

## Pages
- **Matches** — filterable list (pending/applied/dismissed), score dot,
  Applied/Dismiss actions, click a row to open the drafts panel
  (tailored resume / cover letter / recruiter email, with a Gmail-pushed
  indicator on the email tab).
- **Inbox** — important-email flags from Gmail classification, with a
  "mark reviewed" action.