const API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    throw new Error(`${options.method || "GET"} ${path} failed: ${res.status}`);
  }
  return res.json();
}

export const api = {
  getMatches: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/matches${qs ? `?${qs}` : ""}`);
  },
  updateMatch: (id, status) =>
    request(`/matches/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
  refreshMatches: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/matches/refresh${qs ? `?${qs}` : ""}`, { method: "POST" });
  },
  getDrafts: (matchId) => request(`/matches/${matchId}/drafts`),
  generateDrafts: (matchId, force = false) =>
    request(`/matches/${matchId}/generate`, { method: "POST", body: JSON.stringify({ force }) }),
  getAllDrafts: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/drafts${qs ? `?${qs}` : ""}`);
  },
  pushDraftToGmail: (draftId) => request(`/drafts/${draftId}/push-to-gmail`, { method: "POST" }),
  getInbox: (params = {}) => {
    const qs = new URLSearchParams(params).toString();
    return request(`/inbox${qs ? `?${qs}` : ""}`);
  },
  refreshInbox: () => request(`/inbox/refresh`, { method: "POST" }),
  updateInboxFlag: (id, reviewed) =>
    request(`/inbox/${id}`, { method: "PATCH", body: JSON.stringify({ reviewed }) }),
};