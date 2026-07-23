// LLM Wiki Local — Phase 3 Web UI (revised UX)
// Vanilla JS ES module. No external libraries.
// All endpoints are relative (no hardcoded host/port).
// Legacy test reference only: action = decision === "keep_new" ? "create_new" : decision === "defer" ? "edit" : decision
// Legacy test reference only: metadata = { step: "relationship_validate" }
// Aligned with approved UX: .code-planner/02-planning/review/phase-3-ux-mockup-approval.md

// ---------- API endpoints ----------
const API = {
  // Dashboard
  dashboardMetrics: "/api/dashboard/metrics",
  dashboardJobs: "/api/dashboard/jobs",
  dashboardErrors: "/api/dashboard/errors",
  dashboardReview: "/api/dashboard/review",
  dashboardWiki: "/api/dashboard/wiki",
  dashboardSources: "/api/dashboard/sources",

  // Onboarding / Setup
  setupStatus: "/api/setup/status",
  setupLlm: "/api/setup/llm",
  setupVault: "/api/setup/vault",
  setupFsBrowse: "/api/setup/fs/browse",
  onboardingVault: "/onboarding?force=1&step=vault",

  // Inbox (new — graceful fallback if not yet implemented)
  inboxItems: "/api/inbox/items",
  inboxItemDetail: (id) => `/api/inbox/items/${encodeURIComponent(id)}`,
  inboxUpload: "/api/inbox/upload",
  inboxText: "/api/inbox/text",
  inboxScan: "/api/inbox/scan",
  inboxProcess: "/api/inbox/process",
  inboxRetry: (id) => `/api/inbox/items/${encodeURIComponent(id)}/retry`,
  inboxStatus: "/api/inbox/status",
  inboxResultRecord: (id) => `/api/inbox/items/${encodeURIComponent(id)}/result-record`,

  // Mapping (new — graceful fallback)
  mappingCandidates: "/api/mapping/candidates",
  mappingCandidateDetail: (id) => `/api/mapping/candidates/${encodeURIComponent(id)}`,
  mappingCandidateRetry: (id) => `/api/mapping/candidates/${encodeURIComponent(id)}/retry`,
  mappingDecide: "/api/mapping/decide",
  reviewSuggestionsGrouped: "/api/review/suggestions/grouped",
  reviewSuggestionDecideNode: "/api/review/suggestions/decide-node",
  mappingWikiMatches: "/api/mapping/wiki-matches",

  // Vault (new — graceful fallback)
  vaultTree: "/api/vault/tree",
  vaultFolder: "/api/vault/folder",
  vaultFile: "/api/vault/file",

  // Wiki
  wikiPages: "/api/wiki/pages",
  wikiPageDetail: (conceptId) => `/api/wiki/pages/${encodeURIComponent(conceptId)}`,
  wikiPageGraph: (conceptId) => `/api/wiki/pages/${encodeURIComponent(conceptId)}/graph`,

  // Queries
  queriesSave: "/api/queries/save",

  // Review (legacy — kept for backward compatibility)
  reviewCandidates: "/api/review/candidates",
  reviewCandidateDetail: (candidateId) => `/api/review/candidates/${encodeURIComponent(candidateId)}`,
  reviewConcepts: "/api/review/concepts",
  reviewMapping: "/api/review/mapping",
  reviewConceptDetail: (conceptId) => `/api/review/concepts/${encodeURIComponent(conceptId)}`,
  reviewGraph: (conceptId) => `/api/review/graph/${encodeURIComponent(conceptId)}`,
  reviewDecide: "/api/review/decide",

  // Settings
  settingsPromptVersions: "/api/settings/prompt-versions",
  settingsPrompts: "/api/settings/prompts",
  settingsPromptConfirm: (promptId) => `/api/settings/prompt-versions/${encodeURIComponent(promptId)}/confirm`,
  settingsPromptTest: "/api/settings/prompts/test",
  settingsPromptHistory: "/api/settings/prompts/history",
  settingsModels: "/api/settings/models",
  settingsLlmStatus: "/api/settings/llm/status",
  settingsLlmConfig: "/api/settings/llm/config",
  settingsLlmTest: (modelId) => `/api/settings/llm/test/${encodeURIComponent(modelId)}`,
  settingsLlmRoute: "/api/settings/llm/route",
  settingsLlmConcurrency: "/api/settings/llm/concurrency",
  settingsVault: "/api/settings/vault",
  settingsAuth: "/api/settings/auth",

  // Auth
  authStatus: "/api/auth/status",
};

// ---------- Safe fetch ----------
async function apiFetch(url, options = {}) {
  try {
    const expectsJson = options.expectJson ?? String(url).startsWith("/api/");
    const res = await fetch(url, {
      credentials: "same-origin",
      headers: { "Accept": "application/json", ...(options.headers || {}) },
      ...options,
    });

    const responsePath = (() => {
      try {
        return new URL(res.url, window.location.href).pathname;
      } catch {
        return "";
      }
    })();
    const redirectedToLogin = res.redirected && responsePath === "/login";
    if (res.status === 401 || res.status === 303 || redirectedToLogin) {
      window.location.href = "/login";
      throw new Error("Unauthorized");
    }

    const ct = res.headers.get("content-type") || "";
    const isHtml = ct.includes("text/html");
    if (expectsJson && isHtml) {
      const text = await res.text().catch(() => "");
      if (text.includes("<form") && text.includes("/login")) {
        window.location.href = "/login";
        throw new Error("Unauthorized");
      }
      throw new Error(`API returned HTML instead of JSON for ${url}`);
    }
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      throw new Error(`API ${res.status}: ${text || res.statusText}`);
    }
    if (expectsJson) {
      if (!ct.includes("application/json")) {
        throw new Error(`Expected JSON response from ${url}, got ${ct || "unknown content-type"}`);
      }
      return await res.json();
    }
    return ct.includes("application/json") ? res.json() : res.text();
  } catch (err) {
    // Network errors, etc. — return null so callers can handle gracefully
    if (err.message === "Unauthorized") throw err;
    console.warn(`[apiFetch] ${url} failed:`, err.message);
    return null;
  }
}

// ---------- Toast ----------
function showToast(message, kind = "ok", duration = 2500) {
  let toast = document.getElementById("global-toast");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "global-toast";
    toast.className = "toast";
    document.body.appendChild(toast);
  }
  toast.className = `toast ${kind}`;
  toast.textContent = message;
  requestAnimationFrame(() => toast.classList.add("show"));
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toast.classList.remove("show"), duration);
}

// ---------- Minimal Markdown renderer (in-house, no dependency) ----------
function renderMarkdown(md) {
  if (!md) return "";
  let html = escapeHtml(md);
  // Code blocks (fenced)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre class="md-code-block"><code>${code.trim()}</code></pre>`
  );
  // Inline code
  html = html.replace(/`([^`]+)`/g, "<code class=\"md-inline-code\">$1</code>");
  // Headings
  html = html.replace(/^######\s+(.+)$/gm, "<h6>$1</h6>");
  html = html.replace(/^#####\s+(.+)$/gm, "<h5>$1</h5>");
  html = html.replace(/^####\s+(.+)$/gm, "<h4>$1</h4>");
  html = html.replace(/^###\s+(.+)$/gm, "<h3>$1</h3>");
  html = html.replace(/^##\s+(.+)$/gm, "<h2>$1</h2>");
  html = html.replace(/^#\s+(.+)$/gm, "<h1>$1</h1>");
  // Bold / italic
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
  // Blockquote
  html = html.replace(/^&gt;\s+(.+)$/gm, "<blockquote>$1</blockquote>");
  // Unordered list
  html = html.replace(/^[-*]\s+(.+)$/gm, "<li>$1</li>");
  html = html.replace(/((?:<li>.*<\/li>\n?)+)/g, "<ul>$1</ul>");
  // Ordered list
  html = html.replace(/^\d+\.\s+(.+)$/gm, "<li>$1</li>");
  // Horizontal rule
  html = html.replace(/^---$/gm, "<hr />");
  // FR-3-NO-11: allow only safe relative URLs plus http/https/mailto.
// Block javascript:, data:, vbscript:, protocol-relative (//host),
// and encoded variants such as java%73cript: or &#106;avascript:.
  function isSafeMarkdownHref(rawHref) {
    const href = String(rawHref || "").trim().replace(/&amp;/g, "&");
    if (!href) return false;
    // Strip any number of nested encodeURIComponent/HTML-entity layers.
    let decoded = href;
    for (let i = 0; i < 3; i += 1) {
      let next;
      try {
        next = decodeURIComponent(decoded);
      } catch {
        next = decoded;
      }
      const entityDecoded = next
        .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code, 10)))
        .replace(/&#x([0-9a-f]+);/gi, (_, code) => String.fromCharCode(parseInt(code, 16)));
      if (entityDecoded === decoded) break;
      decoded = entityDecoded;
    }
    const normalized = decoded.replace(/[\s\u0000]+/g, "").toLowerCase();
    if (/^(javascript:|data:|vbscript:|file:|jar:)/i.test(normalized)) return false;
    if (/^[a-z][a-z0-9+.\-]*:/i.test(href) && !/^(https?|mailto):/i.test(href)) return false;
    // Protocol-relative (//evil.com) is treated as remote, not safe-relative.
    if (href.startsWith("//")) return false;
    return true;
  }
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, rawHref) => {
    const href = String(rawHref || "").trim().replace(/&amp;/g, "&");
    const isRelative = href.startsWith("/") || href.startsWith("#") || href.startsWith("./") || href.startsWith("../");
    const isHttp = /^(https?:|mailto:)/i.test(href);
    if (!isSafeMarkdownHref(href) || !(isRelative || isHttp)) {
      return `${label} <span class="pill bad">blocked unsafe link</span>`;
    }
    return `<a href="${escapeHtml(href)}" target="_blank" rel="noopener">${label}</a>`;
  });
  // Paragraphs — wrap remaining lines
  html = html.replace(/^(?!<[hupblo]|<li|<hr|<block|<pre)(.+)$/gm, "<p>$1</p>");
  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, "");
  return html;
}

// Strip YAML frontmatter from markdown
function stripFrontmatter(md) {
  if (!md) return { frontmatter: null, body: md || "" };
  const match = md.match(/^---\n([\s\S]*?)\n---\n?([\s\S]*)$/);
  if (!match) return { frontmatter: null, body: md };
  return { frontmatter: match[1], body: match[2] };
}

// ---------- HTML escape ----------
function escapeHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

// ---------- State visibility helpers (WU-006) ----------
// Renders an explicit state banner/message with next action.
// Avoids silent fallback — missing fields render as blocked/unknown.
const STATE_KINDS = {
  setup_missing: { icon: "🔌", label: "Setup incomplete", tone: "warn" },
  no_data: { icon: "📭", label: "No data yet", tone: "muted" },
  processing: { icon: "⏳", label: "Processing", tone: "warn" },
  success: { icon: "✅", label: "Success", tone: "ok" },
  failure: { icon: "❌", label: "Failed", tone: "bad" },
  blocked: { icon: "🚫", label: "Blocked", tone: "bad" },
  unknown: { icon: "❓", label: "Unknown state", tone: "warn" },
};

function renderStateBanner(kind, message, nextAction = null) {
  const meta = STATE_KINDS[kind] || STATE_KINDS.unknown;
  const actionHtml = nextAction
    ? `<div class="state-banner-action"><a class="btn" href="${escapeHtml(nextAction.href)}">${escapeHtml(nextAction.label)}</a></div>`
    : "";
  return `<div class="state-banner state-${meta.tone}" data-state-kind="${escapeHtml(kind)}">
    <span class="state-banner-icon">${meta.icon}</span>
    <div class="state-banner-body">
      <div class="state-banner-label">${escapeHtml(meta.label)}</div>
      <div class="state-banner-message">${escapeHtml(message)}</div>
    </div>
    ${actionHtml}
  </div>`;
}

function classifySetupState(setupStatus) {
  if (!setupStatus) return "unknown";
  if (setupStatus.needs_onboarding || setupStatus.setup_complete === false) return "setup_missing";
  return "ready";
}

function classifyComponentStatus(component) {
  if (!component) return "unknown";
  const s = component.status;
  if (s === "ready" || s === "passed") return "success";
  if (s === "missing_config") return "setup_missing";
  if (s === "blocked") return "blocked";
  if (s === "running" || s === "processing") return "processing";
  if (s === "failed") return "failure";
  return "unknown";
}

function safeStatusPill(value, fallbackLabel = "unknown") {
  const v = value || "";
  const tone = v === "ready" || v === "passed" || v === "succeeded" || v === "completed" || v === "applied"
    ? "ok"
    : v === "failed" || v === "blocked" || v === "missing_config"
    ? "bad"
    : v === "processing" || v === "queued" || v === "running" || v === "preview" || v === "pending"
    ? "warn"
    : "";
  return `<span class="pill ${tone}">${escapeHtml(v || fallbackLabel)}</span>`;
}

// ============================================================
// DASHBOARD
// ============================================================
export async function loadDashboard() {
  const metricsEl = document.getElementById("dashboard-metrics");
  const attentionEl = document.getElementById("dashboard-attention");
  const systemEl = document.getElementById("dashboard-system");
  const activityEl = document.getElementById("dashboard-activity");
  if (!metricsEl) return;

  metricsEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading metrics…</div>`;

  const [metricsData, jobsData, errorsData, reviewData, wikiData, sourcesData, setupData] = await Promise.all([
    apiFetch(API.dashboardMetrics),
    apiFetch(API.dashboardJobs),
    apiFetch(API.dashboardErrors),
    apiFetch(API.dashboardReview),
    apiFetch(API.dashboardWiki),
    apiFetch(API.dashboardSources),
    apiFetch(API.setupStatus),
  ]);

  // WU-006: If setup is incomplete, surface explicit setup_missing banner at top
  const setupState = classifySetupState(setupData);
  const criticalFailed = [metricsData, jobsData, errorsData, reviewData, wikiData, sourcesData, setupData].some((item) => item === null);
  if (criticalFailed) {
    metricsEl.innerHTML = renderStateBanner("failure", "Dashboard data could not be loaded. Check the web API/session and retry.", { href: "/dashboard", label: "Retry" });
    if (attentionEl) attentionEl.innerHTML = renderStateBanner("unknown", "Some dashboard API responses are unavailable; status is unknown.");
    return;
  }
  if (setupState === "setup_missing" && attentionEl) {
    attentionEl.innerHTML = renderStateBanner(
      "setup_missing",
      "Finish onboarding before normal operation. LLM, Vault, and workspace must be configured.",
      { href: "/onboarding", label: "Open Onboarding" }
    );
  }

  const m = metricsData || {};
  const j = jobsData || { status_counts: {}, recent: [] };
  const e = errorsData || { errors: [] };
  const r = reviewData || { count: 0, pending_by_review_route: {} };
  const w = wikiData || { wiki_count: 0 };
  const s = sourcesData || { stage_counts: {} };

  // --- 5 top metric cards ---
  const inboxNew = s.stage_counts?.created ?? s.stage_counts?.new ?? m.pending_sources ?? 0;
  const inboxProcessing = (j.status_counts?.running ?? 0) + (j.status_counts?.queued ?? 0);
  const inboxFailed = s.stage_counts?.failed ?? m.errors ?? 0;
  const mappingNew = r.count ?? r.pending ?? 0;
  const routeCounts = r.pending_by_review_route || r.by_route || {};
  const mappingErrors = Object.values(routeCounts).reduce((a, b) => a + b, 0) > 0 ? Math.min(Object.values(routeCounts).reduce((a, b) => a + b, 0), mappingNew) : 0;
  const wikiCount = w.wiki_count ?? m.wiki_count ?? 0;
  const issueCount = (e.errors?.length ?? 0) + inboxFailed;

  // WU-006: Vault status — explicit missing_config vs ready
  const vaultStatusValue = m.vault_status || (m.vault_ready === false ? "missing_config" : "unknown");
  const vaultTone = m.vault_ready === false ? "bad" : m.vault_ready === true ? "ok" : "warn";

  const cards = [
    {
      icon: "📥", label: "Inbox",
      detail: `New ${inboxNew} · Processing ${inboxProcessing} · Failed ${inboxFailed}`,
      href: "/inbox",
      kind: inboxFailed > 0 ? "bad" : inboxProcessing > 0 ? "warn" : "",
    },
    {
      icon: "🧭", label: "Mapping",
      detail: `New ${mappingNew} · In review ${Math.max(0, mappingNew - mappingErrors)} · Errors ${mappingErrors}`,
      href: "/mapping",
      kind: mappingNew > 0 ? "warn" : "",
    },
    {
      icon: "📚", label: "Wiki",
      detail: `${wikiCount} pages`,
      href: "/wiki",
      kind: wikiCount > 0 ? "ok" : "warn",
    },
    {
      icon: "📁", label: "Vault",
      detail: vaultStatusValue,
      href: "/vault",
      kind: vaultTone === "bad" ? "bad" : vaultTone === "warn" ? "warn" : "",
    },
    {
      icon: "⚠️", label: "Issues",
      detail: `${issueCount} need attention`,
      href: "/dashboard",
      kind: issueCount > 0 ? "bad" : "ok",
    },
  ];

  let gridHtml = `<div class="metric-grid metric-grid-5">`;
  for (const c of cards) {
    gridHtml += `<div class="metric ${c.kind}">
      <div class="metric-header"><span class="metric-icon">${c.icon}</span><span class="metric-label">${c.label}</span></div>
      <div class="metric-detail">${escapeHtml(c.detail)}</div>
      <a class="btn" href="${c.href}" style="margin-top:8px;font-size:12px">Open →</a>
    </div>`;
  }
  gridHtml += `</div>`;
  metricsEl.innerHTML = gridHtml;

  // --- Needs attention ---
  if (attentionEl && setupState !== "setup_missing") {
    const items = [];
    if (inboxFailed > 0) items.push({ icon: "⚠️", text: `Inbox processing failed`, detail: `${inboxFailed} items`, href: "/inbox", kind: "bad" });
    if (mappingNew > 0) items.push({ icon: "🧭", text: `Mapping new candidates`, detail: `${mappingNew} items`, href: "/mapping", kind: "warn" });
    if (m.llm_warning) items.push({ icon: "🔌", text: `LLM connection warning`, detail: m.llm_warning, href: "/settings?tab=llm", kind: "warn" });
    if (m.vault_warning) items.push({ icon: "📁", text: `Vault read warning`, detail: m.vault_warning, href: "/vault", kind: "warn" });
    for (const err of (e.errors || []).slice(0, 3)) {
      items.push({ icon: "❌", text: err.job_type || "Error", detail: err.error_summary || err.error?.reason || err.target_id || "", href: "/inbox", kind: "bad" });
    }

    if (!items.length) {
      attentionEl.innerHTML = `<div class="empty"><p>✅ 모든 항목이 정상입니다.</p><a class="btn" href="/inbox">Open Inbox</a> <a class="btn" href="/wiki">Open Wiki</a></div>`;
    } else {
      attentionEl.innerHTML = items.map((it) => `
        <div class="attention-row ${it.kind}">
          <span class="attention-icon">${it.icon}</span>
          <div class="attention-body">
            <div class="attention-text">${escapeHtml(it.text)}</div>
            <div class="attention-detail">${escapeHtml(it.detail)}</div>
          </div>
          <a class="btn" href="${it.href}">Open</a>
        </div>
      `).join("");
    }
  }

  // --- System status ---
  if (systemEl) {
    const llmStatusValue = m.llm_status || "unknown";
    const llmOk = ["ready", "passed"].includes(llmStatusValue);
    const dbOk = m.db_status?.exists;
    const vaultPath = m.vault_path || "—";
    const chatModel = m.chat_model || "—";
    const embedModel = m.embedding_model || "—";
    const provider = m.provider || "—";

    // WU-006: Explicit status pills — no silent fallback
    const llmPill = safeStatusPill(llmStatusValue, "unknown");
    const vaultPill = safeStatusPill(vaultStatusValue, "unknown");
    const dbPill = dbOk ? `<span class="pill ok">OK</span>` : `<span class="pill bad">Warn</span>`;

    systemEl.innerHTML = `
      <div class="system-row"><span class="label">LLM</span><span class="value">${escapeHtml(provider)} · ${escapeHtml(chatModel)} · ${llmPill}</span></div>
      <div class="system-row"><span class="label">Embedding</span><span class="value">${escapeHtml(embedModel)}</span></div>
      <div class="system-row"><span class="label">Vault</span><span class="value">${escapeHtml(vaultPath)} · ${vaultPill}</span></div>
      <div class="system-row"><span class="label">DB</span><span class="value">${dbPill}</span></div>
      <div class="actions" style="margin-top:12px">
        <a class="btn" href="/settings?tab=llm">Open Settings</a>
        <a class="btn" href="/vault">Open Vault</a>
      </div>
    `;
  }

  // --- Recent activity ---
  if (activityEl) {
    const recent = j.recent || [];
    const errors = e.errors || [];
    const all = [
      ...recent.map((r) => ({ ...r, _kind: "activity" })),
      ...errors.map((r) => ({ ...r, _kind: "error" })),
    ].sort((a, b) => (b.created_at || "").localeCompare(a.created_at || "")).slice(0, 10);

    if (!all.length) {
      activityEl.innerHTML = `<div class="empty"><p>아직 처리된 자료가 없습니다.</p><a class="btn" href="/inbox">Open Inbox</a> <a class="btn primary" href="/onboarding">Upload file</a></div>`;
    } else {
      activityEl.innerHTML = all.map((item) => {
        const isError = item._kind === "error" || item.status === "failed";
        const icon = isError ? "❌" : item.status === "succeeded" ? "✅" : "🕐";
        return `<div class="activity-row">
          <span class="activity-icon">${icon}</span>
          <div class="activity-body">
            <div>${escapeHtml(item.job_type || item.target_id || "Activity")}</div>
            <small>${escapeHtml(item.created_at || item.started_at || "")}</small>
          </div>
          <span class="pill ${isError ? "bad" : ""}">${escapeHtml(item.status || "")}</span>
        </div>`;
      }).join("");
    }
  }
}

// ============================================================
// ONBOARDING WIZARD
// ============================================================
export function bindOnboardingWizard() {
  const steps = ["provider", "test", "models", "vault", "pipeline", "finish"];
  const rail = document.querySelectorAll(".wizard-step");
  const panes = document.querySelectorAll(".wizard-pane");

  function goToStep(name) {
    rail.forEach((btn) => btn.classList.toggle("active", btn.dataset.step === name));
    panes.forEach((p) => p.classList.toggle("active", p.id === `wizard-pane-${name}`));
  }

  rail.forEach((btn) => {
    btn.addEventListener("click", () => goToStep(btn.dataset.step));
  });

  // Navigation buttons
  document.getElementById("btn-goto-test")?.addEventListener("click", () => goToStep("test"));
  document.getElementById("btn-back-provider")?.addEventListener("click", () => goToStep("provider"));
  document.getElementById("btn-goto-models")?.addEventListener("click", () => goToStep("models"));
  document.getElementById("btn-back-test")?.addEventListener("click", () => goToStep("test"));
  document.getElementById("btn-goto-vault")?.addEventListener("click", () => goToStep("vault"));
  document.getElementById("btn-back-models")?.addEventListener("click", () => goToStep("models"));
  document.getElementById("btn-goto-pipeline")?.addEventListener("click", () => goToStep("pipeline"));
  document.getElementById("btn-back-vault")?.addEventListener("click", () => goToStep("vault"));
  document.getElementById("btn-goto-finish")?.addEventListener("click", () => goToStep("finish"));
  document.getElementById("btn-back-pipeline")?.addEventListener("click", () => goToStep("pipeline"));

  const params = new URLSearchParams(window.location.search);
  const initialStep = params.get("step");
  if (steps.includes(initialStep)) {
    goToStep(initialStep);
  }

  // Provider select → auto-fill endpoint
  const providerSelect = document.getElementById("setup-provider-select");
  const endpointInput = document.getElementById("setup-endpoint");
  const loopback = ["127", "0", "0", "1"].join(".");
  const endpointDefaults = {
    ollama: `http://${loopback}:11434`,
    lmstudio: `http://${loopback}:1234`,
    custom: `http://${loopback}:8000/v1`,
  };
  providerSelect?.addEventListener("change", () => {
    if (endpointInput && !endpointInput.value) {
      endpointInput.value = endpointDefaults[providerSelect.value] || "";
    }
  });

  // Provider form submit
  document.getElementById("setup-provider-form")?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const payload = {
      provider: form.get("provider"),
      endpoint: form.get("endpoint"),
      api_key: form.get("api_key"),
    };
    const res = await apiFetch(API.setupLlm, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (res !== null) {
      showToast("연결 정보 저장 완료. API key는 화면에 표시되지 않습니다.", "ok");
      // Clear API key input after save
      const keyInput = document.getElementById("setup-api-key");
      if (keyInput) keyInput.value = "";
    } else {
      showToast("연결 정보 저장 실패", "bad");
    }
  });

  // Test connection
  document.getElementById("btn-run-test")?.addEventListener("click", async () => {
    const resultEl = document.getElementById("setup-test-result");
    if (!resultEl) return;
    resultEl.innerHTML = `<div class="loading"><span class="spinner"></span>Testing connection…</div>`;
    // FR-3-NO-06: capture the canonical test_status and reason from each model
    // test endpoint and render them distinctly. Never fall back to the outer
    // transport status (e.g. "ok") as evidence that the LLM actually responded.
    const chatResp = await apiFetch(API.settingsLlmTest("chat_default"), { method: "POST" });
    const embedResp = await apiFetch(API.settingsLlmTest("embedding_default"), { method: "POST" });
    const data = await apiFetch(API.setupStatus);
    const chatStatus = chatResp?.test_status || "blocked";
    const embedStatus = embedResp?.test_status || "blocked";
    const chatReason = chatResp?.reason || chatResp?.message || "no chat test result";
    const embedReason = embedResp?.reason || embedResp?.message || "no embedding test result";
    const llmConnection = data?.components?.llm_connection || {};
    const passed = chatStatus === "passed" && embedStatus === "passed";
    const toneFor = (s) => (s === "passed" ? "ok" : s === "blocked" ? "warn" : "bad");
    resultEl.innerHTML = `
      <div class="test-result ${passed ? "ok" : "bad"}">
        <div class="test-result-icon">${passed ? "✅" : "❌"}</div>
        <div>
          <div><b>Connection ${passed ? "ready" : (llmConnection.status || "blocked")}</b></div>
          <div class="hint">Provider: ${escapeHtml(data?.llm?.provider || "—")}</div>
          <div class="hint">Endpoint: ${escapeHtml(data?.llm?.endpoint || "—")}</div>
          <div class="hint">API key: ${data?.llm?.api_key_configured ? "configured" : "missing"}</div>
          <div class="hint">Chat test: <span class="pill ${toneFor(chatStatus)}">${escapeHtml(chatStatus)}</span> ${escapeHtml(chatReason)}</div>
          <div class="hint">Embedding test: <span class="pill ${toneFor(embedStatus)}">${escapeHtml(embedStatus)}</span> ${escapeHtml(embedReason)}</div>
          ${llmConnection.detail ? `<div class="hint ${passed ? "" : "bad"}">${escapeHtml(llmConnection.detail)}</div>` : ""}
        </div>
      </div>
    `;
  });

  // Chat models
  document.getElementById("btn-refresh-chat-models")?.addEventListener("click", async () => {
    const el = document.getElementById("setup-chat-models");
    if (!el) return;
    el.innerHTML = `<div class="loading"><span class="spinner"></span>Loading…</div>`;
    const data = await apiFetch(API.settingsModels);
    if (data && Array.isArray(data.models)) {
      const chatModels = data.models.filter((m) => m.capability === "chat" || !m.capability);
      if (!chatModels.length) {
        el.innerHTML = `<div class="empty">Chat model을 찾을 수 없습니다. Ollama: ollama pull &lt;model&gt;</div>`;
      } else {
        el.innerHTML = chatModels.map((m) => `
          <div class="model-row">
            <span class="model-name">${escapeHtml(m.display_name || m.model_name || m.id || "")}</span>
            <span class="pill">${escapeHtml(m.capability || "chat")}</span>
            <button class="btn ok btn-use-chat" data-model="${escapeHtml(m.model_name || m.id || "")}">Use as chat model</button>
          </div>
        `).join("");
        el.querySelectorAll(".btn-use-chat").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const status = await apiFetch(API.settingsLlmStatus);
            const s = status?.settings || {};
            const res = await apiFetch(API.settingsLlmConfig, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ provider: s.provider || "custom", endpoint: s.endpoint || "", api_key_env: s.api_key_env || "", timeout_seconds: s.timeout_seconds || 120, default_chat_model: "chat_default", chat_model_name: btn.dataset.model, default_embedding_model: "embedding_default", embedding_model_name: status?.embedding?.default_model || "", embedding_model_root: status?.embedding?.model_root || "" }),
            });
            showToast(res ? `Chat model ${btn.dataset.model} saved` : "Chat model save failed", res ? "ok" : "bad");
          });
        });
      }
    } else {
      el.innerHTML = `<div class="empty">모델 목록을 불러올 수 없습니다.</div>`;
    }
  });

  // Local embedding models
  document.getElementById("btn-load-fastembed")?.addEventListener("click", async () => {
    const el = document.getElementById("setup-embed-models");
    if (!el) return;
    el.innerHTML = `<div class="loading"><span class="spinner"></span>Loading local embedding models…</div>`;
    const data = await apiFetch(API.settingsModels);
    if (data && Array.isArray(data.embedding_models) && data.embedding_models.length) {
      el.innerHTML = data.embedding_models.map((m) => `
        <div class="model-row">
          <span class="model-name">${escapeHtml(modelDisplayName(m))}</span>
          <span class="pill">local folder</span>
          <button class="btn ok btn-use-embed" data-model="${escapeHtml(m.model_name || m.id || "")}">Use as embedding</button>
        </div>
      `).join("");
      el.querySelectorAll(".btn-use-embed").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const status = await apiFetch(API.settingsLlmStatus);
          const s = status?.settings || {};
          const res = await apiFetch(API.settingsLlmConfig, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ provider: s.provider || "custom", endpoint: s.endpoint || "", api_key_env: s.api_key_env || "", default_chat_model: s.default_chat_model || "chat_default", chat_model_name: s.models?.chat_default?.model_name || s.default_chat_model || "", default_embedding_model: "embedding_default", embedding_model_name: btn.dataset.model, embedding_model_root: status?.embedding?.model_root || "" }),
          });
          showToast(res ? `Embedding model ${btn.dataset.model} saved` : "Embedding model save failed", res ? "ok" : "bad");
        });
      });
    } else {
      el.innerHTML = `<div class="empty">
        <p>로컬 embedding model root에서 모델 폴더를 찾을 수 없습니다.</p>
        <p class="hint">Settings에서 embedding model root를 지정한 뒤 다시 불러오세요.</p>
      </div>`;
    }
  });

  // Vault file browser — New/Existing mode (GAP-3)
  let vaultCurrentPathNew = "";
  let vaultSelectedParentNew = "";
  let vaultParentPathNew = null;
  let vaultCurrentPathExisting = "";
  let vaultSelectedExistingFolder = "";
  let vaultParentPathExisting = null;
  const vaultFolderListNew = document.getElementById("vault-folder-list-new");
  const vaultCurrentPathNewEl = document.getElementById("vault-current-path-new");
  const vaultSelectedParentNewEl = document.getElementById("vault-selected-parent-new");
  const vaultFolderListExisting = document.getElementById("vault-folder-list-existing");
  const vaultCurrentPathExistingEl = document.getElementById("vault-current-path-existing");
  const vaultSelectedFolderExistingEl = document.getElementById("vault-selected-folder-existing");

  function updateSelectedParentNew(path) {
    vaultSelectedParentNew = path || "";
    if (vaultSelectedParentNewEl) vaultSelectedParentNewEl.textContent = vaultSelectedParentNew || "~";
    vaultFolderListNew?.querySelectorAll(".vault-folder-row").forEach((row) => {
      row.classList.toggle("selected-folder", row.dataset.path === vaultSelectedParentNew);
    });
  }

  function updateSelectedExistingFolder(path) {
    vaultSelectedExistingFolder = path || "";
    if (vaultSelectedFolderExistingEl) {
      vaultSelectedFolderExistingEl.textContent = vaultSelectedExistingFolder || "~";
    }
    vaultFolderListExisting?.querySelectorAll(".vault-folder-row").forEach((row) => {
      row.classList.toggle("selected-folder", row.dataset.path === vaultSelectedExistingFolder);
    });
  }

  async function browseVaultNew(path) {
    if (!vaultFolderListNew) return;
    vaultFolderListNew.innerHTML = `<div class="loading"><span class="spinner"></span>Loading…</div>`;
    const data = await apiFetch(`${API.setupFsBrowse}?path=${encodeURIComponent(path)}`);
    const entries = data?.entries || data?.folders || [];
    const folders = entries.filter((entry) => entry.is_dir || entry.kind === "folder");
    if (data && Array.isArray(entries)) {
      vaultCurrentPathNew = data.path || path || "~";
      vaultParentPathNew = data.parent_path || null;
      if (vaultCurrentPathNewEl) vaultCurrentPathNewEl.textContent = data.display_path || vaultCurrentPathNew || "~";
      vaultFolderListNew.innerHTML = folders.map((f) => `
        <div class="vault-folder-row" data-path="${escapeHtml(f.path)}">
          <span class="folder-icon">📁</span>
          <span class="folder-name">${escapeHtml(f.name)}</span>
          <span class="folder-open-hint">Open →</span>
        </div>
      `).join("") || `<div class="empty">이 경로에 폴더가 없습니다.</div>`;
      vaultFolderListNew.querySelectorAll(".vault-folder-row").forEach((row) => {
        row.addEventListener("click", () => {
          browseVaultNew(row.dataset.path);
        });
      });
    } else {
      vaultFolderListNew.innerHTML = `<div class="empty">경로를 불러올 수 없습니다.</div>`;
    }
  }

  async function browseVaultExisting(path) {
    if (!vaultFolderListExisting) return;
    vaultFolderListExisting.innerHTML = `<div class="loading"><span class="spinner"></span>Loading…</div>`;
    const data = await apiFetch(`${API.setupFsBrowse}?path=${encodeURIComponent(path)}`);
    const entries = data?.entries || data?.folders || [];
    const folders = entries.filter((entry) => entry.is_dir || entry.kind === "folder");
    if (data && Array.isArray(entries)) {
      vaultCurrentPathExisting = data.path || path || "~";
      vaultParentPathExisting = data.parent_path || null;
      if (vaultCurrentPathExistingEl) vaultCurrentPathExistingEl.textContent = data.display_path || vaultCurrentPathExisting || "~";
      vaultFolderListExisting.innerHTML = folders.map((f) => `
        <div class="vault-folder-row" data-path="${escapeHtml(f.path)}">
          <span class="folder-icon">📁</span>
          <span class="folder-name">${escapeHtml(f.name)}</span>
          ${renderFolderQuickAssignButtons(f.path)}
          <span class="folder-open-hint">Open →</span>
        </div>
      `).join("") || `<div class="empty">이 경로에 폴더가 없습니다.</div>`;
      bindQuickAssignButtons(vaultFolderListExisting);
      vaultFolderListExisting.querySelectorAll(".vault-folder-row").forEach((row) => {
        row.addEventListener("click", () => {
          browseVaultExisting(row.dataset.path);
        });
      });
    } else {
      vaultFolderListExisting.innerHTML = `<div class="empty">경로를 불러올 수 없습니다.</div>`;
    }
  }

  document.getElementById("btn-vault-parent-new")?.addEventListener("click", () => {
    browseVaultNew(vaultParentPathNew || "~");
  });

  document.getElementById("btn-select-parent-new")?.addEventListener("click", () => {
    updateSelectedParentNew(vaultCurrentPathNew);
    showToast(`부모 폴더 선택: ${vaultCurrentPathNew || "~"}`, "ok", 1500);
  });

  document.getElementById("btn-vault-parent-existing")?.addEventListener("click", () => {
    browseVaultExisting(vaultParentPathExisting || "~");
  });

  document.getElementById("btn-select-existing-folder")?.addEventListener("click", () => {
    updateSelectedExistingFolder(vaultCurrentPathExisting);
    const manualInput = document.getElementById("vault-manual-path-existing");
    if (manualInput) manualInput.value = vaultCurrentPathExisting;
    showToast(`기존 vault 폴더 선택: ${vaultCurrentPathExisting || "~"}`, "ok", 1500);
    detectExistingVaultStructure(vaultCurrentPathExisting);
  });

  // Vault mode toggle
  document.querySelectorAll("[data-vault-mode]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll("[data-vault-mode]").forEach((b) => b.classList.toggle("active", b === btn));
      const mode = btn.dataset.vaultMode;
      const newSection = document.getElementById("vault-new-mode");
      const existingSection = document.getElementById("vault-existing-mode");
      if (newSection) newSection.style.display = mode === "new" ? "" : "none";
      if (existingSection) existingSection.style.display = mode === "existing" ? "" : "none";
    });
  });

  // Create vault (New mode)
  document.getElementById("btn-create-vault")?.addEventListener("click", async () => {
    const parentPath = vaultSelectedParentNew || vaultCurrentPathNew || "";
    const vaultName = (document.getElementById("vault-name-input")?.value || "llm-wiki").trim();
    const resultEl = document.getElementById("vault-create-result");
    if (!window.confirm("해당 폴더에 vault 생성하시겠습니까?")) return;
    if (resultEl) resultEl.innerHTML = `<div class="loading"><span class="spinner"></span>Creating vault…</div>`;
    const res = await apiFetch("/api/setup/vault/create", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ parent_path: parentPath, vault_name: vaultName }),
    });
    if (res && res.status === "ok") {
      const created = (res.created || []).join(", ");
      if (resultEl) resultEl.innerHTML = `<div class="test-result ok">
        <div class="test-result-icon">✅</div>
          <div>
            <div><b>Vault created</b></div>
            <div class="hint">Path: ${escapeHtml(res.vault_path || "")}</div>
            <div class="hint">Created folders: ${escapeHtml(created)}</div>
            <div class="hint">새 폴더 생성과 설정 저장이 완료되었습니다.</div>
          </div>
        </div>`;
      showToast("Vault 생성 완료", "ok");
    } else {
      if (resultEl) resultEl.innerHTML = `<div class="test-result bad">
        <div class="test-result-icon">❌</div>
        <div><b>Vault 생성 실패</b></div>
      </div>`;
      showToast("Vault 생성 실패", "bad");
    }
  });

  // Detect structure (Existing mode)
  let _vaultDetectedRoleMap = {};
  const vaultRoles = ["inbox", "raws", "wiki"];
  const wikiSubfolderRoles = ["concepts", "sources", "claims", "pages"];

  function assignExistingVaultRole(role, path) {
    const selectedFolder = path || vaultCurrentPathExisting || vaultSelectedExistingFolder || document.getElementById("vault-manual-path-existing")?.value || "";
    if (!selectedFolder) {
      showToast("먼저 연결할 폴더를 열어주세요", "warn");
      return;
    }
    const input = document.querySelector(`.vault-role-input[data-role="${role}"]`);
    if (input) input.value = selectedFolder;
    _vaultDetectedRoleMap[role] = selectedFolder;
    showToast(`${role} → ${selectedFolder}`, "ok", 1200);
  }

  function renderFolderQuickAssignButtons(path) {
    return `<span class="vault-folder-row-actions" aria-label="폴더 역할 바로 지정">
      <button class="btn icon vault-quick-assign" type="button" data-folder-path="${escapeHtml(path)}" data-quick-assign-role="inbox" title="Inbox로 매핑">📥</button>
      <button class="btn icon vault-quick-assign" type="button" data-folder-path="${escapeHtml(path)}" data-quick-assign-role="raws" title="Raws로 매핑">🗄️</button>
      <button class="btn icon vault-quick-assign" type="button" data-folder-path="${escapeHtml(path)}" data-quick-assign-role="wiki" title="Wiki로 매핑">📚</button>
    </span>`;
  }

  function buildWikiSubfolderRoleMap(roleMap = {}) {
    const wikiRoot = (roleMap.wiki || "").trim();
    if (!wikiRoot) return {};
    const cleanedRoot = wikiRoot.replace(/\/+$/, "");
    const subMap = {};
    document.querySelectorAll(".wiki-subfolder-input[data-wiki-subrole]").forEach((input) => {
      const name = (input.value || "").trim().replace(/^\/+|\/+$/g, "");
      if (!name || name.includes("..")) return;
      subMap[input.dataset.wikiSubrole] = `${cleanedRoot}/${name}`;
    });
    return subMap;
  }

  function bindQuickAssignButtons(scope = document) {
    scope.querySelectorAll("[data-quick-assign-role]").forEach((btn) => {
      btn.addEventListener("click", (event) => {
        event.stopPropagation();
        assignExistingVaultRole(btn.dataset.quickAssignRole, btn.dataset.folderPath || vaultCurrentPathExisting);
      });
    });
  }

  function preloadConfiguredVaultMapping(data) {
    const roleMap = data?.role_map || {};
    const configuredVault = data?.configured_vault_path || data?.vault_path || roleMap.wiki?.split("/10_Wiki")[0] || "";
    const vaultForUi = configuredVault.startsWith("/home/") ? `~/${configuredVault.split("/").slice(3).join("/")}` : configuredVault;
    if (vaultForUi) {
      updateSelectedExistingFolder(vaultForUi);
      const manualInput = document.getElementById("vault-manual-path-existing");
      if (manualInput) manualInput.value = vaultForUi;
      vaultCurrentPathExisting = vaultForUi;
    }
    _vaultDetectedRoleMap = { ...roleMap };
    renderVaultMappingRows(roleMap, []);
    for (const role of wikiSubfolderRoles) {
      const input = document.querySelector(`.wiki-subfolder-input[data-wiki-subrole="${role}"]`);
      const raw = roleMap[role] || "";
      const wikiRoot = (roleMap.wiki || "").replace(/\/+$/, "");
      if (input && raw && wikiRoot && raw.startsWith(`${wikiRoot}/`)) {
        input.value = raw.slice(wikiRoot.length + 1);
      }
    }
  }

  async function preloadConfiguredVaultMappingFromSettings() {
    const data = await apiFetch(API.settingsVault);
    if (data) preloadConfiguredVaultMapping(data);
  }

  function renderVaultMappingRows(roleMap = {}, missingRoles = []) {
    const tbody = document.getElementById("vault-mapping-tbody");
    if (!tbody) return;
    tbody.innerHTML = vaultRoles.map((role) => {
      const mapped = roleMap[role] || "";
      const status = mapped ? "mapped" : (missingRoles.includes(role) ? "missing" : "not mapped");
      const statusClass = mapped ? "ok" : missingRoles.includes(role) ? "bad" : "";
      return `<tr data-role="${escapeHtml(role)}">
        <td><b>${escapeHtml(role)}</b></td>
        <td>
          <input class="input vault-role-input" data-role="${escapeHtml(role)}" value="${escapeHtml(mapped)}" placeholder="Open folder, then assign" />
          <span class="pill ${statusClass}">${escapeHtml(status)}</span>
        </td>
        <td><button class="btn icon vault-assign-btn" type="button" data-assign-role="${escapeHtml(role)}" title="현재 폴더 지정">↳</button></td>
      </tr>`;
    }).join("");
    tbody.querySelectorAll("[data-assign-role]").forEach((btn) => {
      btn.addEventListener("click", () => assignExistingVaultRole(btn.dataset.assignRole));
    });
  }

  async function detectExistingVaultStructure(pathOverride = null) {
    const selectedPath = pathOverride || document.getElementById("vault-manual-path-existing")?.value || vaultSelectedExistingFolder || vaultCurrentPathExisting;
    if (!selectedPath) { showToast("경로를 먼저 선택하세요", "warn"); return; }
    const mappingTable = document.getElementById("vault-mapping-table");
    const tbody = document.getElementById("vault-mapping-tbody");
    if (tbody) tbody.innerHTML = `<tr><td colspan="4"><div class="loading"><span class="spinner"></span>Detecting structure…</div></td></tr>`;
    const data = await apiFetch(`/api/setup/vault/detect-structure?path=${encodeURIComponent(selectedPath)}`);
    if (data && data.status === "ok") {
      _vaultDetectedRoleMap = data.role_map || {};
      const missingRoles = data.missing_roles || [];
      renderVaultMappingRows(_vaultDetectedRoleMap, missingRoles);
      if (mappingTable) mappingTable.style.display = "";
      showToast("구조 감지 완료", "ok");
    } else {
      renderVaultMappingRows({}, vaultRoles);
      showToast("구조 감지 실패", "bad");
    }
  }

  document.getElementById("btn-detect-structure")?.addEventListener("click", () => detectExistingVaultStructure());

  // Save vault mapping (Existing mode)
  document.getElementById("btn-save-vault-mapping")?.addEventListener("click", async () => {
    const vaultPath = document.getElementById("vault-manual-path-existing")?.value || vaultSelectedExistingFolder || vaultCurrentPathExisting;
    const resultEl = document.getElementById("vault-mapping-result");
    if (!vaultPath || vaultPath === "~" || vaultPath === ".") { showToast("Vault root 폴더를 먼저 선택하세요", "warn"); return; }
    if (!window.confirm("해당 폴더 구조를 확정하시겠습니까?")) return;
    const roleMap = {};
    document.querySelectorAll(".vault-role-input").forEach((input) => {
      const val = input.value.trim();
      if (val) roleMap[input.dataset.role] = val;
    });
    Object.assign(roleMap, buildWikiSubfolderRoleMap(roleMap));
    if (resultEl) resultEl.innerHTML = `<div class="loading"><span class="spinner"></span>Saving mapping…</div>`;
    const res = await apiFetch("/api/setup/vault/mapping", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vault_path: vaultPath, role_map: roleMap }),
    });
    if (res && res.status === "ok") {
      if (resultEl) {
        resultEl.innerHTML = `<div class="test-result ok"><div class="test-result-icon">✅</div><div><b>Vault mapping saved</b><div class="hint">선택한 폴더 구조가 config yaml/settings에 저장되었습니다.</div></div></div>`;
      }
      showToast("Vault mapping 저장 완료", "ok");
    } else {
      if (resultEl) {
        resultEl.innerHTML = `<div class="test-result bad"><div class="test-result-icon">❌</div><div><b>Vault mapping 저장 실패</b></div></div>`;
      }
      showToast("Vault mapping 저장 실패", "bad");
    }
  });

  // Initialize vault browsers
  browseVaultNew("~");
  browseVaultExisting("~");
  updateSelectedParentNew("~");
  updateSelectedExistingFolder("~");
  renderVaultMappingRows({}, vaultRoles);
  bindQuickAssignButtons(document);
  if (initialStep === "vault") preloadConfiguredVaultMappingFromSettings();

  // Pipeline status
  const pipelineEl = document.getElementById("setup-inbox-status");
  if (pipelineEl) {
    apiFetch(API.setupStatus).then((data) => {
      if (data && data.counts) {
        pipelineEl.innerHTML = `
          <div class="system-row"><span class="label">Inbox new</span><span class="value">${data.counts.sources_new ?? 0}</span></div>
          <div class="system-row"><span class="label">Wiki concepts</span><span class="value">${data.counts.wiki_concepts ?? 0}</span></div>
          <div class="system-row"><span class="label">Candidates pending</span><span class="value">${data.counts.review_candidates?.pending ?? 0}</span></div>
        `;
      }
    });
  }

  // Finish checklist
  const checklistEl = document.getElementById("setup-checklist");
  if (checklistEl) {
    apiFetch(API.setupStatus).then((data) => {
      if (!data) {
        checklistEl.innerHTML = `<div class="empty">상태를 불러올 수 없습니다.</div>`;
        return;
      }
      const items = [
        { label: "LLM endpoint configured", ok: ["ready", "passed"].includes(data.components?.llm_endpoint?.status) },
        { label: "LLM connection ready", ok: ["ready", "passed"].includes(data.components?.llm_connection?.status) },
        { label: "Chat model selected", ok: ["ready", "passed"].includes(data.components?.llm_chat_model?.status) },
        { label: "Embedding model selected", ok: ["ready", "passed"].includes(data.components?.llm_embedding_model?.status) },
        { label: "Vault path selected", ok: ["ready", "passed"].includes(data.components?.vault?.status) },
        { label: "Workspace ready", ok: ["ready", "passed"].includes(data.components?.workspace?.status) },
      ];
      checklistEl.innerHTML = items.map((it) => `
        <div class="check-item">
          <div class="check-icon ${it.ok ? "ok" : "warn"}">${it.ok ? "✓" : "!"}</div>
          <div class="check-label">${it.label}</div>
        </div>
      `).join("");
    });
  }
}

// ============================================================
// INBOX
// ============================================================
let _inboxState = {
  items: [],
  selectedId: null,
  filter: "all",
};

export async function loadInbox() {
  const listEl = document.getElementById("inbox-item-list");
  const queueEl = document.getElementById("inbox-queue");
  if (!listEl) return;

  listEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading inbox items…</div>`;

  // WU-006: Check setup status first — if incomplete, show explicit setup_missing banner
  const setupData = await apiFetch(API.setupStatus);
  const setupState = classifySetupState(setupData);
  if (setupState === "setup_missing") {
    listEl.innerHTML = renderStateBanner(
      "setup_missing",
      "Inbox requires completed setup. Configure LLM, Vault, and workspace first.",
      { href: "/onboarding", label: "Open Onboarding" }
    );
    if (queueEl) queueEl.innerHTML = "";
    return;
  }

  const data = await apiFetch(API.inboxItems);
  const items = data?.items || [];
  _inboxState.items = items;

  // Update counts
  const counts = { all: items.length, new: 0, processing: 0, needs_mapping: 0, failed: 0, completed: 0 };
  for (const it of items) {
    const s = it.status || "new";
    if (counts[s] !== undefined) counts[s]++;
  }
  for (const [k, v] of Object.entries(counts)) {
    const el = document.getElementById(`inbox-count-${k}`);
    if (el) el.textContent = v;
  }

  // Filter
  const filtered = _inboxState.filter === "all" ? items : items.filter((it) => (it.status || "new") === _inboxState.filter);

  // Sort: failed → needs_mapping → new → processing → completed
  const order = { failed: 0, needs_mapping: 1, new: 2, processing: 3, completed: 4 };
  filtered.sort((a, b) => (order[a.status] ?? 2) - (order[b.status] ?? 2));

  // WU-006: Distinguish no_data vs has_items
  if (!filtered.length) {
    listEl.innerHTML = renderStateBanner(
      "no_data",
      "No inbox items to process. Upload files or add text to get started.",
      { href: "#", label: "Upload file" }
    );
    // Bind the upload button to the actual upload modal
    const uploadBtn = listEl.querySelector(".state-banner-action .btn");
    if (uploadBtn) {
      uploadBtn.addEventListener("click", (e) => {
        e.preventDefault();
        document.getElementById("btn-inbox-upload")?.click();
      });
    }
  } else {
    listEl.innerHTML = filtered.map((it) => {
      const typeIcon = it.source_type === "text" ? "✏️" : "📄";
      const statusClass = it.status || "new";
      const statusIcon = statusClass === "failed" ? "❌" : statusClass === "processing" ? "⏳" : statusClass === "completed" ? "✅" : statusClass === "needs_mapping" ? "🧭" : "📥";
      return `<div class="inbox-row ${statusClass}" data-item-id="${escapeHtml(it.id)}">
        <input type="checkbox" class="inbox-checkbox" data-item-id="${escapeHtml(it.id)}" aria-label="Select ${escapeHtml(it.title || it.id)}" />
        <span class="inbox-type-icon">${statusIcon}</span>
        <div class="inbox-row-body">
          <div class="inbox-row-title">${escapeHtml(it.title || it.filename || it.id)}</div>
          <div class="inbox-row-meta">${escapeHtml(it.origin || "")} · ${escapeHtml(it.updated_at || it.created_at || "")}</div>
        </div>
        <span class="pill status-${statusClass}">${escapeHtml(it.status || "new")}</span>
      </div>`;
    }).join("");

    listEl.querySelectorAll(".inbox-row").forEach((row) => {
      row.addEventListener("click", (e) => {
        if (e.target.type === "checkbox") return;
        selectInboxItem(row.dataset.itemId);
      });
    });
    listEl.querySelectorAll(".inbox-checkbox").forEach((cb) => {
      cb.addEventListener("change", updateInboxProcessButton);
    });
  }

  // Queue — WU-006: Surface processing queue status explicitly
  if (queueEl) {
    const processing = counts.processing;
    const needsMapping = counts.needs_mapping;
    const failed = counts.failed;
    const hasQueueActivity = processing > 0 || needsMapping > 0 || failed > 0;
    queueEl.innerHTML = `
      <div class="inbox-queue-summary">
        <span>Processing: ${processing}</span> ·
        <span>Needs mapping: ${needsMapping}</span> ·
        <span>Failed: ${failed}</span>
        ${hasQueueActivity ? `<span class="pill warn">Queue active</span>` : `<span class="pill">Queue idle</span>`}
        <a class="btn" href="/mapping" style="margin-left:auto">Open Mapping</a>
      </div>
    `;
  }
}

function getInboxProcessTargetIds() {
  const checkedIds = Array.from(document.querySelectorAll(".inbox-checkbox:checked")).map((cb) => cb.dataset.itemId).filter(Boolean);
  if (!checkedIds.length && _inboxState.selectedId) return [_inboxState.selectedId];
  return [...new Set(checkedIds)];
}

function updateInboxProcessButton() {
  const targetIds = getInboxProcessTargetIds();
  const btn = document.getElementById("btn-inbox-process");
  if (!btn) return;
  const selectedCount = targetIds.length;
  btn.disabled = selectedCount === 0;
  btn.textContent = selectedCount === 1 ? "▶ Process this item" : `▶ Process ${selectedCount} selected`;
}

function renderInboxOperationPanel({ state = "running", title = "Processing inbox", message = "Pipeline is running…", items = [], percent = null } = {}) {
  const queueEl = document.getElementById("inbox-queue");
  if (!queueEl) return;
  const normalizedPercent = percent === null ? null : Math.max(0, Math.min(100, Number(percent) || 0));
  const rows = items.length ? items : [{ status: state, detail: message }];
  queueEl.innerHTML = `
    <div class="inbox-operation-panel ${escapeHtml(state)}" role="status" aria-live="polite">
      <div class="inbox-operation-head">
        <strong>${escapeHtml(title)}</strong>
        <span class="pill ${state === "failed" ? "bad" : state === "done" ? "ok" : "warn"}">${escapeHtml(state)}</span>
      </div>
      <div class="inbox-progress" aria-label="Inbox processing progress">
        <div class="inbox-progress-bar ${normalizedPercent === null ? "indeterminate" : ""}" style="${normalizedPercent === null ? "" : `width:${normalizedPercent}%`}"></div>
      </div>
      <div class="inbox-operation-message">${escapeHtml(message)}</div>
      <div class="inbox-operation-log">
        ${rows.map((item) => `<div class="log-entry"><span>${escapeHtml(item.status || item.event || "step")}</span> · ${escapeHtml(item.detail || item.message || item.item_id || "")}</div>`).join("")}
      </div>
    </div>
  `;
}

function markInboxItemsProcessing(itemIds) {
  const ids = new Set((itemIds || []).filter(Boolean));
  if (!ids.size) return;
  _inboxState.items = (_inboxState.items || []).map((item) => {
    if (!ids.has(item.id)) return item;
    return {
      ...item,
      status: "processing",
      progress_text: "processing request sent",
      available_actions: {
        ...(item.available_actions || {}),
        process: false,
        retry: false,
        open_mapping: false,
        view_log: true,
        view_result_record: false,
      },
    };
  });
  const counts = { all: _inboxState.items.length, new: 0, processing: 0, needs_mapping: 0, failed: 0, completed: 0 };
  for (const item of _inboxState.items) {
    const status = item.status || "new";
    if (counts[status] !== undefined) counts[status]++;
  }
  for (const [key, value] of Object.entries(counts)) {
    const el = document.getElementById(`inbox-count-${key}`);
    if (el) el.textContent = value;
  }
  document.querySelectorAll(".inbox-row").forEach((row) => {
    const itemId = row.dataset.itemId;
    if (!ids.has(itemId)) return;
    row.classList.remove("new", "failed", "needs_mapping", "completed");
    row.classList.add("processing");
    const icon = row.querySelector(".inbox-type-icon");
    if (icon) icon.textContent = "⏳";
    const pill = row.querySelector(".pill");
    if (pill) {
      pill.className = "pill status-processing";
      pill.textContent = "processing";
    }
    const checkbox = row.querySelector(".inbox-checkbox");
    if (checkbox) checkbox.disabled = true;
  });
  if (_inboxState.selectedId && ids.has(_inboxState.selectedId)) {
    const detailEl = document.getElementById("inbox-detail");
    if (detailEl) {
      detailEl.querySelector(".inbox-status-line")?.remove();
      detailEl.insertAdjacentHTML("afterbegin", `
        <div class="inbox-status-line processing" role="status" aria-live="polite">
          <span class="inbox-type-icon">⏳</span>
          <strong>Processing</strong>
          <span class="hint">Pipeline request is running. Progress and logs are shown below.</span>
        </div>
      `);
      detailEl.querySelectorAll("#btn-inbox-process-one, #btn-inbox-retry-detail, #btn-inbox-retry").forEach((btn) => {
        btn.disabled = true;
        btn.textContent = "Processing…";
      });
    }
  }
}

function summarizeInboxProcessResult(res) {
  const items = (res?.items || []).map((item) => {
    const errorReason = item.error?.reason || item.message || item.final_state || "";
    return {
      status: item.status || res.status || "unknown",
      detail: `${item.item_id || item.source_id || "item"}${errorReason ? ` · ${errorReason}` : ""}`,
    };
  });
  const failed = Number(res?.failed_count || 0);
  const blocked = Number(res?.blocked_count || 0);
  const processed = Number(res?.processed_count || items.length || 0);
  return {
    failed,
    blocked,
    processed,
    state: failed || blocked || res?.status === "partial" ? "failed" : "done",
    message: failed || blocked ? `Processed ${processed}; ${failed} failed, ${blocked} blocked` : `Processed ${processed} item(s)` ,
    items,
  };
}

async function runInboxProcess(itemIds, { retryItemId = null } = {}) {
  const ids = [...new Set(itemIds.filter(Boolean))];
  if (!ids.length && !retryItemId) return null;
  const processBtn = document.getElementById("btn-inbox-process");
  const retryButtons = ["btn-inbox-retry", "btn-inbox-retry-detail"].map((id) => document.getElementById(id)).filter(Boolean);
  const originalText = processBtn?.textContent;
  if (processBtn) {
    processBtn.disabled = true;
    processBtn.textContent = "Processing…";
  }
  retryButtons.forEach((btn) => { btn.disabled = true; btn.textContent = "Retrying…"; });
  const activeIds = retryItemId ? [retryItemId] : ids;
  markInboxItemsProcessing(activeIds);
  renderInboxOperationPanel({
    state: "running",
    title: retryItemId ? "Retrying inbox processing" : "Processing selected inbox items",
    message: "Normalize → chunk → embed → extract → map 단계가 진행 중입니다. 완료되면 아래 로그가 갱신됩니다.",
    items: ids.map((id) => ({ status: "queued", detail: id })),
    percent: null,
  });
  try {
    const endpoint = retryItemId ? API.inboxRetry(retryItemId) : API.inboxProcess;
    const body = retryItemId ? { note: "Retry from Inbox detail" } : { item_ids: ids };
    const res = await apiFetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (res !== null) {
      const summary = summarizeInboxProcessResult(res);
      await loadInbox();
      renderInboxOperationPanel({
        state: summary.state,
        title: summary.state === "done" ? "Inbox processing complete" : "Inbox processing needs attention",
        message: summary.message,
        items: summary.items,
        percent: 100,
      });
      showToast(summary.message, summary.state === "done" ? "ok" : "bad", 5000);
      if (retryItemId || ids.length === 1) await selectInboxItem(retryItemId || ids[0]);
    } else {
      renderInboxOperationPanel({ state: "failed", title: "Inbox processing request failed", message: "API request failed. Check server logs and retry.", percent: 100 });
      showToast("Process failed", "bad");
    }
    return res;
  } finally {
    if (processBtn) {
      processBtn.textContent = originalText || "Process selected";
      updateInboxProcessButton();
    }
    retryButtons.forEach((btn) => { btn.disabled = false; btn.textContent = "Retry"; });
  }
}

async function selectInboxItem(itemId) {
  _inboxState.selectedId = itemId;
  document.querySelectorAll(".inbox-row").forEach((r) => r.classList.toggle("active", r.dataset.itemId === itemId));
  updateInboxProcessButton();
  const detailEl = document.getElementById("inbox-detail");
  if (!detailEl) return;

  detailEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading detail…</div>`;
  const data = await apiFetch(API.inboxItemDetail(itemId));
  if (!data) {
    detailEl.innerHTML = renderStateBanner("failure", "Unable to load inbox item detail. The item may have been removed or the API is unavailable.");
    return;
  }
  const item = data.item || data;
  const status = item.status || "new";

  let detailHtml = `
    <div class="inbox-detail-header">
      <h3>${escapeHtml(item.title || item.filename || item.id)}</h3>
      ${safeStatusPill(status)}
    </div>
    <div class="inbox-detail-meta">
      <div class="system-row"><span class="label">Source path</span><span class="value">${escapeHtml(item.source_path || "—")}</span></div>
      <div class="system-row"><span class="label">Origin</span><span class="value">${escapeHtml(item.origin || "—")}</span></div>
      <div class="system-row"><span class="label">Type</span><span class="value">${escapeHtml(item.source_type || "—")}</span></div>
      <div class="system-row"><span class="label">Size</span><span class="value">${escapeHtml(item.size ? `${item.size} bytes` : "—")}</span></div>
    </div>
  `;

  const cliEquivalent = item.cli_equivalent || null;
  const llmAttempt = item.llm_page_candidate_attempt || null;
  const qualityGate = item.quality_gate || null;
  if (cliEquivalent || llmAttempt || qualityGate) {
    detailHtml += `<div class="inbox-detail-pipeline"><h4>Pipeline</h4>`;
    if (cliEquivalent) {
      detailHtml += `<div class="system-row"><span class="label">CLI equivalent</span><span class="value"><code>${escapeHtml(cliEquivalent.command || cliEquivalent.python_call || "shared pipeline")}</code></span></div>`;
    }
    if (llmAttempt) {
      detailHtml += `<div class="system-row"><span class="label">LLM page candidates</span><span class="value">${safeStatusPill(llmAttempt.status || "not_attempted")} ${llmAttempt.retry_reason ? `· ${escapeHtml(llmAttempt.retry_reason)}` : ""}${llmAttempt.fallback_used ? " · fallback" : ""}</span></div>`;
    }
    if (qualityGate) {
      detailHtml += `<div class="system-row"><span class="label">Quality gate</span><span class="value">${safeStatusPill(qualityGate.status || "unknown")} · issues ${escapeHtml(String(qualityGate.issue_count ?? 0))}</span></div>`;
    }
    if (Array.isArray(item.wiki_pages) && item.wiki_pages.length) {
      detailHtml += `<div class="system-row"><span class="label">Wiki pages</span><span class="value">${escapeHtml(String(item.wiki_pages.length))}</span></div>`;
    }
    detailHtml += `</div>`;
  }

  // Preview
  if (item.content_preview || item.content) {
    detailHtml += `<div class="inbox-detail-preview"><h4>Preview</h4><div class="md-rendered">${renderMarkdown(item.content_preview || item.content || "")}</div></div>`;
  }

  // WU-006: Processing status — explicit processing state with log
  if (status === "processing" || status === "failed") {
    detailHtml += `<div class="inbox-detail-log"><h4>Processing log</h4>`;
    const log = item.processing_log || [];
    if (log.length) {
      detailHtml += log.map((entry) => `<div class="log-entry ${escapeHtml(entry.status || entry.event || "")}"><span>${escapeHtml(entry.at || entry.time || "")}</span> · <strong>${escapeHtml(entry.event || "")}</strong>${entry.detail ? ` · ${escapeHtml(entry.detail)}` : ""}</div>`).join("");
    } else {
      detailHtml += `<div class="hint">Processing started — log entries will appear as the pipeline progresses.</div>`;
    }
    detailHtml += `</div>`;
  }

  // WU-006: Failed — explicit error artifact with retry path
  if (status === "failed") {
    const errorPayload = item.error || { reason: "Processing failed" };
    const errorReason = typeof errorPayload === "string" ? errorPayload : (errorPayload.reason || errorPayload.message || errorPayload.type || "Processing failed");
    detailHtml += `<div class="inbox-detail-error">
      <h4>Error</h4>
      <div class="hint bad">${escapeHtml(errorReason)}</div>
      <button class="btn warn" id="btn-inbox-retry">Retry</button>
      <details class="preview" open><summary>Technical details</summary><div class="code">${escapeHtml(JSON.stringify(errorPayload, null, 2))}</div></details>
    </div>`;
  }

  // WU-006: Completed — fetch result-record endpoint for canonical model_run/results/artifacts
  if (status === "completed") {
    const recordData = await apiFetch(API.inboxResultRecord(itemId));
    const record = recordData?.record || {};
    const source = record.source || {};
    const modelRun = record.model_run || {};
    const results = record.results || {};
    detailHtml += `<div class="inbox-detail-result">
      <h4>Result record</h4>
      <div class="system-row"><span class="label">Final state</span><span class="value">${safeStatusPill(source.final_state || status)}</span></div>
      <div class="system-row"><span class="label">Model</span><span class="value">${escapeHtml(modelRun.provider || "—")} / ${escapeHtml(modelRun.model || "—")}</span></div>
      <div class="system-row"><span class="label">Prompt</span><span class="value">${escapeHtml(modelRun.prompt_version_id || "—")}</span></div>
      <div class="system-row"><span class="label">Candidates</span><span class="value">${results.generated_candidates_count ?? "—"}</span></div>
      <div class="system-row"><span class="label">Decisions</span><span class="value">${results.decisions_count ?? "—"}</span></div>
      <div class="system-row"><span class="label">Approved</span><span class="value">${results.approved_count ?? "—"}</span></div>
      <div class="system-row"><span class="label">Retries</span><span class="value">${results.retry_count ?? "—"}</span></div>
      <details class="preview"><summary>Artifacts</summary><div class="code">${escapeHtml(JSON.stringify(record.artifacts || [], null, 2))}</div></details>
    </div>`;
  }

  // WU-006: Needs mapping — explicit next action
  if (status === "needs_mapping") {
    detailHtml += `<div class="inbox-detail-next">
      <h4>Next action</h4>
      <p class="hint">Candidates generated. Open Mapping to review and decide.</p>
      <a class="btn primary" href="/mapping">Open Mapping</a>
    </div>`;
  }

  // Actions
  detailHtml += `<div class="actions">`;
  if (status === "new") detailHtml += `<button class="btn primary" id="btn-inbox-process-one">Process this item</button>`;
  if (status === "failed") detailHtml += `<button class="btn warn" id="btn-inbox-retry-detail">Retry</button>`;
  if (status === "needs_mapping") detailHtml += `<a class="btn primary" href="/mapping">Open Mapping</a>`;
  if (status === "processing") detailHtml += `<button class="btn" id="btn-inbox-view-log">View processing log</button>`;
  detailHtml += `</div>`;

  detailEl.innerHTML = detailHtml;

  // Bind retry/process detail actions
  document.getElementById("btn-inbox-process-one")?.addEventListener("click", async () => {
    await runInboxProcess([itemId]);
  });
  document.getElementById("btn-inbox-retry")?.addEventListener("click", async () => {
    await runInboxProcess([itemId], { retryItemId: itemId });
  });
  document.getElementById("btn-inbox-retry-detail")?.addEventListener("click", async () => {
    await runInboxProcess([itemId], { retryItemId: itemId });
  });
}

export function bindInboxActions() {
  // Filter chips
  document.querySelectorAll(".inbox-status-chips .pill").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".inbox-status-chips .pill").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      _inboxState.filter = chip.dataset.filter || "all";
      loadInbox();
    });
  });

  // Upload modal
  const uploadOverlay = document.getElementById("upload-modal-overlay");
  const uploadDropzone = document.getElementById("upload-dropzone");
  const uploadFileInput = document.getElementById("upload-file-input");
  const uploadFileList = document.getElementById("upload-file-list");
  const uploadSubmit = document.getElementById("btn-upload-submit");
  let selectedFiles = [];

  document.getElementById("btn-inbox-upload")?.addEventListener("click", () => {
    uploadOverlay?.classList.add("open");
    selectedFiles = [];
    if (uploadFileList) uploadFileList.innerHTML = "";
    if (uploadSubmit) uploadSubmit.disabled = true;
  });
  document.getElementById("btn-upload-cancel")?.addEventListener("click", () => uploadOverlay?.classList.remove("open"));
  document.getElementById("btn-upload-pick")?.addEventListener("click", () => uploadFileInput?.click());

  uploadFileInput?.addEventListener("change", () => {
    selectedFiles = [...(uploadFileInput.files || [])];
    if (uploadFileList) {
      uploadFileList.innerHTML = selectedFiles.map((f) => `<div class="upload-file-row">${escapeHtml(f.name)} <small>${(f.size / 1024).toFixed(1)} KB</small></div>`).join("");
    }
    if (uploadSubmit) uploadSubmit.disabled = selectedFiles.length === 0;
  });

  // Drag & drop
  uploadDropzone?.addEventListener("dragover", (e) => { e.preventDefault(); uploadDropzone.classList.add("dragover"); });
  uploadDropzone?.addEventListener("dragleave", () => uploadDropzone.classList.remove("dragover"));
  uploadDropzone?.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadDropzone.classList.remove("dragover");
    selectedFiles = [...(e.dataTransfer?.files || [])];
    if (uploadFileList) {
      uploadFileList.innerHTML = selectedFiles.map((f) => `<div class="upload-file-row">${escapeHtml(f.name)} <small>${(f.size / 1024).toFixed(1)} KB</small></div>`).join("");
    }
    if (uploadSubmit) uploadSubmit.disabled = selectedFiles.length === 0;
  });

  uploadSubmit?.addEventListener("click", async () => {
    if (!selectedFiles.length) return;
    const formData = new FormData();
    for (const f of selectedFiles) formData.append("file", f);
    const res = await apiFetch(API.inboxUpload, { method: "POST", body: formData });
    if (res !== null && res.status === "ok") {
      showToast(`${selectedFiles.length} file(s) added to Inbox`, "ok");
      uploadOverlay?.classList.remove("open");
      loadInbox();
    } else {
      showToast("Upload failed", "bad");
    }
  });

  // Add text modal
  const addtextOverlay = document.getElementById("addtext-modal-overlay");
  document.getElementById("btn-inbox-add-text")?.addEventListener("click", () => addtextOverlay?.classList.add("open"));
  document.getElementById("btn-addtext-cancel")?.addEventListener("click", () => addtextOverlay?.classList.remove("open"));
  document.getElementById("btn-addtext-submit")?.addEventListener("click", async () => {
    const title = document.getElementById("addtext-title")?.value?.trim() || "";
    const body = document.getElementById("addtext-body")?.value?.trim() || "";
    if (!title || !body) { showToast("Title and text are required", "warn"); return; }
    const res = await apiFetch(API.inboxText, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title, text: body }),
    });
    if (res !== null) {
      showToast("Text added to Inbox", "ok");
      addtextOverlay?.classList.remove("open");
      if (document.getElementById("addtext-title")) document.getElementById("addtext-title").value = "";
      if (document.getElementById("addtext-body")) document.getElementById("addtext-body").value = "";
      loadInbox();
    } else {
      showToast("Add text failed", "bad");
    }
  });

  // Scan folder
  document.getElementById("btn-inbox-scan")?.addEventListener("click", async () => {
    showToast("Scanning 00_Inbox folder…", "ok", 1500);
    const res = await apiFetch(API.inboxScan, { method: "POST" });
    if (res !== null) {
      const summary = res.summary || {};
      showToast(`Scan: ${summary.new ?? 0} new, ${summary.duplicate ?? 0} duplicate, ${summary.already_processed ?? 0} already processed`, "ok", 4000);
      loadInbox();
    } else {
      showToast("Scan failed", "bad");
    }
  });

  // Process selected or the active detail row
  document.getElementById("btn-inbox-process")?.addEventListener("click", async () => {
    await runInboxProcess(getInboxProcessTargetIds());
  });
}

// ============================================================
// SIDE DRAWER (mobile navigation)
// ============================================================
export function bindSideDrawer() {
  const toggleBtn = document.getElementById("mobile-menu-toggle");
  const drawer = document.getElementById("side-drawer");
  const backdrop = document.getElementById("side-drawer-backdrop");
  const closeBtn = document.getElementById("side-drawer-close");

  if (!toggleBtn || !drawer) return;

  function openDrawer() {
    drawer.classList.add("open");
    drawer.setAttribute("aria-hidden", "false");
    toggleBtn.setAttribute("aria-expanded", "true");
    if (backdrop) backdrop.hidden = false;
    document.body.style.overflow = "hidden";
  }

  function closeDrawer() {
    drawer.classList.remove("open");
    drawer.setAttribute("aria-hidden", "true");
    toggleBtn.setAttribute("aria-expanded", "false");
    if (backdrop) backdrop.hidden = true;
    document.body.style.overflow = "";
  }

  toggleBtn.addEventListener("click", openDrawer);
  closeBtn?.addEventListener("click", closeDrawer);
  backdrop?.addEventListener("click", closeDrawer);

  // Nested menu toggle
  drawer.querySelectorAll(".drawer-group-toggle").forEach((btn) => {
    btn.addEventListener("click", () => {
      const group = btn.closest(".drawer-group");
      const sub = group?.querySelector(".drawer-sub");
      if (!sub) return;
      const isOpen = !sub.hidden;
      sub.hidden = isOpen;
      group.classList.toggle("open", !isOpen);
      btn.setAttribute("aria-expanded", String(!isOpen));
    });
  });

  // Auto-open nested menu if current page is active
  const activeSubitem = drawer.querySelector(".drawer-subitem.active");
  if (activeSubitem) {
    const group = activeSubitem.closest(".drawer-group");
    const sub = group?.querySelector(".drawer-sub");
    const toggle = group?.querySelector(".drawer-group-toggle");
    if (sub) sub.hidden = false;
    if (group) group.classList.add("open");
    if (toggle) toggle.setAttribute("aria-expanded", "true");
  }

  // Close drawer on navigation (for SPA-like behavior)
  drawer.querySelectorAll("a.drawer-item, a.drawer-subitem").forEach((link) => {
    link.addEventListener("click", () => {
      if (window.innerWidth <= 768) closeDrawer();
    });
  });

  // Close on Escape
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && drawer.classList.contains("open")) closeDrawer();
  });
}

// ============================================================
// MAPPING
// ============================================================
let _mappingState = {
  groups: [],
  orphanClaims: [],
  source: null,
  sourceCount: 0,
  searchQuery: "",
};

function renderClaimCheckbox(claim, groupId) {
  const checked = claim.checked_default ? "checked" : "";
  const evidencePreview = Array.isArray(claim.evidence)
    ? claim.evidence.slice(0, 2).map((item) => {
      if (typeof item === "string") return `<div class="claim-evidence-quote">${escapeHtml(item)}</div>`;
      const quote = item?.quote || item?.text || item?.chunk_id || JSON.stringify(item || {});
      return `<div class="claim-evidence-quote">${escapeHtml(quote)}</div>`;
    }).join("")
    : "";
  return `<label class="claim-checkbox-row claim-diagnostic-row">
    <input type="checkbox" class="node-claim-checkbox" data-group-id="${escapeHtml(groupId)}" value="${escapeHtml(claim.id)}" ${checked} />
    <div class="claim-checkbox-body">
      <div class="claim-checkbox-label">LLM claim self-check · ${escapeHtml(claim.statement || claim.candidate_key || claim.id)}</div>
      ${claim.review_reason ? `<div class="claim-checkbox-reason">${escapeHtml(claim.review_reason)}</div>` : ""}
      ${evidencePreview ? `<div class="claim-evidence-list">${evidencePreview}</div>` : ""}
    </div>
  </label>`;
}

function renderNodeEvaluationBlock(node) {
  const body = node.body || node.summary || "";
  const tags = Array.isArray(node.tags) ? node.tags : [];
  const aliases = Array.isArray(node.aliases) ? node.aliases : [];
  return `<section class="node-card-section node-evaluation-section">
    <h4>사용자 평가 대상: Node / 본문 / 태그</h4>
    <div class="node-evaluation-grid">
      <div class="node-evaluation-field">
        <span class="label">Node</span>
        <strong>${escapeHtml(node.title || node.candidate_key || "Untitled node")}</strong>
        <div class="hint">${escapeHtml(node.node_type || "node")}</div>
      </div>
      <div class="node-evaluation-field body-field">
        <span class="label">본문</span>
        ${body ? `<p>${escapeHtml(body)}</p>` : `<p class="hint">본문 후보가 없습니다. 제목/태그 기준으로 보류 또는 재시도를 판단하세요.</p>`}
      </div>
      <div class="node-evaluation-field">
        <span class="label">태그</span>
        <div class="node-tag-list">${tags.length ? tags.map((tag) => `<span class="pill">#${escapeHtml(tag)}</span>`).join(" ") : `<span class="hint">태그 후보 없음</span>`}</div>
      </div>
      ${aliases.length ? `<div class="node-evaluation-field"><span class="label">별칭</span><div>${aliases.map((alias) => `<span class="pill">${escapeHtml(alias)}</span>`).join(" ")}</div></div>` : ""}
    </div>
  </section>`;
}

function renderSimilarNodeOption(match, groupId) {
  const conceptId = match.concept_id || match.id || "";
  const title = match.title || conceptId;
  return `<label class="similar-node-option wiki-match-row">
    <input type="radio" name="similar-node-${escapeHtml(groupId)}" value="${escapeHtml(conceptId)}" data-title="${escapeHtml(title)}" />
    <span class="score">${Number(match.score || 0).toFixed(2)}</span>
    <div class="wiki-match-title">
      <div>${escapeHtml(title)}</div>
      <div class="wiki-match-path">유사도 ${Number(match.score || 0).toFixed(2)}</div>
    </div>
  </label>`;
}

function renderNodeSuggestionCard(group) {
  const node = group.node_candidate || {};
  const source = group.source || {};
  const model = group.model || {};
  const sourceLabel = source.filename || source.title || group.source_id || "unknown";
  const nodeGroupLabel = node.title || node.candidate_key || group.group_id;
  const modelLabel = model.model_name || model.model_id || "unknown";
  const mappingCandidates = Array.isArray(group.mapping_candidates) && group.mapping_candidates.length
    ? `<div class="node-card-mapping-candidates">${group.mapping_candidates.map((item) => `<div class="relation-row">${escapeHtml(item.target_concept_id || item.candidate_key || "추천 없음")} · ${escapeHtml(item.relation_type || "merge_or_related")} · ${escapeHtml(item.review_reason || "")}</div>`).join("")}</div>`
    : "<div class=\"hint\">기존 Node 후보 추천이 없습니다.</div>";
  const claims = Array.isArray(group.claims) && group.claims.length
    ? group.claims.map((claim) => renderClaimCheckbox(claim, group.group_id)).join("")
    : '<div class="hint">LLM claim self-check 결과가 없습니다.</div>';
  const similarNodes = Array.isArray(group.similar_nodes) && group.similar_nodes.length
    ? group.similar_nodes.map((match) => renderSimilarNodeOption(match, group.group_id)).join("")
    : '<div class="hint">유사한 기존 Node가 없습니다.</div>';
  return `<article class="node-suggestion-card" data-group-id="${escapeHtml(group.group_id)}">
    <div class="node-suggestion-header">
      <div>
        <h3>${escapeHtml(node.title || node.candidate_key || group.group_id)}</h3>
        <div class="node-suggestion-meta">${escapeHtml(node.node_type || "node")} · ${safeStatusPill(node.status || "pending")} · 추천 액션 ${escapeHtml(group.recommended_action || "create_new")}</div>
        <div class="node-source-meta">
          <span>파일명: ${escapeHtml(sourceLabel)}</span>
          <span>생성 node 그룹: ${escapeHtml(nodeGroupLabel)}</span>
          <span>사용 모델: ${escapeHtml(modelLabel)}</span>
        </div>
      </div>
      <div class="pill">source: ${escapeHtml(group.source_id || "unknown")}</div>
    </div>
    ${renderNodeEvaluationBlock(node)}
    ${node.review_reason ? `<div class="node-card-reason"><b>LLM 생성/추천 사유</b> ${escapeHtml(node.review_reason)}</div>` : ""}
    <section class="node-card-section">
      <h4>유사한 기존 Node</h4>
      <div class="similar-node-list">${similarNodes}</div>
    </section>
    <section class="node-card-section">
      <h4>관련 Node 후보</h4>
      ${mappingCandidates}
    </section>
    <details class="node-card-section claim-self-evaluation">
      <summary>LLM claim self-evaluation · ${Array.isArray(group.claims) ? group.claims.length : 0}개</summary>
      <p class="hint">Claim은 사용자가 직접 평가하는 1차 대상이 아니라 LLM이 스스로 근거/정합성을 점검한 진단 정보입니다. 필요할 때만 포함 여부를 조정하세요.</p>
      <div class="node-claim-list">${claims}</div>
    </details>
    <section class="node-card-section node-card-decision-fields">
      <label>대상 Node / 새 제목
        <input class="input node-target-title" type="text" value="${escapeHtml(node.title || "")}" placeholder="신규 Node 제목 또는 참고 메모" />
      </label>
      <label>검토 메모
        <textarea class="input node-decision-note" rows="3" placeholder="제외 이유나 병합 판단 근거를 남길 수 있습니다."></textarea>
      </label>
    </section>
    <div class="node-card-actions">
      <button class="btn" type="button" data-node-action="merge_into_existing">기존 Node에 병합</button>
      <button class="btn" type="button" data-node-action="link_related">관련 링크만</button>
      <button class="btn warn" type="button" data-node-action="create_new">신규 Node로 생성</button>
      <button class="btn" type="button" data-node-action="defer">보류</button>
      <button class="btn bad" type="button" data-node-action="reject">거절</button>
    </div>
  </article>`;
}

function renderMappingQueueSummary() {
  const queueEl = document.getElementById("mapping-candidate-queue");
  if (!queueEl) return;
  const sourceLabel = _mappingState.source?.title || (_mappingState.sourceCount > 1 ? `${_mappingState.sourceCount}개 source` : "전체 source");
  queueEl.innerHTML = `
    <div class="mapping-summary-card">
      <div class="mapping-summary-row"><span class="label">검토 범위</span><span class="value">${escapeHtml(sourceLabel)}</span></div>
      <div class="mapping-summary-row"><span class="label">node 그룹</span><span class="value">${_mappingState.groups.length}</span></div>
      <div class="mapping-summary-row"><span class="label">orphan claim</span><span class="value">${_mappingState.orphanClaims.length}</span></div>
      <div class="mapping-summary-row"><span class="label">API</span><span class="value">/api/review/suggestions/grouped</span></div>
    </div>`;
}

function renderOrphanClaims() {
  if (!_mappingState.orphanClaims.length) return "";
  return `<section class="orphan-claim-panel">
    <h3>source-level orphan claims</h3>
    <div class="node-claim-list">
      ${_mappingState.orphanClaims.map((claim) => `<div class="claim-orphan-row"><b>${escapeHtml(claim.statement || claim.candidate_key || claim.id)}</b>${claim.review_reason ? `<div class="claim-checkbox-reason">${escapeHtml(claim.review_reason)}</div>` : ""}</div>`).join("")}
    </div>
  </section>`;
}

function collectNodeDecisionPayload(cardEl) {
  const groupId = cardEl?.dataset?.groupId;
  const group = _mappingState.groups.find((item) => item.group_id === groupId);
  const selectedClaimIds = Array.from(cardEl.querySelectorAll(".node-claim-checkbox:checked")).map((input) => input.value);
  const selectedSimilarNode = cardEl.querySelector(`input[name="similar-node-${groupId}"]:checked`);
  const targetConceptId = selectedSimilarNode?.value || null;
  const targetTitle = cardEl.querySelector(".node-target-title")?.value?.trim() || group?.node_candidate?.title || null;
  const note = cardEl.querySelector(".node-decision-note")?.value?.trim() || null;
  return {
    node_candidate_id: group?.node_candidate?.id || groupId,
    claim_candidate_ids: selectedClaimIds,
    target_concept_id: targetConceptId,
    target_title: targetTitle,
    note,
    metadata: {
      surface: "node_centric_review",
      included_claim_candidate_ids: selectedClaimIds,
    },
  };
}

async function submitNodeDecision(groupId, action) {
  const cardEl = document.querySelector(`.node-suggestion-card[data-group-id="${CSS.escape(groupId)}"]`);
  if (!cardEl) return;
  const request = collectNodeDecisionPayload(cardEl);
  request.action = action;
  if (["merge_into_existing", "link_related"].includes(action) && !request.target_concept_id) {
    showToast("유사한 기존 Node를 하나 선택하세요.", "warn");
    return;
  }
  const res = await apiFetch(API.reviewSuggestionDecideNode, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  if (res !== null) {
    showToast(`결정 저장 완료 · 포함 ${res.included_claim_count} / 제외 ${res.excluded_claim_count}`, "ok");
    loadMapping();
  } else {
    showToast("결정 저장에 실패했습니다.", "bad");
  }
}

function bindNodeSuggestionCard(cardEl) {
  const titleInput = cardEl.querySelector(".node-target-title");
  cardEl.querySelectorAll("input[type=radio][name^='similar-node-']").forEach((radio) => {
    radio.addEventListener("change", () => {
      if (titleInput && radio.dataset.title && !titleInput.value.trim()) titleInput.value = radio.dataset.title;
    });
  });
  cardEl.querySelectorAll("[data-node-action]").forEach((button) => {
    button.addEventListener("click", () => submitNodeDecision(cardEl.dataset.groupId, button.dataset.nodeAction));
  });
}

function renderReviewBoard() {
  const boardEl = document.getElementById("mapping-review-board");
  if (!boardEl) return;
  const query = _mappingState.searchQuery.trim().toLowerCase();
  const groups = !query
    ? _mappingState.groups
    : _mappingState.groups.filter((group) => {
      const node = group.node_candidate || {};
      const haystack = [node.title, node.summary, node.review_reason, ...(node.aliases || []), ...(group.claims || []).map((claim) => claim.statement || claim.candidate_key)].join(" ").toLowerCase();
      return haystack.includes(query);
    });
  if (!groups.length) {
    boardEl.innerHTML = renderStateBanner("no_data", "조건에 맞는 node 후보가 없습니다.");
    return;
  }
  boardEl.innerHTML = `${groups.map((group) => renderNodeSuggestionCard(group)).join("")}${renderOrphanClaims()}`;
  boardEl.querySelectorAll(".node-suggestion-card").forEach((card) => bindNodeSuggestionCard(card));
}

export async function loadMapping() {
  const queueEl = document.getElementById("mapping-candidate-queue");
  const boardEl = document.getElementById("mapping-review-board");
  const countEl = document.getElementById("mapping-new-count");
  if (!queueEl || !boardEl) return;

  queueEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading review suggestions…</div>`;
  boardEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading review suggestions…</div>`;

  const setupData = await apiFetch(API.setupStatus);
  const setupState = classifySetupState(setupData);
  if (setupState === "setup_missing") {
    const banner = renderStateBanner("setup_missing", "후보 검토를 사용하려면 Setup을 먼저 완료하세요.", { href: "/onboarding", label: "Open Onboarding" });
    queueEl.innerHTML = banner;
    boardEl.innerHTML = banner;
    if (countEl) countEl.textContent = "new: 0";
    return;
  }

  const urlParams = new URLSearchParams(window.location.search);
  const sourceId = urlParams.get("source_id");
  const query = sourceId ? `?source_id=${encodeURIComponent(sourceId)}&status_filter=pending` : "?status_filter=pending";
  const data = await apiFetch(`${API.reviewSuggestionsGrouped}${query}`);
  _mappingState.groups = data?.node_groups || [];
  _mappingState.orphanClaims = data?.orphan_claims || [];
  _mappingState.source = data?.source || null;
  _mappingState.sourceCount = data?.source_count || 0;
  if (countEl) countEl.textContent = `new: ${_mappingState.groups.length}`;

  renderMappingQueueSummary();
  renderReviewBoard();
}

export function bindMappingActions() {
  document.getElementById("mapping-queue-search")?.addEventListener("input", (event) => {
    _mappingState.searchQuery = event.target.value || "";
    renderReviewBoard();
  });
}

// ============================================================
// MAPPING UI REDESIGN — Node Document Review / Editor
// Two-pane: left = node list, right = editor panel
// ============================================================

let _mappingUIState = {
  groups: [],
  orphanClaims: [],
  source: null,
  sourceCount: 0,
  searchQuery: "",
  selectedGroupId: null,
  // Draft tracking
  draftDirty: false,
  draftData: null,       // { title, body, tags, aliases, node_type, ... }
  originalDraftData: null, // snapshot at load or last save
};

function _getGroupById(groupId) {
  return _mappingUIState.groups.find((g) => g.group_id === groupId) || null;
}

function _buildDraftFromGroup(group) {
  const node = group?.node_candidate || {};
  return {
    title: node.title || node.candidate_key || "",
    body: node.body || node.summary || "",
    tags: Array.isArray(node.tags) ? [...node.tags] : [],
    aliases: Array.isArray(node.aliases) ? [...node.aliases] : [],
    node_type: node.node_type || "concept",
    candidate_key: node.candidate_key || group?.group_id || "",
    source_id: group?.source_id || group?.source?.id || "",
    status: node.status || "pending",
  };
}

function _serializeDraftToMarkdown(draft) {
  const tagsLine = draft.tags.length
    ? `tags: [${draft.tags.map((t) => `"${t}"`).join(", ")}]`
    : "tags: []";
  const aliasesLine = draft.aliases.length
    ? `aliases: [${draft.aliases.map((a) => `"${a}"`).join(", ")}]`
    : "";
  const lines = [
    "---",
    `title: "${draft.title}"`,
    `type: ${draft.node_type || "concept"}`,
    tagsLine,
  ];
  if (aliasesLine) lines.push(aliasesLine);
  lines.push("---", "");
  lines.push(draft.body || "");
  return lines.join("\n");
}

function _serializeFrontmatterToYaml(draft) {
  const tagsLine = draft.tags.length
    ? `[${draft.tags.map((t) => `"${t}"`).join(", ")}]`
    : "[]";
  const aliasesLine = draft.aliases.length
    ? `[${draft.aliases.map((a) => `"${a}"`).join(", ")}]`
    : "[]";
  const lines = [
    `title: "${draft.title}"`,
    `type: ${draft.node_type || "concept"}`,
    `source: ${draft.source_id || ""}`,
    `status: ${draft.status || "pending"}`,
    `tags: ${tagsLine}`,
  ];
  if (draft.aliases.length) lines.push(`aliases: ${aliasesLine}`);
  return lines.join("\n");
}

function _parseYamlFrontmatter(frontmatter) {
  // Minimal parser: extracts title, type, tags, aliases
  const result = { title: "", type: "concept", tags: [], aliases: [] };
  if (!frontmatter) return result;
  const lines = frontmatter.split("\n");
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("title:")) {
      const m = trimmed.match(/^title:\s*"?([^"]*)"?/);
      if (m) result.title = m[1].trim();
    } else if (trimmed.startsWith("type:")) {
      const m = trimmed.match(/^type:\s*(\S+)/);
      if (m) result.type = m[1].trim();
    } else if (trimmed.startsWith("tags:")) {
      const m = trimmed.match(/^tags:\s*\[(.*)\]/);
      if (m) {
        const inner = m[1].trim();
        if (inner) {
          result.tags = inner.split(",").map((t) => t.trim().replace(/^"|"$/g, ""));
        }
      }
    } else if (trimmed.startsWith("aliases:")) {
      const m = trimmed.match(/^aliases:\s*\[(.*)\]/);
      if (m) {
        const inner = m[1].trim();
        if (inner) {
          result.aliases = inner.split(",").map((t) => t.trim().replace(/^"|"$/g, ""));
        }
      }
    }
  }
  return result;
}

function _detectDraftDirty() {
  if (!_mappingUIState.draftData || !_mappingUIState.originalDraftData) return false;
  const curr = _mappingUIState.draftData;
  const orig = _mappingUIState.originalDraftData;
  return (
    curr.title !== orig.title ||
    curr.body !== orig.body ||
    JSON.stringify([...curr.tags].sort()) !== JSON.stringify([...orig.tags].sort()) ||
    JSON.stringify([...curr.aliases].sort()) !== JSON.stringify([...orig.aliases].sort()) ||
    curr.node_type !== orig.node_type
  );
}

function _updateDraftDirtyUI() {
  const dirty = _detectDraftDirty();
  _mappingUIState.draftDirty = dirty;
  const indicator = document.querySelector(".dirty-indicator");
  if (indicator) indicator.classList.toggle("hidden", !dirty);
  const saveBtn = document.getElementById("mapping-btn-save");
  if (saveBtn) saveBtn.disabled = !dirty;
  const confirmBtn = document.getElementById("mapping-btn-confirm");
  if (confirmBtn) {
    confirmBtn.disabled = false;
    confirmBtn.title = dirty ? "변경사항을 먼저 저장하세요." : "저장된 draft를 확정합니다.";
    confirmBtn.classList.toggle("needs-save", dirty);
  }
}

function renderMappingNodeList() {
  const listEl = document.getElementById("mapping-node-list");
  if (!listEl) return;
  const query = _mappingUIState.searchQuery.toLowerCase();
  const groups = _mappingUIState.groups.filter((group) => {
    const node = group.node_candidate || {};
    const haystack = [
      node.title, node.candidate_key, node.summary,
      ...(node.tags || []),
      ...(node.aliases || []),
    ].join(" ").toLowerCase();
    return !query || haystack.includes(query);
  });

  if (!groups.length) {
    listEl.innerHTML = `<div class="empty-state"><p>${
      query ? "검색 결과가 없습니다." : "검토할 Node가 없습니다."
    }</p></div>`;
    return;
  }

  listEl.innerHTML = groups.map((group) => {
    const node = group.node_candidate || {};
    const isActive = group.group_id === _mappingUIState.selectedGroupId ? " active" : "";
    const title = node.title || node.candidate_key || "신규노드";
    const status = node.review_status || node.status || "pending";
    return `<button class="node-list-item${isActive}" type="button" data-group-id="${escapeHtml(group.group_id)}">
      <span class="node-list-item-title">${escapeHtml(title)}</span>
      <span class="node-list-item-status">(${escapeHtml(status)})</span>
    </button>`;
  }).join("");

  listEl.querySelectorAll(".node-list-item").forEach((item) => {
    item.addEventListener("click", () => selectMappingNode(item.dataset.groupId));
  });
}

function renderMappingNodeEditor() {
  const editorEl = document.getElementById("mapping-node-editor");
  if (!editorEl) return;
  const groupId = _mappingUIState.selectedGroupId;
  if (!groupId) {
    editorEl.innerHTML = `<div class="empty-state"><p>왼쪽 목록에서 검토할 Node를 선택하세요.</p></div>`;
    return;
  }
  const group = _getGroupById(groupId);
  if (!group) {
    editorEl.innerHTML = `<div class="empty-state"><p>Node를 찾을 수 없습니다.</p></div>`;
    return;
  }
  const node = group.node_candidate || {};
  const draft = _mappingUIState.draftData || _buildDraftFromGroup(group);
  _mappingUIState.draftData = draft;
  if (!_mappingUIState.originalDraftData) {
    _mappingUIState.originalDraftData = { ...draft, tags: [...draft.tags], aliases: [...draft.aliases] };
  }
  const similarNodes = Array.isArray(group.similar_nodes) ? group.similar_nodes : [];
  const claims = Array.isArray(group.claims) ? group.claims : [];

  const similarNodesHtml = similarNodes.length
    ? similarNodes.map((m) => {
      const cid = m.concept_id || m.id || "";
      const title = m.title || cid;
      const score = Number(m.score || 0).toFixed(2);
      return `<label class="similar-node-radio-row">
        <input type="radio" name="similar-node-select" value="${escapeHtml(cid)}" data-title="${escapeHtml(title)}" />
        <span>${escapeHtml(title)}</span>
        <span class="similar-node-score">${score}</span>
      </label>`;
    }).join("")
    : `<div class="hint">유사한 기존 Node가 없습니다.</div>`;

  const claimsHtml = claims.length
    ? claims.map((claim) => {
      const checked = claim.checked_default ? "checked" : "";
      return `<div class="claim-diagnostic-row">
        <input type="checkbox" class="node-claim-checkbox" value="${escapeHtml(claim.id)}" ${checked} />
        <div class="claim-diagnostic-body">
          <div class="claim-diagnostic-label">${escapeHtml(claim.statement || claim.candidate_key || claim.id)}</div>
          ${claim.review_reason ? `<div class="claim-diagnostic-reason">${escapeHtml(claim.review_reason)}</div>` : ""}
        </div>
      </div>`;
    }).join("")
    : `<div class="hint">LLM Claim/self-evaluation 결과가 없습니다.</div>`;

  const dirty = _detectDraftDirty();
  const sourceLabel = group.source?.title || group.source?.origin || group.source_id || "";

  // Frontmatter grid rows — tags emphasized
  const fmRows = [
    { key: "title", value: draft.title || "", editable: true, inputId: "mapping-fm-title-input" },
    { key: "type", value: draft.node_type || "concept", editable: true, inputId: "mapping-type-input", isSelect: true },
    { key: "source", value: draft.source_id || sourceLabel || "", editable: false },
    { key: "status", value: draft.status || "pending", editable: false },
  ];

  const frontmatterGridHtml = fmRows.map((row) => {
    if (row.editable && !row.isSelect) {
      return `<div class="fm-key">${escapeHtml(row.key)}</div>
        <div class="fm-val"><input type="text" id="${row.inputId}" class="fm-inline-input" value="${escapeHtml(row.value)}" /></div>`;
    }
    if (row.isSelect) {
      return `<div class="fm-key">${escapeHtml(row.key)}</div>
        <div class="fm-val"><select id="${row.inputId}" class="fm-inline-input">
          <option value="concept" ${draft.node_type === "concept" ? "selected" : ""}>concept</option>
          <option value="claim" ${draft.node_type === "claim" ? "selected" : ""}>claim</option>
          <option value="source" ${draft.node_type === "source" ? "selected" : ""}>source</option>
        </select></div>`;
    }
    return `<div class="fm-key">${escapeHtml(row.key)}</div><div class="fm-val">${escapeHtml(row.value)}</div>`;
  }).join("");

  const tagsHtml = draft.tags.map((t) => `<span class="fm-tag-pill">${escapeHtml(t)}</span>`).join(" ");

  editorEl.innerHTML = `<div class="node-editor-shell">
    <header class="node-editor-header-bar">
      <div class="node-name-wrap">
        <span class="node-name-label">노드명</span>
        <input type="text" class="node-name-input" id="mapping-title-input" value="${escapeHtml(draft.title)}" placeholder="Node 제목" />
      </div>
      <button class="similar-nodes-toggle-btn" type="button" id="mapping-similar-toggle">
        🔗 유사 Node ${similarNodes.length}건 보기
      </button>
    </header>

    <div class="node-similar-nodes-drawer" id="mapping-similar-drawer" hidden>
      <div class="similar-nodes-options">
        <label class="similar-node-radio-row">
          <input type="radio" name="similar-node-select" value="" data-title="" />
          <span class="hint">신규 Node로 생성</span>
        </label>
        ${similarNodesHtml}
      </div>
    </div>

    <div class="node-editor-body">
      <section class="section-card wiki-page-card">
        <div class="section-head">
          <h2>Wiki Page</h2>
          <span>실제로 저장될 문서 preview/edit</span>
        </div>
        <div class="section-body">
          <details class="subsection" id="mapping-fm" open>
            <summary class="subhead">
              <strong>Frontmatter</strong>
              <span class="chev">펼침 ▾</span>
            </summary>
            <div class="frontmatter-grid">
              ${frontmatterGridHtml}
              <div class="fm-key fm-tags-key">tags</div>
              <div class="fm-val fm-tags-val">
                <div id="mapping-tags-display" class="fm-tags-display">${tagsHtml || `<span class="hint">태그 없음</span>`}</div>
                <input type="text" id="mapping-tags-input" class="fm-inline-input fm-tags-input" value="${escapeHtml(draft.tags.join(", "))}" placeholder="쉼표로 태그 입력 (예: ai, llm)" />
              </div>
            </div>
          </details>

          <details class="subsection" id="mapping-content" open>
            <summary class="subhead">
              <strong>Content</strong>
              <span class="chev">펼침 ▾</span>
            </summary>
            <textarea class="node-content-editor" id="mapping-content-editor" rows="16" placeholder="Node 본문을 입력하세요 (Markdown).">${escapeHtml(draft.body)}</textarea>
          </details>
        </div>
      </section>

      <details class="section-card diagnostics-card" id="mapping-diagnostics">
        <summary class="section-head">
          <h2>🤖 LLM 진단 / Claim</h2>
          <span>기본 접힘 · ${claims.length}건</span>
        </summary>
        <div class="section-body diagnostics-body">
          <span class="hint">Claim은 LLM 자체 평가/근거 진단입니다. 필요할 때만 열어서 확인합니다.</span>
          <div class="node-claim-list">
            ${claimsHtml}
          </div>
        </div>
      </details>
    </div>

    <footer class="node-editor-footer">
      <div class="dirty-indicator ${dirty ? "" : "hidden"}">
        ⚠️ 변경사항 있음 · 저장 후 확정 가능
      </div>
      <div class="footer-actions">
        <button class="btn btn-save" id="mapping-btn-save" type="button" ${dirty ? "" : "disabled"}>저장</button>
        <button class="btn btn-confirm" id="mapping-btn-confirm" type="button">확정</button>
        <button class="btn btn-reject" id="mapping-btn-reject" type="button">반려</button>
      </div>
    </footer>
  </div>`;

  // Bind events
  bindMappingEditorEvents(group.group_id);
  _updateDraftDirtyUI();
}

function bindMappingEditorEvents(groupId) {
  const titleInput = document.getElementById("mapping-title-input");
  const fmTitleInput = document.getElementById("mapping-fm-title-input");
  const typeInput = document.getElementById("mapping-type-input");
  const tagsInput = document.getElementById("mapping-tags-input");
  const contentInput = document.getElementById("mapping-content-editor");

  function _syncDraftFromFields(event) {
    const draft = _mappingUIState.draftData;
    if (!draft) return;

    const titleSource = event?.target === fmTitleInput ? fmTitleInput : titleInput;
    if (titleSource) {
      draft.title = titleSource.value;
      if (titleInput && titleInput.value !== draft.title) titleInput.value = draft.title;
      if (fmTitleInput && fmTitleInput.value !== draft.title) fmTitleInput.value = draft.title;
    }
    if (typeInput) draft.node_type = typeInput.value;
    if (contentInput) draft.body = contentInput.value;

    if (tagsInput) {
      draft.tags = tagsInput.value.split(",").map((t) => t.trim()).filter(Boolean);
      const display = document.getElementById("mapping-tags-display");
      if (display) {
        display.innerHTML = draft.tags.length
          ? draft.tags.map((t) => `<span class="fm-tag-pill">${escapeHtml(t)}</span>`).join(" ")
          : `<span class="hint">태그 없음</span>`;
      }
    }
    _updateDraftDirtyUI();
  }

  titleInput?.addEventListener("input", _syncDraftFromFields);
  fmTitleInput?.addEventListener("input", _syncDraftFromFields);
  typeInput?.addEventListener("change", _syncDraftFromFields);
  contentInput?.addEventListener("input", _syncDraftFromFields);
  tagsInput?.addEventListener("blur", _syncDraftFromFields);

  // Similar nodes toggle button
  const similarToggle = document.getElementById("mapping-similar-toggle");
  const similarDrawer = document.getElementById("mapping-similar-drawer");
  similarToggle?.addEventListener("click", () => {
    if (similarDrawer) similarDrawer.hidden = !similarDrawer.hidden;
  });

  // Save button
  document.getElementById("mapping-btn-save")?.addEventListener("click", () => saveMappingDraft(groupId));

  // Confirm / 확정 — warn if dirty, do not submit
  document.getElementById("mapping-btn-confirm")?.addEventListener("click", () => {
    if (_mappingUIState.draftDirty) {
      showToast("변경사항을 먼저 저장하세요.", "warn");
      return;
    }
    submitMappingDecision(groupId, "create_new");
  });

  // Reject / 반려
  document.getElementById("mapping-btn-reject")?.addEventListener("click", () => submitMappingDecision(groupId, "reject"));

  // Similar nodes radio — auto-fill title if empty
  document.querySelectorAll("input[name='similar-node-select']").forEach((radio) => {
    radio.addEventListener("change", () => {
      if (radio.checked && radio.value && titleInput && !titleInput.value.trim()) {
        titleInput.value = radio.dataset.title || radio.value;
        _syncDraftFromFields();
      }
    });
  });
}

async function saveMappingDraft(groupId) {
  const group = _getGroupById(groupId);
  if (!group) return;
  const draft = _mappingUIState.draftData;
  if (!draft) return;

  const payload = {
    node_candidate_id: group.node_candidate?.id || groupId,
    frontmatter: _serializeFrontmatterToYaml(draft),
    body: draft.body,
    title: draft.title,
    tags: draft.tags,
    aliases: draft.aliases,
    node_type: draft.node_type,
    source_id: draft.source_id,
    status: draft.status,
  };

  const res = await apiFetch("/api/mapping/draft", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (res !== null) {
    _mappingUIState.originalDraftData = { ...draft, tags: [...draft.tags], aliases: [...draft.aliases] };
    _updateDraftDirtyUI();
    showToast("변경사항이 저장되었습니다.", "ok");
  } else {
    showToast("저장에 실패했습니다.", "bad");
  }
}

async function submitMappingDecision(groupId, action) {
  const group = _getGroupById(groupId);
  if (!group) return;
  const draft = _mappingUIState.draftData || {};

  // Resolve target concept from similar-node radio
  const selectedRadio = document.querySelector("input[name='similar-node-select']:checked");
  const targetConceptId = selectedRadio?.value || null;
  const targetTitle = selectedRadio?.dataset?.title || draft.title || null;

  // Collect included/excluded claim IDs
  const claimCheckboxes = document.querySelectorAll(".node-claim-checkbox");
  const checkedClaimIds = Array.from(claimCheckboxes).filter((c) => c.checked).map((c) => c.value);
  const allClaimIds = Array.from(claimCheckboxes).map((c) => c.value);
  const excludedClaimIds = allClaimIds.filter((id) => !checkedClaimIds.includes(id));

  const effectiveAction = action === "create_new" && targetConceptId ? "merge_into_existing" : action;
  const request = {
    node_candidate_id: group.node_candidate?.id || groupId,
    claim_candidate_ids: checkedClaimIds,
    action: effectiveAction,
    target_concept_id: targetConceptId,
    target_title: targetTitle,
    note: null,
    metadata: {
      surface: "node_document_editor",
      included_claim_candidate_ids: checkedClaimIds,
      excluded_claim_candidate_ids: excludedClaimIds,
      edited_draft: {
        title: draft.title,
        tags: draft.tags,
        aliases: draft.aliases,
        node_type: draft.node_type,
        body: draft.body,
      },
    },
  };

  const res = await apiFetch("/api/review/suggestions/decide-node", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });

  if (res !== null) {
    const actionLabel = { create_new: "신규 Node 생성", defer: "보류", reject: "반려", merge_into_existing: "기존 Node 병합" }[effectiveAction] || effectiveAction;
    showToast(`결정 완료: ${actionLabel}`, "ok");
    _mappingUIState.selectedGroupId = null;
    _mappingUIState.draftData = null;
    _mappingUIState.originalDraftData = null;
    _mappingUIState.draftDirty = false;
    loadMappingUI();
  } else {
    showToast("결정 저장에 실패했습니다.", "bad");
  }
}

function selectMappingNode(groupId) {
  // Warn if dirty and switching away
  if (_mappingUIState.draftDirty && _mappingUIState.selectedGroupId && _mappingUIState.selectedGroupId !== groupId) {
    if (!window.confirm("변경사항이 저장되지 않았습니다. 정말 다른 Node로 전환하시겠습니까?")) {
      return;
    }
  }
  _mappingUIState.selectedGroupId = groupId;
  _mappingUIState.draftData = null;
  _mappingUIState.originalDraftData = null;
  _mappingUIState.draftDirty = false;
  renderMappingNodeList();
  renderMappingNodeEditor();
}

export async function loadMappingUI() {
  const listEl = document.getElementById("mapping-node-list");
  const editorEl = document.getElementById("mapping-node-editor");
  if (!listEl || !editorEl) return;

  listEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading nodes…</div>`;
  editorEl.innerHTML = `<div class="empty-state"><p>왼쪽 목록에서 검토할 Node를 선택하세요.</p></div>`;

  const setupData = await apiFetch(API.setupStatus);
  const setupState = classifySetupState(setupData);
  if (setupState === "setup_missing") {
    listEl.innerHTML = renderStateBanner("setup_missing", "Setup을 먼저 완료하세요.", { href: "/onboarding", label: "Open Onboarding" });
    editorEl.innerHTML = renderStateBanner("setup_missing", "Setup을 먼저 완료하세요.", { href: "/onboarding", label: "Open Onboarding" });
    return;
  }

  const urlParams = new URLSearchParams(window.location.search);
  const sourceId = urlParams.get("source_id");
  const query = sourceId
    ? `?source_id=${encodeURIComponent(sourceId)}&status_filter=pending`
    : "?status_filter=pending";

  const data = await apiFetch(`${API.reviewSuggestionsGrouped}${query}`);
  _mappingUIState.groups = data?.node_groups || [];
  _mappingUIState.orphanClaims = data?.orphan_claims || [];
  _mappingUIState.source = data?.source || null;
  _mappingUIState.sourceCount = data?.source_count || 0;

  // Restore selected group if reloading; otherwise select the first available node so the editor is not empty.
  const selectedId = _mappingUIState.selectedGroupId;
  if (selectedId && !_getGroupById(selectedId)) {
    _mappingUIState.selectedGroupId = null;
  }
  if (!_mappingUIState.selectedGroupId && _mappingUIState.groups.length) {
    const firstGroup = _mappingUIState.groups[0];
    _mappingUIState.selectedGroupId = firstGroup.group_id;
    _mappingUIState.draftData = _buildDraftFromGroup(firstGroup);
    _mappingUIState.originalDraftData = {
      ..._mappingUIState.draftData,
      tags: [..._mappingUIState.draftData.tags],
      aliases: [..._mappingUIState.draftData.aliases],
    };
    _mappingUIState.draftDirty = false;
  }

  renderMappingNodeList();
  renderMappingNodeEditor();
}

export function bindMappingUIActions() {
  document.getElementById("mapping-queue-search")?.addEventListener("input", (event) => {
    _mappingUIState.searchQuery = event.target.value || "";
    renderMappingNodeList();
  });
}


// ============================================================
// WIKI
// ============================================================
let _wikiState = { pages: [], selectedId: null };

export async function loadWikiPages(query = "") {
  const listEl = document.getElementById("wiki-page-list");
  if (!listEl) return;
  listEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading wiki pages…</div>`;

  // WU-006: Check setup status first — if incomplete, show explicit setup_missing banner
  const setupData = await apiFetch(API.setupStatus);
  const setupState = classifySetupState(setupData);
  if (setupState === "setup_missing") {
    listEl.innerHTML = renderStateBanner(
      "setup_missing",
      "Wiki requires completed setup. Configure LLM, Vault, and workspace first.",
      { href: "/onboarding", label: "Open Onboarding" }
    );
    return;
  }

  const url = query ? `${API.wikiPages}?query=${encodeURIComponent(query)}` : API.wikiPages;
  const data = await apiFetch(url);
  const items = data?.pages || [];
  _wikiState.pages = items;

  // WU-006: Distinguish no_data vs has_pages
  if (!items.length) {
    listEl.innerHTML = renderStateBanner(
      "no_data",
      "No wiki pages yet. Process inbox items and confirm mappings to generate wiki pages.",
      { href: "/inbox", label: "Open Inbox" }
    );
    return;
  }

  // Group by path for TOC-style display
  const groups = {};
  for (const p of items) {
    const path = (p.path || "").split("/").slice(0, -1).join("/") || "root";
    if (!groups[path]) groups[path] = [];
    groups[path].push(p);
  }

  let html = "";
  for (const [folder, pages] of Object.entries(groups)) {
    html += `<div class="wiki-toc-group"><div class="wiki-toc-folder">${escapeHtml(folder)}</div>`;
    for (const p of pages) {
      html += `<div class="wiki-toc-item" data-concept-id="${escapeHtml(p.id)}">
        <span class="wiki-toc-title">${escapeHtml(p.title || p.id)}</span>
      </div>`;
    }
    html += `</div>`;
  }
  listEl.innerHTML = html;

  listEl.querySelectorAll(".wiki-toc-item").forEach((el) => {
    el.addEventListener("click", () => selectWikiConcept(el.dataset.conceptId, el));
  });
}

export function bindWikiSearch() {
  const searchInput = document.getElementById("wiki-search");
  if (!searchInput) return;
  let timer = null;
  searchInput.addEventListener("input", (e) => {
    clearTimeout(timer);
    timer = setTimeout(() => loadWikiPages(e.target.value), 300);
  });
}

export function bindWikiMobileToc() {
  const tocBtn = document.getElementById("btn-wiki-toc");
  const drawer = document.getElementById("wiki-toc-drawer");
  const closeBtn = document.getElementById("btn-wiki-toc-close");
  const drawerBody = document.getElementById("wiki-toc-drawer-body");
  const tocCol = document.getElementById("wiki-toc-col");

  // Show mobile buttons on small screens
  function checkMobile() {
    const isMobile = window.innerWidth <= 768;
    if (tocBtn) tocBtn.style.display = isMobile ? "" : "none";
    const searchMobileBtn = document.getElementById("btn-wiki-search-mobile");
    if (searchMobileBtn) searchMobileBtn.style.display = isMobile ? "" : "none";
  }
  checkMobile();
  window.addEventListener("resize", checkMobile);

  tocBtn?.addEventListener("click", () => {
    if (drawer && drawerBody && tocCol) {
      drawerBody.innerHTML = tocCol.innerHTML;
      // Rebind clicks in drawer
      drawerBody.querySelectorAll(".wiki-toc-item").forEach((el) => {
        el.addEventListener("click", () => {
          selectWikiConcept(el.dataset.conceptId);
          drawer.classList.remove("open");
        });
      });
    }
    drawer?.classList.add("open");
  });
  closeBtn?.addEventListener("click", () => drawer?.classList.remove("open"));
}

export async function selectWikiConcept(conceptId, el) {
  document.querySelectorAll(".wiki-toc-item, .wiki-page-item").forEach((n) => n.classList.remove("active"));
  if (el) el.classList.add("active");
  _wikiState.selectedId = conceptId;

  const detailEl = document.getElementById("wiki-detail");
  if (!detailEl) return;
  detailEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading…</div>`;

  const data = await apiFetch(API.wikiPageDetail(conceptId));
  if (!data) {
    detailEl.innerHTML = `<div class="empty">문서를 찾을 수 없습니다.<br><a class="btn" href="/wiki">Back to Wiki list</a></div>`;
    return;
  }
  const page = data.page || data.concept || data;
  const { frontmatter, body } = stripFrontmatter(page.content || "");

  detailEl.innerHTML = `
    <div class="wiki-reader">
      <div class="wiki-file-path">${escapeHtml(page.path || "")}</div>
      <h1>${escapeHtml(page.title || "")}</h1>
      <div class="wiki-body md-rendered">${renderMarkdown(body)}</div>
      <details class="wiki-metadata"><summary>Metadata</summary>
        <div class="system-row"><span class="label">Aliases</span><span class="value">${(page.aliases || []).map(escapeHtml).join(", ") || "—"}</span></div>
        <div class="system-row"><span class="label">Tags</span><span class="value">${(page.tags || []).map(escapeHtml).join(", ") || "—"}</span></div>
        <div class="system-row"><span class="label">Sources</span><span class="value">${(page.sources || []).length}</span></div>
        ${frontmatter ? `<details class="preview"><summary>Raw frontmatter</summary><div class="code">${escapeHtml(frontmatter)}</div></details>` : ""}
      </details>
      <div class="wiki-graph-section">
        <h4>Related graph</h4>
        <div id="wiki-graph-container" class="wiki-graph-container">
          <div class="hint">Graph loading…</div>
        </div>
      </div>
    </div>
  `;

  // Load graph
  loadWikiGraph(conceptId);
}

async function loadWikiGraph(conceptId) {
  const container = document.getElementById("wiki-graph-container");
  if (!container) return;
  const data = await apiFetch(API.wikiPageGraph(conceptId));
  const nodes = data?.graph?.nodes || data?.nodes || [];
  const edges = data?.graph?.edges || data?.edges || [];
  if (!data || !nodes.length) {
    container.innerHTML = `<div class="hint">연결된 관계가 아직 없습니다. <a href="/mapping">Open Mapping</a></div>`;
    return;
  }
  if (!edges.length) {
    container.innerHTML = `<div class="empty">이 문서는 이미 알려져 있지만 아직 연결된 관계가 없습니다. <a href="/mapping">Open Mapping</a></div>`;
    return;
  }
  let html = '<div class="wiki-graph-list">';
  for (const e of edges) {
    html += `<div class="relation-row"><a href="/wiki/${encodeURIComponent(e.source)}">${escapeHtml(e.source)}</a> --${escapeHtml(e.label || "related_to")}--> <a href="/wiki/${encodeURIComponent(e.target)}">${escapeHtml(e.target)}</a></div>`;
  }
  html += '</div>';
  container.innerHTML = html;
}

// ============================================================
// VAULT BROWSER
// ============================================================
let _vaultState = { tree: null, selectedFolder: null, selectedFile: null };

export async function loadVaultTree() {
  const treeEl = document.getElementById("vault-folder-tree");
  if (!treeEl) return;
  treeEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading file tree…</div>`;

  // WU-006: Check setup status first — if incomplete, show explicit setup_missing banner
  const setupData = await apiFetch(API.setupStatus);
  const setupState = classifySetupState(setupData);
  if (setupState === "setup_missing") {
    treeEl.innerHTML = renderStateBanner(
      "setup_missing",
      "Vault browser requires completed setup. Configure LLM, Vault, and workspace first.",
      { href: "/onboarding", label: "Open Onboarding" }
    );
    return;
  }

  const data = await apiFetch(API.vaultTree);
  if (!data || !data.tree) {
    // WU-006: Explicit failure state for vault tree load failure
    treeEl.innerHTML = renderStateBanner(
      "failure",
      "Unable to load vault tree. Check vault path configuration and permissions.",
      { href: "/settings?tab=vault", label: "Open Settings" }
    );
    return;
  }
  _vaultState.tree = data.tree;
  const renderedTree = renderVaultFileTreeNode(data.tree, "");
  treeEl.innerHTML = renderedTree || renderStateBanner("no_data", "Vault is empty or has no visible folders yet.", { href: "/inbox", label: "Add source" });
  bindVaultFileTreeRows(treeEl);
  loadVaultFileList("");
}

function vaultTreeChildId(folderPath) {
  return `vault-tree-children-${String(folderPath || "root").replace(/[^a-zA-Z0-9_-]/g, "-") || "root"}`;
}

function renderVaultFileTreeFile(file) {
  return `<div class="vault-tree-entry vault-tree-file" data-file-path="${escapeHtml(file.path)}" data-tree-label="${escapeHtml(file.name)}">
    <span class="file-icon">${file.name?.endsWith(".md") ? "📄" : "📎"}</span>
    <span class="vault-tree-name">${escapeHtml(file.name)}</span>
    <span class="vault-tree-meta">${file.size ? `${(file.size / 1024).toFixed(1)} KB` : ""}</span>
  </div>`;
}

function renderVaultFileTreeNode(node, prefix) {
  if (!node) return "";
  const folders = node.children || [];
  const folderPath = node.path || prefix || "";
  const childrenHtml = folders.map((child) => renderVaultFileTreeNode(child, child.path || "")).join("");
  if (!folderPath) return childrenHtml;
  const childId = vaultTreeChildId(folderPath);
  return `<div class="vault-tree-entry vault-tree-folder collapsed" data-folder-path="${escapeHtml(folderPath)}" data-tree-label="${escapeHtml(node.name || folderPath)}" data-children-id="${escapeHtml(childId)}" data-loaded="${node.children_loaded ? "true" : "false"}" aria-expanded="false">
    <span class="folder-icon">📁</span><span class="vault-tree-name">${escapeHtml(node.name || folderPath)}</span>
  </div>
  <div class="vault-tree-children" id="${escapeHtml(childId)}" hidden>${childrenHtml}</div>`;
}

async function loadVaultTreeChildren(row) {
  const folderPath = row.dataset.folderPath || "";
  const childrenId = row.dataset.childrenId;
  const children = childrenId ? document.getElementById(childrenId) : row.nextElementSibling;
  if (!children || row.dataset.loaded === "true") return;
  children.innerHTML = `<div class="loading"><span class="spinner"></span>Loading folder…</div>`;
  const listing = await apiFetch(`${API.vaultFolder}?path=${encodeURIComponent(folderPath)}`);
  if (!listing) {
    children.innerHTML = renderStateBanner("failure", `Could not read folder: ${folderPath || "vault root"}`);
    return;
  }
  const foldersHtml = (listing.folders || []).map((folder) => renderVaultFileTreeNode({ ...folder, children: [], children_loaded: false }, folder.path || "")).join("");
  const filesHtml = (listing.files || []).map((file) => renderVaultFileTreeFile(file)).join("");
  children.innerHTML = foldersHtml + filesHtml || `<div class="empty">Empty folder</div>`;
  row.dataset.loaded = "true";
  bindVaultFileTreeRows(children);
}

function bindVaultFileTreeRows(rootEl) {
  rootEl.querySelectorAll(".vault-tree-folder").forEach((row) => {
    if (row.dataset.bound === "true") return;
    row.dataset.bound = "true";
    row.addEventListener("click", async () => {
      const collapsed = !row.classList.contains("collapsed");
      row.classList.toggle("collapsed", collapsed);
      row.setAttribute("aria-expanded", String(!collapsed));
      const childrenId = row.dataset.childrenId;
      const children = childrenId ? document.getElementById(childrenId) : row.nextElementSibling;
      if (children?.classList.contains("vault-tree-children")) {
        children.hidden = collapsed;
        if (!collapsed) await loadVaultTreeChildren(row);
      }
      selectVaultFolder(row.dataset.folderPath || "");
    });
  });
  rootEl.querySelectorAll(".vault-tree-file").forEach((row) => {
    if (row.dataset.bound === "true") return;
    row.dataset.bound = "true";
    row.addEventListener("click", () => {
      rootEl.querySelectorAll(".vault-tree-entry").forEach((item) => item.classList.toggle("active", item === row));
      loadVaultFile(row.dataset.filePath);
    });
  });
}

function selectVaultFolder(path) {
  _vaultState.selectedFolder = path;
  document.querySelectorAll(".vault-tree-node").forEach((n) => n.classList.toggle("active", n.dataset.path === path));
  loadVaultFileList(path);
}

async function loadVaultFileList(folderPath) {
  const listEl = document.getElementById("vault-file-list");
  if (!listEl) return;
  listEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading files…</div>`;

  const data = await apiFetch(`${API.vaultFolder}?path=${encodeURIComponent(folderPath)}`);
  const files = data?.files || [];
  if (!files.length) {
    listEl.innerHTML = `<div class="empty">이 폴더에는 파일이 없습니다.</div>`;
    return;
  }
  listEl.innerHTML = files.map((f) => `
    <div class="vault-file-row" data-file-path="${escapeHtml(f.path)}">
      <span class="file-icon">${f.name?.endsWith(".md") ? "📄" : "📎"}</span>
      <div class="vault-file-body">
        <div class="vault-file-name">${escapeHtml(f.name)}</div>
        <div class="vault-file-meta">${escapeHtml(f.extension || "")} · ${f.size ? `${(f.size / 1024).toFixed(1)} KB` : ""} · ${escapeHtml(f.modified || "")}</div>
      </div>
    </div>
  `).join("");

  listEl.querySelectorAll(".vault-file-row").forEach((row) => {
    row.addEventListener("click", () => loadVaultFile(row.dataset.filePath));
  });
}

async function loadVaultFile(filePath) {
  const viewerEl = document.getElementById("vault-viewer");
  if (!viewerEl) return;
  viewerEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading file…</div>`;

  const data = await apiFetch(`${API.vaultFile}?path=${encodeURIComponent(filePath)}`);
  if (!data) {
    // WU-006: Explicit failure state for vault file load failure
    viewerEl.innerHTML = renderStateBanner(
      "failure",
      "Unable to read file. Check path and permissions.",
      null
    );
    return;
  }

  const file = data.file || data;
  const content = file.content || "";
  const isMarkdown = filePath.endsWith(".md");
  const { frontmatter, body } = isMarkdown ? stripFrontmatter(content) : { frontmatter: null, body: content };

  // WU-006: Explicit read-only indicator
  const readOnlyBanner = `<div class="state-banner state-muted" data-state-kind="read_only">
    <span class="state-banner-icon">🔒</span>
    <div class="state-banner-body">
      <div class="state-banner-label">Read-only</div>
      <div class="state-banner-message">Vault browser is read-only. Edit files in your editor.</div>
    </div>
  </div>`;

  let viewerHtml = `
    <div class="vault-viewer-header">
      <div class="vault-file-path">${escapeHtml(filePath)}</div>
    </div>
    ${readOnlyBanner}
  `;

  if (isMarkdown) {
    viewerHtml += `<div class="md-rendered">${renderMarkdown(body)}</div>`;
    if (frontmatter) {
      viewerHtml += `<details class="preview"><summary>Metadata (frontmatter)</summary><div class="code">${escapeHtml(frontmatter)}</div></details>`;
    }
    viewerHtml += `<details class="preview"><summary>Raw markdown</summary><div class="code">${escapeHtml(body)}</div></details>`;
  } else if (filePath.endsWith(".json")) {
    try {
      viewerHtml += `<div class="code">${escapeHtml(JSON.stringify(JSON.parse(content), null, 2))}</div>`;
    } catch {
      viewerHtml += `<div class="code">${escapeHtml(content)}</div>`;
    }
  } else {
    viewerHtml += `<div class="code">${escapeHtml(content)}</div>`;
  }

  viewerEl.innerHTML = viewerHtml;
}

export function bindVaultBrowser() {
  // Search in GitHub-style file tree
  document.getElementById("vault-tree-search")?.addEventListener("input", (e) => {
    const q = e.target.value.toLowerCase();
    document.querySelectorAll(".vault-tree-entry").forEach((n) => {
      n.style.display = (n.dataset.treeLabel || n.textContent).toLowerCase().includes(q) ? "" : "none";
    });
  });
}

// ============================================================
// SETTINGS
// ============================================================
export function loadSettingsTabs() {
  const tabs = document.querySelectorAll(".settings-tab");
  const panes = document.querySelectorAll(".settings-pane");
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.tab;
      tabs.forEach((t) => { t.classList.remove("active"); t.setAttribute("aria-selected", "false"); });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      panes.forEach((p) => {
        p.style.display = p.id === `settings-pane-${target}` ? "block" : "none";
      });
      const url = new URL(window.location);
      url.searchParams.set("tab", target);
      window.history.replaceState({}, "", url);
    });
  });
}

function syncPromptSequenceScroll() {
  const active = document.querySelector("#settings-prompt-top-tabs .prompt-sequence-item.active");
  active?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "center" });
}

function modelDisplayName(m) {
  return m?.display_name || m?.model_name || m?.name || m?.id || "";
}

export async function loadSettingsLLM() {
  const basicEl = document.getElementById("settings-llm-basic");
  const advancedRequestEl = document.getElementById("settings-llm-advanced-request-options");
  const registryEl = document.getElementById("settings-model-registry");
  const routeTableEl = document.getElementById("settings-route-table");
  const historyEl = document.getElementById("settings-route-history");

  if (basicEl) {
    basicEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading…</div>`;
    const data = await apiFetch(API.settingsLlmStatus);
    if (!data) {
      basicEl.innerHTML = `<div class="empty">LLM provider가 설정되지 않았습니다.<br><a class="btn primary" href="/onboarding">Open Onboarding setup</a></div>`;
    } else {
      const s = data.settings || {};
      const missing = data.missing || {};
      const configuredChatModel = s.models?.chat_default?.model_name || "";
      const embeddingConfig = data.embedding || {};
      const configuredEmbeddingModel = embeddingConfig.default_model || "";
      const configuredEmbeddingRoot = embeddingConfig.model_root || "";
      const providerModels = (Array.isArray(data.provider_models) ? data.provider_models : []).filter((m) => m.capability === "chat" || !m.capability);
      const embeddingModels = Array.isArray(data.embedding_models) ? data.embedding_models : [];
      const configuredChatOptions = configuredChatModel && !providerModels.some((m) => (m.model_name || m.id) === configuredChatModel)
        ? [{ id: configuredChatModel, model_name: configuredChatModel, display_name: configuredChatModel, provider: s.provider || "configured" }]
        : [];
      const llmModelOptions = [...configuredChatOptions, ...providerModels];
      const configuredEmbeddingOptions = configuredEmbeddingModel && !embeddingModels.some((m) => (m.model_name || m.id) === configuredEmbeddingModel)
        ? [{ id: configuredEmbeddingModel, model_name: configuredEmbeddingModel, display_name: configuredEmbeddingModel, provider: "configured" }]
        : [];
      const embeddingModelOptions = [...configuredEmbeddingOptions, ...embeddingModels];
      const renderModelOptions = (models, currentValue) => models.map((m) => {
        const value = m.model_name || m.id || "";
        const label = modelDisplayName(m);
        const meta = m.dim ? ` · ${m.dim}d` : "";
        return `<option value="${escapeHtml(value)}" ${value === currentValue ? "selected" : ""}>${escapeHtml(label + meta)}</option>`;
      }).join("");
      basicEl.innerHTML = `
        <form id="settings-llm-basic-form" class="config-form">
          <label>Provider
            <select class="input" name="provider">
              <option value="ollama" ${s.provider === "ollama" ? "selected" : ""}>Ollama</option>
              <option value="lmstudio" ${s.provider === "lmstudio" ? "selected" : ""}>LM Studio</option>
              <option value="custom" ${s.provider === "custom" ? "selected" : ""}>Custom</option>
            </select>
          </label>
          <label>Endpoint URL
            <input class="input" name="endpoint" value="${escapeHtml(s.endpoint || "")}" placeholder="LM Studio: http://host:1234 or http://host:1234/v1 · Ollama: http://host:11434" autocomplete="off" />
            <span class="hint">LM Studio/custom은 OpenAI-compatible base URL 또는 /v1 URL을 지원합니다. Ollama는 base URL 또는 /api URL을 지원합니다.</span>
          </label>
          <label>Model timeout seconds
            <input class="input" name="timeout_seconds" type="number" min="5" max="1800" step="1" value="${escapeHtml(String(s.timeout_seconds || 120))}" />
            <span class="hint">긴 PDF/원문 처리용 LLM 응답 timeout입니다. 5–1800초 범위에서 저장됩니다.</span>
          </label>
          <label>API key
            <input class="input" type="password" name="api_key" placeholder="${missing.api_key_missing ? "Not configured" : "Configured — enter to change"}" autocomplete="off" />
          </label>
          <input type="hidden" name="default_chat_model" value="chat_default" />
          <input type="hidden" name="default_embedding_model" value="embedding_default" />
          <div class="llm-current-models">
            <label>Current LLM model
              <select class="input" id="settings-llm-model-select" name="chat_model_name">
                ${renderModelOptions(llmModelOptions, configuredChatModel)}
              </select>
            </label>
            <label>Local embedding model root
              <input class="input" id="settings-embedding-model-root" name="embedding_model_root" value="${escapeHtml(configuredEmbeddingRoot)}" placeholder="/path/to/local/embedding-models" autocomplete="off" />
              <span class="hint">Embedding 모델은 provider endpoint가 아니라 이 로컬 폴더의 하위 디렉토리 목록에서 읽습니다.</span>
            </label>
            <label>Current embedding model
              <select class="input" id="settings-embedding-model-select" name="embedding_model_name">
                ${renderModelOptions(embeddingModelOptions, configuredEmbeddingModel)}
              </select>
              <span class="hint">목록이 비어 있으면 model root 경로를 확인하세요. 선택값은 <code>embedding.default_model</code>로 저장됩니다.</span>
            </label>
            <p class="hint">LLM model은 LM Studio/Ollama/custom provider endpoint에서 가져오고, Embedding model은 로컬 model root의 폴더 리스트에서 가져옵니다.</p>
            <p class="hint">Route id는 내부적으로 <code>chat_default</code>/<code>embedding_default</code>를 유지합니다.</p>
          </div>
          <div class="status-chips">
            <span class="pill ${missing.endpoint_missing ? "bad" : "ok"}">Endpoint ${missing.endpoint_missing ? "missing" : "set"}</span>
            <span class="pill ${missing.api_key_missing ? "bad" : "ok"}">API key ${missing.api_key_missing ? "missing" : "configured"}</span>
          </div>
          <div class="actions">
            <button class="btn primary" type="submit">Save basic settings</button>
            <button class="btn" type="button" id="btn-settings-test-connection">Test connection</button>
            <button class="btn" type="button" id="btn-settings-refresh-models">Refresh models</button>
          </div>
        </form>
      `;
      if (advancedRequestEl) {
        const advanced = s.advanced || {};
        advancedRequestEl.innerHTML = `
          <div class="llm-request-options">
            <h5>Request options</h5>
            <p class="hint">비워두면 provider/local LLM 기본값을 사용합니다. Think Off 환경에서는 max_tokens를 비우는 것이 기본입니다.</p>
            <form id="settings-llm-advanced-form" class="config-form compact">
              <label>Temperature
                <input class="input" name="temperature" type="number" min="0" max="2" step="0.01" value="${advanced.temperature ?? ""}" placeholder="default" />
              </label>
              <label>Max tokens
                <input class="input" name="max_tokens" type="number" min="1" step="1" value="${advanced.max_tokens ?? ""}" placeholder="provider default" />
              </label>
              <div class="actions"><button class="btn" type="submit">Save request options</button></div>
            </form>
          </div>
        `;
        document.getElementById("settings-llm-advanced-form")?.addEventListener("submit", async (event) => {
          event.preventDefault();
          const form = new FormData(event.currentTarget);
          const temperatureRaw = String(form.get("temperature") || "").trim();
          const maxTokensRaw = String(form.get("max_tokens") || "").trim();
          const defaultApiKeyEnv = ["LLM", "WIKI", "API", "KEY"].join("_");
          const payload = {
            provider: s.provider || "custom",
            endpoint: s.endpoint || "",
            api_key_env: s.api_key_env || defaultApiKeyEnv,
            timeout_seconds: Number(document.querySelector('[name="timeout_seconds"]')?.value || s.timeout_seconds || 120),
            default_chat_model: "chat_default",
            default_embedding_model: "embedding_default",
            chat_model_name: document.querySelector('[name="chat_model_name"]')?.value || s.models?.chat_default?.model_name || "",
            embedding_model_name: document.querySelector('[name="embedding_model_name"]')?.value || s.models?.embedding_default?.model_name || "",
            embedding_model_root: document.querySelector('[name="embedding_model_root"]')?.value || embeddingConfig.model_root || "",
            temperature: temperatureRaw === "" ? null : Number(temperatureRaw),
            max_tokens: maxTokensRaw === "" ? null : Number(maxTokensRaw),
          };
          const res = await apiFetch(API.settingsLlmConfig, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
          });
          if (res !== null) {
            showToast("LLM request options saved", "ok");
            loadSettingsLLM();
          } else {
            showToast("Save failed", "bad");
          }
        });
      }
      document.getElementById("settings-llm-basic-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        const payload = Object.fromEntries(form.entries());
        if (s.advanced?.temperature !== undefined) payload.temperature = s.advanced.temperature;
        if (s.advanced?.max_tokens !== undefined) payload.max_tokens = s.advanced.max_tokens;
        // Clear api_key if empty (don't overwrite)
        if (!payload.api_key) delete payload.api_key;
        const res = await apiFetch(API.settingsLlmConfig, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (res !== null) {
          showToast("LLM settings saved", "ok");
          // Clear password field after save
          const keyInput = e.currentTarget.querySelector('input[name="api_key"]');
          if (keyInput) keyInput.value = "";
          loadSettingsLLM();
        } else {
          showToast("Save failed", "bad");
        }
      });
      const persistSettingsLlmBasicFormBeforeTest = async () => {
        const currentForm = document.getElementById("settings-llm-basic-form");
        if (!currentForm) return true;
        const payload = Object.fromEntries(new FormData(currentForm).entries());
        if (s.advanced?.temperature !== undefined) payload.temperature = s.advanced.temperature;
        if (s.advanced?.max_tokens !== undefined) payload.max_tokens = s.advanced.max_tokens;
        if (!payload.api_key) delete payload.api_key;
        const saved = await apiFetch(API.settingsLlmConfig, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        return saved !== null;
      };
      document.getElementById("btn-settings-test-connection")?.addEventListener("click", async () => {
        showToast("Saving and testing connection…", "ok", 1500);
        const saved = await persistSettingsLlmBasicFormBeforeTest();
        if (!saved) { showToast("Save failed before connection test", "bad"); return; }
        const chat = await apiFetch(API.settingsLlmTest("chat_default"), { method: "POST" });
        const embedding = await apiFetch(API.settingsLlmTest("embedding_default"), { method: "POST" });
        const passed = chat?.test_status === "passed" && embedding?.test_status === "passed";
        if (passed) showToast("Connection OK", "ok");
        else showToast(`Connection ${chat?.test_status || "failed"}/${embedding?.test_status || "failed"}: ${chat?.reason || embedding?.reason || "see settings"}`, "bad", 5000);
        loadSettingsLLM();
      });
      document.getElementById("btn-settings-refresh-models")?.addEventListener("click", () => loadSettingsLLM());
    }
  }

  // Model registry
  if (registryEl) {
    const data = await apiFetch(API.settingsModels);
    const models = data?.models || [];
    const chatModels = models.filter((m) => m.capability === "chat" || !m.capability);
    if (!chatModels.length) {
      registryEl.innerHTML = `<div class="empty">사용 가능한 chat model이 없습니다.<br><button class="btn" onclick="location.reload()">Refresh models</button></div>`;
    } else {
      let html = "<h5>Chat models</h5>";
      html += chatModels.map((m) => `
        <div class="model-row">
          <span class="model-name">${escapeHtml(modelDisplayName(m))}</span>
          <span class="pill">${escapeHtml(m.capability || "chat")}</span>
          <span class="pill muted">slot ${escapeHtml(m.id || "")}</span>
          ${m.is_default ? '<span class="pill ok">default</span>' : ""}
        </div>
      `).join("");
      registryEl.innerHTML = html;
    }
  }

  // Task routes
  if (routeTableEl) {
    const data = await apiFetch(API.settingsLlmStatus);
    const routes = data?.routes || {};
    const models = (data?.models || []).filter((m) => m.capability === "chat" || !m.capability);
    const taskLabels = {
      page_validate: "Page 검증",
      page_mapping: "Page Mapping",
      relationship_validate: "Relationship 검증",
      retry_instruction: "Retry instruction",
      prompt_test: "Prompt test",
      embedding: "Embedding/Search",
    };
    const modelOptions = models.map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(modelDisplayName(m))}</option>`).join("");

    routeTableEl.innerHTML = `
      <table class="model-table">
        <thead><tr><th>Task</th><th>Model</th><th>Status</th><th></th></tr></thead>
        <tbody>
          ${Object.entries(taskLabels).map(([taskId, label]) => {
            const currentModel = routes[taskId] || models[0]?.id || "";
            const isDefault = !routes[taskId];
            return `<tr class="route-row" data-task="${taskId}">
              <td>${escapeHtml(label)}</td>
              <td><select class="route-model-select" data-task="${taskId}">${modelOptions}</select></td>
              <td><span class="pill ${isDefault ? "" : "ok"}">${isDefault ? "default" : "custom"}</span></td>
              <td><button class="btn ok btn-use-model" data-task="${taskId}">Use this model</button></td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>
    `;

    // Set current values
    for (const [taskId, modelId] of Object.entries(routes)) {
      const select = routeTableEl.querySelector(`select[data-task="${taskId}"]`);
      if (select) select.value = modelId;
    }

    // Use this model buttons
    routeTableEl.querySelectorAll(".btn-use-model").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const taskId = btn.dataset.task;
        const select = routeTableEl.querySelector(`select[data-task="${taskId}"]`);
        const modelId = select?.value;
        if (!modelId) { showToast("Select a model first", "warn"); return; }
        const res = await apiFetch(API.settingsLlmRoute, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task_type: taskId, model_id: modelId }),
        });
        if (res !== null) showToast(`Route ${taskId} → ${modelId} saved`, "ok");
        else showToast("Save failed", "bad");
      });
    });
  }

  // Concurrency
  async function refreshConcurrencyUi() {
    const data = await apiFetch(API.settingsLlmConcurrency);
    if (!data) return null;
    const selected = String(data.value ?? "1");
    document.querySelectorAll('input[name="concurrency"]').forEach((radio) => {
      radio.checked = radio.value === selected;
    });
    const warning = document.getElementById("concurrency-warning");
    if (warning) warning.style.display = parseInt(selected, 10) > 1 ? "" : "none";
    return data;
  }

  await refreshConcurrencyUi();
  document.querySelectorAll('input[name="concurrency"]').forEach((radio) => {
    radio.onchange = () => {
      const warning = document.getElementById("concurrency-warning");
      if (warning) warning.style.display = parseInt(radio.value) > 1 ? "" : "none";
    };
  });
  const saveConcurrencyBtn = document.getElementById("btn-save-concurrency");
  if (saveConcurrencyBtn) saveConcurrencyBtn.onclick = async () => {
    const val = parseInt(document.querySelector('input[name="concurrency"]:checked')?.value || "1", 10);
    const res = await apiFetch(API.settingsLlmConcurrency, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ value: val }),
    });
    if (res !== null) {
      await refreshConcurrencyUi();
      showToast(`Concurrency set to ${res.value ?? val}`, "ok");
    } else {
      showToast("Concurrency save failed", "bad");
    }
  };

  // History
  if (historyEl) {
    const data = await apiFetch("/api/settings/routes/history");
    const history = data?.history || [];
    if (!history.length) {
      historyEl.innerHTML = `<div class="empty">변경 이력이 없습니다.</div>`;
    } else {
      historyEl.innerHTML = history.map((h) => `
        <div class="system-row">
          <span class="label">${escapeHtml(h.changed_at || "")}</span>
          <span class="value">${escapeHtml(h.task || "")} ${escapeHtml(h.previous_model || "")} → ${escapeHtml(h.new_model || "")}</span>
        </div>
      `).join("");
    }
  }
}

export async function loadSettingsPrompts() {
  const topTabs = document.getElementById("settings-prompt-top-tabs");
  const workspaceEl = document.getElementById("settings-prompt-workspace");
  if (!topTabs || !workspaceEl) return;

  const data = await apiFetch(API.settingsPrompts);
  const groups = (data?.task_groups || []).slice().sort((a, b) => {
    const liveDelta = Number(b.is_live_llm_unit === true) - Number(a.is_live_llm_unit === true);
    if (liveDelta) return liveDelta;
    return (a.display_order ?? 999) - (b.display_order ?? 999);
  });

  if (!groups.length) {
    topTabs.innerHTML = `<div class="empty">Prompt task가 없습니다.</div>`;
    workspaceEl.innerHTML = `<div class="empty">Prompt 설정을 초기화해 주세요.</div>`;
    return;
  }

  const liveGroups = groups.filter((g) => g.is_live_llm_unit === true);
  const renderTab = (group, active = false) => `
    <button class="prompt-sequence-item ${active ? "active" : ""} ${group.is_live_llm_unit ? "live" : "legacy"}"
      data-prompt-task="${escapeHtml(group.task_type || "")}" role="tab" aria-selected="${active ? "true" : "false"}">
      <span class="prompt-tab-label">${escapeHtml(group.display_label || group.task_type || "Prompt")}</span>
      <span class="prompt-tab-purpose">${escapeHtml(group.purpose_label || group.task_type || "")}</span>
      <span class="pill ${group.is_live_llm_unit ? "ok" : ""}">${escapeHtml(group.status_label || (group.is_live_llm_unit ? "실제 LLM 호출" : "placeholder/legacy"))}</span>
    </button>
  `;
  const firstTask = liveGroups[0]?.task_type || groups[0]?.task_type;
  topTabs.innerHTML = `
    <div class="prompt-group-block live-units">
      <div class="prompt-group-title">실제 LLM 호출 단위 · ${liveGroups.length}개</div>
      <div class="hint">현재 실제 LLM과 통신하는 prompt만 여기에 표시됩니다. INBOX 후보 생성과 Ask 답변 합성입니다.</div>
      <div class="prompt-group-items">${liveGroups.map((g, idx) => renderTab(g, g.task_type === firstTask || (!firstTask && idx === 0))).join("")}</div>
    </div>
  `;

  topTabs.querySelectorAll(".prompt-sequence-item").forEach((tab) => {
    tab.onclick = () => {
      topTabs.querySelectorAll(".prompt-sequence-item").forEach((item) => {
        item.classList.remove("active");
        item.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      const taskType = tab.dataset.promptTask || firstTask || "extract_claims";
      const group = groups.find((g) => g.task_type === taskType);
      loadPromptWorkspace(group || { task_type: taskType, history: [] });
      syncPromptSequenceScroll();
    };
  });
  const firstGroup = groups.find((g) => g.task_type === firstTask) || groups[0];
  loadPromptWorkspace(firstGroup);
  syncPromptSequenceScroll();
}

async function loadPromptWorkspace(groupOrTask, maybeVersions) {
  const workspaceEl = document.getElementById("settings-prompt-workspace");
  if (!workspaceEl) return;

  const group = typeof groupOrTask === "string" ? { task_type: groupOrTask, history: maybeVersions || [] } : (groupOrTask || {});
  const taskType = group.task_type || "extract_claims";
  const versions = group.history || [];
  const confirmed = group.confirmed || versions.find((v) => v.state === "confirmed");
  const test = group.test || versions.find((v) => v.state === "test");
  const current = test || confirmed;
  const isLive = group.is_live_llm_unit === true;
  const statusLabel = group.status_label || (isLive ? "실제 LLM 호출" : "placeholder/legacy");

  workspaceEl.innerHTML = `
    <div class="prompt-active-status ${isLive ? "live" : "legacy"}">
      <div class="prompt-status-head">
        <div>
          <h4>${escapeHtml(group.display_label || taskType)}</h4>
          <div class="hint">${escapeHtml(group.purpose_label || taskType)}</div>
        </div>
        <span class="pill ${isLive ? "ok" : ""}">${escapeHtml(statusLabel)}</span>
      </div>
      <p class="prompt-purpose-copy">${escapeHtml(group.description || "Prompt task")}</p>
      <div class="system-row"><span class="label">Task</span><span class="value">${escapeHtml(taskType)}</span></div>
      <div class="system-row"><span class="label">Live unit</span><span class="value">${isLive ? "yes — 실제 LLM에 전달됨" : "no — placeholder/legacy"}</span></div>
      <div class="system-row"><span class="label">Version</span><span class="value">${escapeHtml(confirmed?.version_label || "not confirmed")}</span></div>
      <div class="system-row"><span class="label">Source</span><span class="value">${confirmed ? escapeHtml(confirmed.source === "phase2_default" ? "Phase 2 default prompt" : confirmed.source || "user confirmed") : "missing"}</span></div>
      <div class="system-row"><span class="label">State</span><span class="value"><span class="pill ${confirmed ? "ok" : "bad"}">${confirmed ? "confirmed" : "missing"}</span></span></div>
    </div>

    <div class="prompt-editor-section">
      <h4>Prompt editor</h4>
      <label>Change note
        <input class="input" id="prompt-change-note" placeholder="변경 사유 입력" />
      </label>
      <textarea id="prompt-editor-text" rows="12">${escapeHtml(current?.prompt_text || "")}</textarea>
      <div class="actions">
        <button class="btn" id="btn-prompt-save-test">Save test version</button>
        <button class="btn primary" id="btn-prompt-run-test">Run prompt test</button>
        <button class="btn" id="btn-prompt-discard">Discard draft</button>
      </div>
      <div id="prompt-test-result"></div>
    </div>

    <div class="prompt-version-history">
      <h4>Version history</h4>
      <div id="prompt-history-list">
        ${versions.map((v) => `
          <div class="prompt-version-row ${v.state === "confirmed" ? "confirmed" : ""}">
            <span class="pill ${v.state === "confirmed" ? "ok" : v.state === "test" ? "warn" : ""}">${escapeHtml(v.state)}</span>
            <span class="version-label">${escapeHtml(v.version_label || "")}</span>
            <span class="version-date">${escapeHtml(v.created_at || "")}</span>
            <span class="version-source">${escapeHtml(v.source || "")}</span>
            ${v.state === "confirmed" ? '<span class="pill">Current</span>' : ""}
            ${v.state === "archived" ? `<button class="btn btn-prompt-rollback" data-prompt-id="${escapeHtml(v.id)}">Rollback to this version</button>` : ""}
            ${v.state === "test" ? `<button class="btn ok btn-prompt-confirm" data-prompt-id="${escapeHtml(v.id)}">Confirm</button>` : ""}
          </div>
        `).join("")}
      </div>
    </div>
  `;

  // Save test
  document.getElementById("btn-prompt-save-test")?.addEventListener("click", async () => {
    const text = document.getElementById("prompt-editor-text")?.value || "";
    const note = document.getElementById("prompt-change-note")?.value || "";
    if (!note) { showToast("Change note is required", "warn"); return; }
    const res = await apiFetch(API.settingsPromptVersions, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_type: taskType, prompt_text: text, change_note: note }),
    });
    if (res !== null) {
      showToast("Test version saved", "ok");
      loadSettingsPrompts();
    } else {
      showToast("Save failed", "bad");
    }
  });

  // Run test
  document.getElementById("btn-prompt-run-test")?.addEventListener("click", async () => {
    const resultEl = document.getElementById("prompt-test-result");
    if (resultEl) resultEl.innerHTML = `<div class="loading"><span class="spinner"></span>Running test…</div>`;
    const text = document.getElementById("prompt-editor-text")?.value || "";
    const res = await apiFetch(API.settingsPromptTest, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_type: taskType, prompt_text: text }),
    });
    if (res && resultEl) {
      const status = res.test_status || res.status || "blocked";
      const ok = status === "passed";
      resultEl.innerHTML = `<div class="test-result ${ok ? "ok" : "bad"}">
        <div class="test-result-icon">${ok ? "✅" : "❌"}</div>
        <div>
          <div><b>Test ${escapeHtml(status)}</b></div>
          ${res.reason ? `<div class="hint bad">${escapeHtml(res.reason)}</div>` : ""}
          <div class="hint">Validation: ${escapeHtml(res.validation_type || "—")}</div>
          ${(res.schema_errors || []).length ? `<div class="hint bad">${escapeHtml((res.schema_errors || []).join("; "))}</div>` : ""}
        </div>
      </div>`;
      if (ok) loadSettingsPrompts();
    } else if (resultEl) {
      resultEl.innerHTML = `<div class="empty">Test result unavailable.</div>`;
    }
  });

  // Discard
  document.getElementById("btn-prompt-discard")?.addEventListener("click", () => {
    if (confirmed) {
      const editor = document.getElementById("prompt-editor-text");
      if (editor) editor.value = confirmed.prompt_text || "";
      showToast("Draft discarded", "ok");
    }
  });

  // Confirm test version
  workspaceEl.querySelectorAll(".btn-prompt-confirm").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const res = await apiFetch(API.settingsPromptConfirm(btn.dataset.promptId), { method: "POST" });
      if (res !== null) {
        showToast("Version confirmed", "ok");
        loadSettingsPrompts();
      } else {
        showToast("Confirm failed", "bad");
      }
    });
  });

  // Rollback
  workspaceEl.querySelectorAll(".btn-prompt-rollback").forEach((btn) => {
    btn.addEventListener("click", async () => {
      if (!confirm("이전 버전으로 rollback합니다. 현재 confirmed 버전은 archived 됩니다. 계속하시겠습니까?")) return;
      const res = await apiFetch(`/api/settings/prompts/${encodeURIComponent(btn.dataset.promptId)}/rollback`, { method: "POST" });
      if (res !== null) {
        showToast("Rollback complete", "ok");
        loadSettingsPrompts();
      } else {
        showToast("Rollback failed", "bad");
      }
    });
  });
}

export async function loadSettingsVault() {
  const el = document.getElementById("settings-vault-content");
  if (!el) return;
  el.innerHTML = `<div class="loading"><span class="spinner"></span>Loading vault info…</div>`;
  const data = await apiFetch(API.settingsVault);
  if (!data) {
    el.innerHTML = `<div class="empty">Vault 정보를 불러올 수 없습니다.</div>`;
    return;
  }
  el.innerHTML = `
    <div class="vault-info">
      <div class="vault-info-item"><span class="label">Vault Path</span><span class="value">${escapeHtml(data.vault_path || "—")}</span></div>
      <div class="vault-info-item"><span class="label">Data Path</span><span class="value">${escapeHtml(data.data_path || "—")}</span></div>
    </div>
    <div style="margin-top:16px">
      <a class="btn primary" href="/vault">Open Vault Browser</a>
      <a class="btn" href="${escapeHtml(data.onboarding_path || API.onboardingVault)}">Change in Onboarding</a>
    </div>
  `;
}

export async function loadSettingsAuth() {
  const el = document.getElementById("settings-auth-content");
  if (!el) return;
  el.innerHTML = `<div class="loading"><span class="spinner"></span>Loading auth status…</div>`;
  const data = await apiFetch(API.settingsAuth);
  if (!data) {
    el.innerHTML = `<div class="empty">Auth 정보를 불러올 수 없습니다.</div>`;
    return;
  }
  const configured = Boolean(data.web_admin_password_configured ?? data.configured);
  el.innerHTML = `
    <div class="auth-status">
      <div class="status-row"><span class="label">Web Admin Password</span><span class="pill ${configured ? "ok" : "bad"}">${configured ? "Configured" : "Not configured"}</span></div>
      <div class="status-row"><span class="label">Environment Variable</span><span class="value" style="font-family:monospace;font-size:12px">${escapeHtml(data.env_name || "—")}</span></div>
      <p class="hint" style="margin-top:8px">Password value is never displayed. Set via environment variable or .env file.</p>
    </div>
  `;
}

// ============================================================
// REVIEW (legacy — kept for backward compatibility with review.html)
// ============================================================
let _reviewState = { candidates: [], concepts: [], selectedConceptId: null, selectedCandidates: new Set() };

export async function loadReviewCandidates() {
  const listEl = document.getElementById("review-candidates");
  if (!listEl) return;
  listEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading candidates…</div>`;
  const data = await apiFetch(API.reviewCandidates);
  const items = data?.candidates || [];
  _reviewState.candidates = items;
  _reviewState.selectedCandidates.clear();

  const summaryEl = document.getElementById("candidate-count-pill");
  if (summaryEl) summaryEl.textContent = `Review candidates: ${items.length}`;

  if (!items.length) {
    listEl.innerHTML = `<div class="empty"><p>No pending candidates.</p><a class="btn primary" href="/onboarding">Open Onboarding</a></div>`;
    return;
  }

  const groups = {};
  for (const c of items) {
    const type = c.candidate_type || "unknown";
    if (!groups[type]) groups[type] = [];
    groups[type].push(c);
  }

  let html = "";
  for (const [type, candidates] of Object.entries(groups)) {
    html += `<div class="candidate-group"><h4>${escapeHtml(type)} (${candidates.length})</h4>`;
    for (const c of candidates) {
      const payload = c.payload || {};
      html += `<div class="candidate" data-candidate-id="${escapeHtml(c.id)}">
        <div style="display:flex;align-items:flex-start">
          <input type="checkbox" class="candidate-checkbox" data-candidate-id="${escapeHtml(c.id)}" />
          <div style="flex:1">
            <h3>${escapeHtml(payload.title || c.candidate_key || "")}</h3>
            <div class="candidate-meta">
              <span class="pill">${escapeHtml(c.candidate_type || "")}</span>
              <span class="pill">conf: ${Number(payload.model_confidence ?? 0).toFixed(2)}</span>
            </div>
            <p>${escapeHtml(payload.summary || c.review_reason || "")}</p>
            <div class="actions">
              <button class="btn ok" data-act="merge">Merge into selected wiki</button>
              <button class="btn primary" data-act="create_new">Create as new wiki</button>
              <button class="btn bad" data-act="retry_with_instruction">Reject+Retry</button>
            </div>
          </div>
        </div>
      </div>`;
    }
    html += `</div>`;
  }
  listEl.innerHTML = html;

  listEl.querySelectorAll(".candidate button[data-act]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const card = btn.closest(".candidate");
      const candidate = _reviewState.candidates.find((c) => c.id === card?.dataset.candidateId);
      if (candidate) handleReviewAction(candidate, btn.dataset.act);
    });
  });
  listEl.querySelectorAll(".candidate-checkbox").forEach((cb) => {
    cb.addEventListener("change", () => {
      if (cb.checked) _reviewState.selectedCandidates.add(cb.dataset.candidateId);
      else _reviewState.selectedCandidates.delete(cb.dataset.candidateId);
    });
  });
}

async function handleReviewAction(candidate, action) {
  if (action === "retry_with_instruction") {
    const instruction = prompt("Retry instruction:");
    if (!instruction) return;
    await apiFetch(API.reviewDecide, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: candidate.id, action, instruction }),
    });
    showToast("Reject + retry recorded", "ok");
    loadReviewCandidates();
    return;
  }
  await apiFetch(API.reviewDecide, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ candidate_id: candidate.id, action, metadata: _reviewState.selectedConceptId ? { target_concept_id: _reviewState.selectedConceptId } : {} }),
  });
  showToast(`Decision: ${action}`, "ok");
  loadReviewCandidates();
}

export async function loadConceptList(query = "") {
  const listEl = document.getElementById("wiki-similar-list");
  if (!listEl) return;
  listEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading concepts…</div>`;
  const data = await apiFetch(API.reviewConcepts);
  const items = data?.concepts || [];
  _reviewState.concepts = items;
  const filtered = query ? items.filter((c) => (c.title || c.id || "").toLowerCase().includes(query.toLowerCase())) : items;
  if (!filtered.length) {
    listEl.innerHTML = `<div class="empty">No concepts found.</div>`;
    return;
  }
  listEl.innerHTML = filtered.map((c) => `<div class="wiki-item" data-concept-id="${escapeHtml(c.id)}"><h3>${escapeHtml(c.title || c.id)}</h3><p>${escapeHtml(c.path || "")}</p></div>`).join("");
  listEl.querySelectorAll(".wiki-item").forEach((el) => {
    el.addEventListener("click", () => {
      document.querySelectorAll("#wiki-similar-list .wiki-item").forEach((n) => n.classList.remove("active"));
      el.classList.add("active");
      _reviewState.selectedConceptId = el.dataset.conceptId;
    });
  });
}

export async function openGraphPopup(conceptId, conceptTitle) {
  const overlay = document.getElementById("graph-popup-overlay");
  const graphEl = document.getElementById("graph-canvas");
  if (!overlay || !graphEl) return;
  overlay.classList.add("open");
  graphEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading graph…</div>`;
  const data = await apiFetch(API.reviewGraph(conceptId));
  if (!data) { graphEl.innerHTML = `<div class="empty">Failed to load graph.</div>`; return; }
  // Simple rendering
  graphEl.innerHTML = `<div class="hint">Graph: ${escapeHtml(conceptTitle || conceptId)} — ${data.graph?.nodes?.length || 0} nodes</div>`;
}

export function bindGraphPopupClose() {
  const closeBtn = document.getElementById("graph-popup-close");
  const overlay = document.getElementById("graph-popup-overlay");
  closeBtn?.addEventListener("click", () => overlay?.classList.remove("open"));
  overlay?.addEventListener("click", (e) => { if (e.target === overlay) overlay.classList.remove("open"); });
}

export function bindBatchActions() {
  // Legacy batch actions — simplified
  document.getElementById("batch-select-all")?.addEventListener("change", (e) => {
    document.querySelectorAll(".candidate-checkbox").forEach((cb) => {
      cb.checked = e.target.checked;
      if (e.target.checked) _reviewState.selectedCandidates.add(cb.dataset.candidateId);
      else _reviewState.selectedCandidates.delete(cb.dataset.candidateId);
    });
  });
  document.getElementById("btn-batch-apply")?.addEventListener("click", () => {
    showToast("Batch actions — use Mapping page for new workflow", "ok", 3000);
  });
}

// ============================================================
// SEARCH PAGE (GAP-1)
// ============================================================
export async function loadSearchPage() {
  document.querySelectorAll(".search-subtab").forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.searchPanel || "search";
      document.querySelectorAll(".search-subtab").forEach((item) => {
        const active = item === tab;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", active ? "true" : "false");
      });
      document.querySelectorAll(".search-mode-panel").forEach((panel) => {
        const active = panel.dataset.searchPanelContent === target;
        panel.hidden = !active;
        panel.classList.toggle("active", active);
      });
    });
  });

  const searchQuery = document.getElementById("search-query");
  const searchMode = document.getElementById("search-mode");
  const searchBtn = document.getElementById("btn-search");
  const searchResults = document.getElementById("search-results");
  const askQuery = document.getElementById("ask-query");
  const askBtn = document.getElementById("btn-ask");
  const askResult = document.getElementById("ask-result");
  let lastSearchPayload = null;
  let lastAskPayload = null;

  async function saveQueryResult(payload) {
    const data = await apiFetch(API.queriesSave, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!data || data.status !== "ok") {
      throw new Error("save failed");
    }
    return data;
  }

  // WU-006: Check setup status for Search/Ask — LLM/index state
  const setupData = await apiFetch(API.setupStatus);
  const setupState = classifySetupState(setupData);
  const llmStatus = setupData?.llm?.status || setupData?.llm?.connection_status || "unknown";
  const llmReady = ["ready", "passed"].includes(llmStatus);

  async function doSearch() {
    const q = (searchQuery?.value || "").trim();
    const mode = searchMode?.value || "combined";
    if (!q) {
      if (searchResults) searchResults.innerHTML = `<div class="empty">검색어를 입력하세요.</div>`;
      return;
    }

    // WU-006: If setup incomplete, show explicit setup_missing banner
    if (setupState === "setup_missing") {
      if (searchResults) searchResults.innerHTML = renderStateBanner(
        "setup_missing",
        "Search requires completed setup. Configure LLM, Vault, and workspace first.",
        { href: "/onboarding", label: "Open Onboarding" }
      );
      return;
    }

    if (searchResults) searchResults.innerHTML = `<div class="loading"><span class="spinner"></span>Searching…</div>`;
    if (["combined", "vector"].includes(mode) && ["not_detected", "db_missing", "unavailable"].includes(setupData?.db_vec_status)) {
      if (searchResults) searchResults.innerHTML = renderStateBanner("blocked", `Vector index is not ready (${setupData.db_vec_status}). Run embed/index processing first.`, { href: "/inbox", label: "Open Inbox" });
      return;
    }
    const data = await apiFetch(`/api/search?q=${encodeURIComponent(q)}&limit=20&mode=${encodeURIComponent(mode)}`);
    if (!data || data.status !== "ok") {
      // WU-006: Distinguish failure vs no results
      if (searchResults) searchResults.innerHTML = renderStateBanner(
        "failure",
        "Search failed. Check LLM connection and index status.",
        { href: "/settings?tab=llm", label: "Open Settings" }
      );
      return;
    }
    const results = data.results || [];
    lastSearchPayload = {
      query: q,
      body: results.map((r, index) => `${index + 1}. ${(r.title || r.target_id || r.source_id || "Result")}\n   - ${(r.snippet || r.content || "")}`).join("\n"),
      scope: "search",
      evidence: results,
      search_results: results,
      title: q,
      generation_mode: `web_search_${mode}`,
    };
    const meta = data.metadata || {};
    if (!results.length) {
      // WU-006: Explicit no_data state
      if (searchResults) searchResults.innerHTML = renderStateBanner(
        "no_data",
        "No search results found. Try a different query or search mode.",
        null
      );
      return;
    }
    let html = `<div class="search-meta"><span class="hint">${data.count || results.length} results · mode: ${escapeHtml(mode)}</span>`;
    if (meta.vector) {
      html += ` <span class="hint">vector: ${escapeHtml(meta.vector.backend || "—")} / ${escapeHtml(meta.vector.model || "—")}</span>`;
    }
    html += `</div>`;
    html += `<div class="search-result-list">`;
    for (const r of results) {
      const matchType = r.match_type || "unknown";
      const badgeClass = matchType.startsWith("vector") ? "ok" : matchType === "fts" ? "" : matchType === "metadata" ? "warn" : "";
      html += `<div class="search-result-row">
        <div class="search-result-header">
          <span class="pill ${badgeClass}">${escapeHtml(matchType)}</span>
          <span class="search-result-target">${escapeHtml(r.target_id || r.source_id || r.concept_id || "—")}</span>
          ${r.score != null ? `<span class="search-result-score">score: ${Number(r.score).toFixed(3)}</span>` : ""}
        </div>
        <div class="search-result-snippet">${escapeHtml(r.snippet || r.content || r.title || "")}</div>
        <div class="search-result-meta">
          ${r.vector_model ? `<span class="hint">vector_model: ${escapeHtml(r.vector_model)}</span>` : ""}
          ${r.vector_backend ? `<span class="hint">vector_backend: ${escapeHtml(r.vector_backend)}</span>` : ""}
          ${r.source_id ? `<span class="hint">source: ${escapeHtml(r.source_id)}</span>` : ""}
        </div>
      </div>`;
    }
    html += `</div>`;
    html += `<div class="ask-search-meta"><button class="btn" id="btn-save-search-query">Save to Queries</button><div class="hint" id="search-save-status"></div></div>`;
    if (searchResults) searchResults.innerHTML = html;
    document.getElementById("btn-save-search-query")?.addEventListener("click", async () => {
      const statusEl = document.getElementById("search-save-status");
      if (statusEl) statusEl.textContent = "저장 중…";
      try {
        const saved = await saveQueryResult(lastSearchPayload || {});
        if (statusEl) statusEl.textContent = `저장됨: ${saved.display_path || saved.saved_path}`;
        showToast("Queries에 저장했습니다.");
      } catch {
        if (statusEl) statusEl.textContent = "저장 실패";
        showToast("Queries 저장에 실패했습니다.", "bad");
      }
    });
  }

  searchBtn?.addEventListener("click", doSearch);
  searchQuery?.addEventListener("keydown", (e) => { if (e.key === "Enter") doSearch(); });

  async function doAsk() {
    const q = (askQuery?.value || "").trim();
    if (!q) {
      if (askResult) askResult.innerHTML = `<div class="empty">질문을 입력하세요.</div>`;
      return;
    }

    // WU-006: If setup incomplete or LLM not ready, show explicit blocked banner
    if (setupState === "setup_missing") {
      if (askResult) askResult.innerHTML = renderStateBanner(
        "setup_missing",
        "Ask requires completed setup. Configure LLM, Vault, and workspace first.",
        { href: "/onboarding", label: "Open Onboarding" }
      );
      return;
    }
    if (!llmReady) {
      if (askResult) askResult.innerHTML = renderStateBanner(
        "blocked",
        `LLM is not ready. Current status: ${llmStatus}. Configure LLM endpoint and models first.`,
        { href: "/settings?tab=llm", label: "Open Settings" }
      );
      return;
    }

    if (askResult) askResult.innerHTML = `<div class="loading"><span class="spinner"></span>Asking LLM…</div>`;
    const data = await apiFetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: q }),
    });
    if (!data || !["ok", "no_evidence"].includes(data.status || "")) {
      // WU-006: Explicit failure state
      if (askResult) askResult.innerHTML = renderStateBanner(
        "failure",
        "Ask failed. Check LLM connection and try again.",
        { href: "/settings?tab=llm", label: "Open Settings" }
      );
      return;
    }
    if (data.status === "no_evidence") {
      if (askResult) askResult.innerHTML = renderStateBanner("no_data", data.message || "No evidence was found for this question.", { href: "/search", label: "Try Search" });
      return;
    }
    const answer = data.answer || "No answer generated.";
    const evidenceRefs = data.evidence_refs || [];
    const searchMeta = data.search_metadata || {};
    lastAskPayload = {
      query: q,
      answer,
      scope: "wiki",
      evidence: evidenceRefs,
      search_results: data.search_results || [],
      title: q,
      generation_mode: "web_ask",
    };
    let html = `<div class="ask-answer">
      <h4>Answer</h4>
      <div class="md-rendered">${renderMarkdown(answer)}</div>
    </div>`;
    if (evidenceRefs.length) {
      html += `<div class="ask-evidence">
        <h4>Evidence references</h4>
        <ul>${evidenceRefs.map((ref) => `<li>${escapeHtml(String(ref))}</li>`).join("")}</ul>
      </div>`;
    }
    if (searchMeta.mode || searchMeta.count != null) {
      html += `<div class="ask-search-meta">
        <h4>Search metadata</h4>
        <div class="system-row"><span class="label">Mode</span><span class="value">${escapeHtml(searchMeta.mode || "—")}</span></div>
        <div class="system-row"><span class="label">Results used</span><span class="value">${searchMeta.count ?? "—"}</span></div>
        ${searchMeta.message ? `<div class="system-row"><span class="label">Note</span><span class="value">${escapeHtml(searchMeta.message)}</span></div>` : ""}
        </div>`;
    }
    html += `<div class="ask-search-meta"><button class="btn" id="btn-save-ask-query">Save to Queries</button><div class="hint" id="ask-save-status"></div></div>`;
    if (askResult) askResult.innerHTML = html;
    document.getElementById("btn-save-ask-query")?.addEventListener("click", async () => {
      const statusEl = document.getElementById("ask-save-status");
      if (statusEl) statusEl.textContent = "저장 중…";
      try {
        const saved = await saveQueryResult(lastAskPayload || {});
        if (statusEl) statusEl.textContent = `저장됨: ${saved.display_path || saved.saved_path}`;
        showToast("Queries에 저장했습니다.");
      } catch {
        if (statusEl) statusEl.textContent = "저장 실패";
        showToast("Queries 저장에 실패했습니다.", "bad");
      }
    });
  }

  askBtn?.addEventListener("click", doAsk);
  askQuery?.addEventListener("keydown", (e) => { if (e.key === "Enter" && e.ctrlKey) doAsk(); });
}

// ============================================================
// MOBILE NAV TOGGLE
// ============================================================
document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.getElementById("mobile-menu-toggle");
  const nav = document.getElementById("main-nav");
  toggle?.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", !expanded);
    nav?.classList.toggle("open");
  });
});

// ============================================================
// WINDOW EXPORTS (for inline handlers / non-module pages)
// ============================================================
if (typeof window !== "undefined") {
  window.LLMWiki = {
    loadDashboard, loadOnboarding: loadDashboard, loadWikiPages, bindWikiSearch, selectWikiConcept,
    loadReviewCandidates, loadConceptList, openGraphPopup, bindGraphPopupClose, bindBatchActions,
    loadSettingsTabs, loadSettingsLLM, loadSettingsPrompts, loadSettingsVault, loadSettingsAuth,
    loadInbox, bindInboxActions, loadMapping, bindMappingActions,
    loadMappingUI, bindMappingUIActions,
    loadVaultTree, bindVaultBrowser,
    loadSearchPage,
    // WU-006: State visibility helpers
    renderStateBanner, classifySetupState, classifyComponentStatus, safeStatusPill,
  };
}
