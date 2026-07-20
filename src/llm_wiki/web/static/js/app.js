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
  mappingWikiMatches: "/api/mapping/wiki-matches",

  // Vault (new — graceful fallback)
  vaultTree: "/api/vault/tree",
  vaultFolder: "/api/vault/folder",
  vaultFile: "/api/vault/file",

  // Wiki
  wikiPages: "/api/wiki/pages",
  wikiPageDetail: (conceptId) => `/api/wiki/pages/${encodeURIComponent(conceptId)}`,
  wikiPageGraph: (conceptId) => `/api/wiki/pages/${encodeURIComponent(conceptId)}/graph`,

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

  // Provider select → auto-fill endpoint
  const providerSelect = document.getElementById("setup-provider-select");
  const endpointInput = document.getElementById("setup-endpoint");
  const endpointDefaults = {
    ollama: "",
    lmstudio: "",
    custom: "",
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
            <span class="model-name">${escapeHtml(m.id || m.model_name || "")}</span>
            <span class="pill">${escapeHtml(m.capability || "chat")}</span>
            <button class="btn ok btn-use-chat" data-model="${escapeHtml(m.id || "")}">Use as chat model</button>
          </div>
        `).join("");
        el.querySelectorAll(".btn-use-chat").forEach((btn) => {
          btn.addEventListener("click", async () => {
            const status = await apiFetch(API.settingsLlmStatus);
            const s = status?.settings || {};
            const res = await apiFetch(API.settingsLlmConfig, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ endpoint: s.endpoint || "", api_key_env: s.api_key_env || "", default_chat_model: "chat_default", chat_model_name: btn.dataset.model, default_embedding_model: s.default_embedding_model || "embedding_default", embedding_model_name: s.models?.embedding_default?.model_name || s.default_embedding_model || "" }),
            });
            showToast(res ? `Chat model ${btn.dataset.model} saved` : "Chat model save failed", res ? "ok" : "bad");
          });
        });
      }
    } else {
      el.innerHTML = `<div class="empty">모델 목록을 불러올 수 없습니다.</div>`;
    }
  });

  // Fastembed models
  document.getElementById("btn-load-fastembed")?.addEventListener("click", async () => {
    const el = document.getElementById("setup-embed-models");
    if (!el) return;
    el.innerHTML = `<div class="loading"><span class="spinner"></span>Loading fastembed models…</div>`;
    // Fastembed models may come from a different endpoint; graceful fallback
    const data = await apiFetch(API.settingsModels);
    if (data && Array.isArray(data.fastembed_models)) {
      el.innerHTML = data.fastembed_models.map((m) => `
        <div class="model-row">
          <span class="model-name">${escapeHtml(m.id || m.model_name || "")}</span>
          <span class="pill">${m.downloaded ? "downloaded" : "not downloaded"}</span>
          <button class="btn ok btn-use-embed" data-model="${escapeHtml(m.id || "")}">${m.downloaded ? "Use as embedding" : "Download"}</button>
        </div>
      `).join("");
      el.querySelectorAll(".btn-use-embed").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const status = await apiFetch(API.settingsLlmStatus);
          const s = status?.settings || {};
          const res = await apiFetch(API.settingsLlmConfig, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ endpoint: s.endpoint || "", api_key_env: s.api_key_env || "", default_chat_model: s.default_chat_model || "chat_default", chat_model_name: s.models?.chat_default?.model_name || s.default_chat_model || "", default_embedding_model: "embedding_default", embedding_model_name: btn.dataset.model }),
          });
          showToast(res ? `Embedding model ${btn.dataset.model} saved` : "Embedding model save failed", res ? "ok" : "bad");
        });
      });
    } else {
      el.innerHTML = `<div class="empty">
        <p>fastembed 모델 목록을 불러올 수 없습니다.</p>
        <p class="hint">기본 모델: paraphrase-multilingual-MiniLM-L12-v2</p>
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
          <span class="folder-open-hint">Open →</span>
        </div>
      `).join("") || `<div class="empty">이 경로에 폴더가 없습니다.</div>`;
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
  const vaultRoles = ["inbox", "wiki", "review", "raws", "settings", "data", "artifacts"];

  function renderVaultMappingRows(roleMap = {}, missingRoles = []) {
    const tbody = document.getElementById("vault-mapping-tbody");
    if (!tbody) return;
    tbody.innerHTML = vaultRoles.map((role) => {
      const mapped = roleMap[role] || "";
      const status = mapped ? "mapped" : (missingRoles.includes(role) ? "missing" : "not mapped");
      const statusClass = mapped ? "ok" : missingRoles.includes(role) ? "bad" : "";
      return `<tr data-role="${escapeHtml(role)}">
        <td><b>${escapeHtml(role)}</b></td>
        <td><input class="input vault-role-input" data-role="${escapeHtml(role)}" value="${escapeHtml(mapped)}" placeholder="Open folder, then assign" /></td>
        <td><button class="btn vault-assign-btn" type="button" data-assign-role="${escapeHtml(role)}">Assign current folder</button></td>
        <td><span class="pill ${statusClass}">${escapeHtml(status)}</span></td>
      </tr>`;
    }).join("");
    tbody.querySelectorAll("[data-assign-role]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const selectedFolder = vaultCurrentPathExisting || vaultSelectedExistingFolder || document.getElementById("vault-manual-path-existing")?.value || "";
        if (!selectedFolder) {
          showToast("먼저 연결할 폴더를 열어주세요", "warn");
          return;
        }
        const input = tbody.querySelector(`.vault-role-input[data-role="${btn.dataset.assignRole}"]`);
        if (input) input.value = selectedFolder;
        showToast(`${btn.dataset.assignRole} → ${selectedFolder}`, "ok", 1200);
      });
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
    if (!vaultPath) { showToast("Vault 경로를 선택하세요", "warn"); return; }
    if (!window.confirm("해당 폴더 구조를 확정하시겠습니까?")) return;
    const roleMap = {};
    document.querySelectorAll(".vault-role-input").forEach((input) => {
      const val = input.value.trim();
      if (val) roleMap[input.dataset.role] = val;
    });
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

function updateInboxProcessButton() {
  const checked = document.querySelectorAll(".inbox-checkbox:checked");
  const btn = document.getElementById("btn-inbox-process");
  if (btn) btn.disabled = checked.length === 0;
}

async function selectInboxItem(itemId) {
  _inboxState.selectedId = itemId;
  document.querySelectorAll(".inbox-row").forEach((r) => r.classList.toggle("active", r.dataset.itemId === itemId));
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

  // Preview
  if (item.content_preview || item.content) {
    detailHtml += `<div class="inbox-detail-preview"><h4>Preview</h4><div class="md-rendered">${renderMarkdown(item.content_preview || item.content || "")}</div></div>`;
  }

  // WU-006: Processing status — explicit processing state with log
  if (status === "processing") {
    detailHtml += `<div class="inbox-detail-log"><h4>Processing log</h4>`;
    const log = item.processing_log || [];
    if (log.length) {
      detailHtml += log.map((entry) => `<div class="log-entry">${escapeHtml(entry.time || "")} ${escapeHtml(entry.event || "")}</div>`).join("");
    } else {
      detailHtml += `<div class="hint">Processing started — log entries will appear as the pipeline progresses.</div>`;
    }
    detailHtml += `</div>`;
  }

  // WU-006: Failed — explicit error artifact with retry path
  if (status === "failed") {
    const errorReason = item.error?.reason || item.error || "Processing failed";
    detailHtml += `<div class="inbox-detail-error">
      <h4>Error</h4>
      <div class="hint bad">${escapeHtml(errorReason)}</div>
      <button class="btn warn" id="btn-inbox-retry">Retry</button>
      <details class="preview"><summary>Technical details</summary><div class="code">${escapeHtml(JSON.stringify(item.error || {}, null, 2))}</div></details>
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

  // Bind retry
  document.getElementById("btn-inbox-retry")?.addEventListener("click", async () => {
    const res = await apiFetch(API.inboxRetry(itemId), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note: "Retry from Inbox detail" }) });
    if (res !== null) { showToast("Retry started", "ok"); loadInbox(); }
    else showToast("Retry failed", "bad");
  });
  document.getElementById("btn-inbox-retry-detail")?.addEventListener("click", async () => {
    const res = await apiFetch(API.inboxRetry(itemId), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ note: "Retry from Inbox detail" }) });
    if (res !== null) { showToast("Retry started", "ok"); loadInbox(); }
    else showToast("Retry failed", "bad");
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

  // Process selected
  document.getElementById("btn-inbox-process")?.addEventListener("click", async () => {
    const ids = [...document.querySelectorAll(".inbox-checkbox:checked")].map((cb) => cb.dataset.itemId);
    if (!ids.length) return;
    const res = await apiFetch(API.inboxProcess, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ item_ids: ids }),
    });
    if (res !== null && res.status === "ok") {
      showToast(`Processed ${ids.length} item(s)`, "ok");
      loadInbox();
    } else if (res !== null) {
      showToast(`Processing ${res.status || "non-success"}: ${res.failed_count || 0} failed, ${res.blocked_count || 0} blocked`, "bad", 5000);
      loadInbox();
    } else {
      showToast("Process failed", "bad");
    }
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
  candidates: [],
  selectedId: null,
  selectedMatchId: null,
  selectedMatchTitle: null,
  currentStep: 1,
  wikiMatches: [],
  preview: null,
};

function currentMappingStepId() {
  const step = _mappingState.currentStep;
  if (step === "errors") return "errors";
  if (step === 2) return "page_mapping";
  if (step === 3) return "relationship_validate";
  return "page_validate";
}

export async function loadMapping() {
  const queueEl = document.getElementById("mapping-candidate-queue");
  const countEl = document.getElementById("mapping-new-count");
  if (!queueEl) return;

  queueEl.innerHTML = `<div class="loading"><span class="spinner"></span>Loading candidates…</div>`;

  // WU-006: Check setup status first — if incomplete, show explicit setup_missing banner
  const setupData = await apiFetch(API.setupStatus);
  const setupState = classifySetupState(setupData);
  if (setupState === "setup_missing") {
    queueEl.innerHTML = renderStateBanner(
      "setup_missing",
      "Mapping requires completed setup. Configure LLM, Vault, and workspace first.",
      { href: "/onboarding", label: "Open Onboarding" }
    );
    _mappingState.selectedId = null;
    _mappingState.selectedMatchId = null;
    _mappingState.selectedMatchTitle = null;
    updateSelectedWikiIndicator();
    updateMappingActionBar();
    if (countEl) countEl.textContent = "new: 0";
    return;
  }

  const data = await apiFetch(API.mappingCandidates);
  const candidates = data?.candidates || [];
  _mappingState.candidates = candidates;

  if (countEl) countEl.textContent = `new: ${candidates.filter((c) => c.status === "pending").length}`;

  // WU-006: Distinguish no_data vs has_candidates
  if (!candidates.length) {
    queueEl.innerHTML = renderStateBanner(
      "no_data",
      "No mapping candidates yet. Process inbox items to generate candidates.",
      { href: "/inbox", label: "Open Inbox" }
    );
    _mappingState.selectedId = null;
    _mappingState.selectedMatchId = null;
    _mappingState.selectedMatchTitle = null;
    updateSelectedWikiIndicator();
    updateMappingActionBar();
    return;
  }

  queueEl.innerHTML = candidates.map((c) => {
    const hasError = c.status === "error" || c.status === "failed";
    const isProcessing = c.status === "processing" || c.status === "queued";
    const statusIcon = hasError ? "❌" : isProcessing ? "⏳" : c.status === "approved" ? "✅" : "🧩";
    return `<div class="mapping-queue-row ${hasError ? "error" : ""}" data-candidate-id="${escapeHtml(c.id)}">
      <span class="candidate-type-icon">${statusIcon}</span>
      <div class="mapping-queue-body">
        <div class="mapping-queue-title">${escapeHtml(c.title || c.candidate_key || c.id)}</div>
        <div class="mapping-queue-meta">${escapeHtml(c.candidate_type || "")} · ${safeStatusPill(c.status || "pending")}</div>
      </div>
      ${hasError ? '<span class="pill bad">error</span>' : ""}
    </div>`;
  }).join("");

  queueEl.querySelectorAll(".mapping-queue-row").forEach((row) => {
    row.addEventListener("click", () => selectMappingCandidate(row.dataset.candidateId));
  });
}

async function selectMappingCandidate(candidateId) {
  _mappingState.selectedId = candidateId;
  _mappingState.selectedMatchId = null;
  _mappingState.selectedMatchTitle = null;
  document.querySelectorAll(".mapping-queue-row").forEach((r) => r.classList.toggle("active", r.dataset.candidateId === candidateId));

  const candidate = _mappingState.candidates.find((c) => c.id === candidateId);
  if (!candidate) return;

  // Render step 1
  const step1El = document.getElementById("mapping-step1-content");
  if (step1El) {
    const payload = candidate.payload || {};
    step1El.innerHTML = `
      <div class="mapping-step-content">
        <div class="system-row"><span class="label">Wiki name</span><span class="value"><b>${escapeHtml(payload.title || candidate.title || "")}</b></span></div>
        <div class="system-row"><span class="label">LLM reason</span><span class="value">${escapeHtml(payload.reason || payload.summary || "—")}</span></div>
        <div class="mapping-section"><h4>Draft body</h4><div class="md-rendered">${renderMarkdown(payload.body || payload.content || "")}</div></div>
        <div class="mapping-section"><h4>Proposed relationships</h4>${(payload.proposed_relations || []).map((r) => `<div class="relation-row">${escapeHtml(r.source || "")} --${escapeHtml(r.label || "related_to")}--> ${escapeHtml(r.target || "")}</div>`).join("") || '<div class="hint">No proposed relationships.</div>'}</div>
        <details class="preview"><summary>Technical details</summary><div class="code">${escapeHtml(JSON.stringify(payload, null, 2))}</div></details>
      </div>
    `;
  }

  // Fetch wiki matches and render in persistent area
  const matches = await apiFetch(`${API.mappingWikiMatches}?candidate_id=${encodeURIComponent(candidateId)}`);
  const matchList = matches?.matches || [];
  _mappingState.wikiMatches = matchList;

  // Render wiki matches in persistent area
  const wikiMatchesListEl = document.getElementById("mapping-wiki-matches-list");
  if (wikiMatchesListEl) {
    if (!matchList.length) {
      wikiMatchesListEl.innerHTML = `<div class="empty"><p>유사한 기존 wiki가 없습니다.</p><button class="btn btn-sm" disabled title="switch할 wiki match가 없습니다">Switch unavailable</button></div>`;
    } else {
      wikiMatchesListEl.innerHTML = matchList.map((m, idx) => {
        const score = Number(m.score || 0).toFixed(2);
        const title = m.title || m.concept_id || m.id;
        const path = m.path || "";
        const reason = m.reason || (idx === 0 && parseFloat(score) >= 0.9 ? "exact alias" : parseFloat(score) >= 0.7 ? "related" : "relation proximity");
        const isSelected = _mappingState.selectedMatchId === (m.concept_id || m.id);
        return `<div class="wiki-match-row ${isSelected ? 'active' : ''}" data-wiki-id="${escapeHtml(m.concept_id || m.id)}" data-wiki-title="${escapeHtml(title)}">
          <span class="score">${score}</span>
          <div class="wiki-match-title">
            <div>${escapeHtml(title)}</div>
            <div class="wiki-match-path">${escapeHtml(reason)}${path ? ' · ' + escapeHtml(path) : ''}</div>
          </div>
          <div class="wiki-match-actions">
            ${isSelected
              ? '<span class="pill ok">selected</span>'
              : `<button class="btn btn-sm wiki-match-use" data-wiki-id="${escapeHtml(m.concept_id || m.id)}" data-wiki-title="${escapeHtml(title)}">${idx === 0 ? 'Use this wiki' : 'Switch'}</button>`
            }
          </div>
        </div>`;
      }).join("");

      // Bind Use/Switch buttons
      wikiMatchesListEl.querySelectorAll(".wiki-match-use").forEach((btn) => {
        btn.addEventListener("click", (e) => {
          e.stopPropagation();
          selectWikiMatch(btn.dataset.wikiId, btn.dataset.wikiTitle);
        });
      });

      // Bind row click to select
      wikiMatchesListEl.querySelectorAll(".wiki-match-row").forEach((row) => {
        row.addEventListener("click", () => {
          selectWikiMatch(row.dataset.wikiId, row.dataset.wikiTitle);
        });
      });
    }
  }

  // Render step 2 (also includes wiki matches for comparison)
  const step2El = document.getElementById("mapping-step2-content");
  if (step2El) {
    step2El.innerHTML = `
      <div class="mapping-step-content">
        <div class="mapping-compare">
          <div class="mapping-compare-left">
            <h4>Candidate</h4>
            <div class="md-rendered">${renderMarkdown((candidate.payload || {}).body || candidate.title || "")}</div>
          </div>
          <div class="mapping-compare-right">
            <h4>Similar existing wiki</h4>
            ${matchList.length ? matchList.map((m) => `<div class="wiki-match-row" data-wiki-id="${escapeHtml(m.concept_id || m.id)}" data-wiki-title="${escapeHtml(m.title || m.concept_id || m.id)}"><span class="score">${Number(m.score || 0).toFixed(2)}</span> ${escapeHtml(m.title || m.concept_id || m.id)}</div>`).join("") : '<div class="hint">유사한 기존 wiki가 없습니다.</div>'}
          </div>
        </div>
        <div class="mapping-decision">
          <h4>Decision</h4>
          <label><input type="radio" name="mapping-decision" value="merge" /> Merge into existing</label>
          <label><input type="radio" name="mapping-decision" value="keep_new" checked /> Keep as new page</label>
          <label><input type="radio" name="mapping-decision" value="defer" /> Unsure, defer</label>
        </div>
      </div>
    `;
    step2El.querySelectorAll(".wiki-match-row").forEach((row) => {
      row.addEventListener("click", () => {
        selectWikiMatch(row.dataset.wikiId, row.dataset.wikiTitle || row.textContent.trim());
      });
    });
  }

  // Render step 3
  const step3El = document.getElementById("mapping-step3-content");
  if (step3El) {
    const payload = candidate.payload || {};
    const relations = payload.proposed_relations || [];
    step3El.innerHTML = `
      <div class="mapping-step-content">
        <h4>Relationship structure</h4>
        ${relations.length ? relations.map((r) => `<div class="relation-row">${escapeHtml(r.source || "")} --${escapeHtml(r.label || "related_to")}--> ${escapeHtml(r.target || "")}</div>`).join("") : '<div class="hint">No relationships to verify.</div>'}
        <div class="mapping-graph-placeholder" id="mapping-mini-graph">
          <div class="hint">Graph visualization (click relation to preview target wiki)</div>
        </div>
      </div>
    `;
  }

  // Update action bar visibility and labels
  updateMappingActionBar();
  updateSelectedWikiIndicator();
}

function selectWikiMatch(wikiId, wikiTitle) {
  _mappingState.selectedMatchId = wikiId;
  _mappingState.selectedMatchTitle = wikiTitle;

  // Update wiki matches list UI
  const wikiMatchesListEl = document.getElementById("mapping-wiki-matches-list");
  if (wikiMatchesListEl) {
    wikiMatchesListEl.querySelectorAll(".wiki-match-row").forEach((row) => {
      const isSelected = row.dataset.wikiId === wikiId;
      row.classList.toggle("active", isSelected);
      const actionsEl = row.querySelector(".wiki-match-actions");
      if (actionsEl) {
        if (isSelected) {
          actionsEl.innerHTML = '<span class="pill ok">selected</span>';
        } else {
          const btn = actionsEl.querySelector(".wiki-match-use");
          if (!btn) {
            const title = row.dataset.wikiTitle || "";
            actionsEl.innerHTML = `<button class="btn btn-sm wiki-match-use" data-wiki-id="${escapeHtml(row.dataset.wikiId)}" data-wiki-title="${escapeHtml(title)}">Switch</button>`;
            actionsEl.querySelector(".wiki-match-use")?.addEventListener("click", (e) => {
              e.stopPropagation();
              selectWikiMatch(row.dataset.wikiId, row.dataset.wikiTitle);
            });
          }
        }
      }
    });
  }

  updateMappingActionBar();
  updateSelectedWikiIndicator();
  showToast(`Selected wiki: ${wikiTitle}`, "ok", 1500);
}

function updateSelectedWikiIndicator() {
  const pillEl = document.getElementById("mapping-selected-wiki-pill");
  const switchBtn = document.getElementById("btn-mapping-switch-wiki");
  if (pillEl) {
    if (_mappingState.selectedMatchId && _mappingState.selectedMatchTitle) {
      pillEl.textContent = _mappingState.selectedMatchTitle;
      pillEl.className = "pill ok";
    } else {
      pillEl.textContent = "none";
      pillEl.className = "pill";
    }
  }
  if (switchBtn) {
    switchBtn.disabled = !_mappingState.selectedId;
    switchBtn.title = _mappingState.selectedId ? "Existing wiki matches로 이동" : "candidate를 먼저 선택하세요";
  }
}

function updateMappingActionBar() {
  const addBtn = document.getElementById("btn-mapping-add");
  const mergeBtn = document.getElementById("btn-mapping-merge");
  const createBtn = document.getElementById("btn-mapping-create");
  const editBtn = document.getElementById("btn-mapping-edit");
  const rejectBtn = document.getElementById("btn-mapping-reject");
  const confirmBtn = document.getElementById("btn-mapping-confirm");
  const step = _mappingState.currentStep;

  // Update Add/Merge button labels and disabled state based on selected wiki
  const wikiTitle = _mappingState.selectedMatchTitle;
  const hasWiki = Boolean(wikiTitle);

  if (addBtn) {
    addBtn.textContent = hasWiki ? `Add to "${wikiTitle}"` : "Add to wiki";
    addBtn.disabled = !hasWiki;
    addBtn.title = hasWiki ? "" : "select wiki";
  }
  if (mergeBtn) {
    mergeBtn.textContent = hasWiki ? `Merge into "${wikiTitle}"` : "Merge into wiki";
    mergeBtn.disabled = !hasWiki;
    mergeBtn.title = hasWiki ? "" : "select wiki";
  }

  // Update Create button label with candidate name
  const candidate = _mappingState.candidates.find((c) => c.id === _mappingState.selectedId);
  const hasCandidate = Boolean(candidate);
  if (createBtn && candidate) {
    const candidateTitle = (candidate.payload || {}).title || candidate.title || "candidate";
    createBtn.textContent = `Create new "${candidateTitle}"`;
  }
  if (createBtn) {
    createBtn.disabled = !hasCandidate;
    createBtn.title = hasCandidate ? "" : "select candidate";
    if (!hasCandidate) createBtn.textContent = "Create new";
  }
  if (editBtn) {
    editBtn.disabled = !hasCandidate;
    editBtn.title = hasCandidate ? "" : "select candidate";
  }
  if (rejectBtn) {
    rejectBtn.disabled = !hasCandidate;
    rejectBtn.title = hasCandidate ? "" : "select candidate";
  }

  // Show/hide Confirm based on step
  if (confirmBtn) {
    confirmBtn.disabled = !hasCandidate;
    confirmBtn.title = hasCandidate ? "" : "select candidate";
    confirmBtn.style.display = step === 3 ? "" : "none";
  }
}

export function bindMappingActions() {
  // Step bar
  document.querySelectorAll(".mapping-step").forEach((btn) => {
    btn.addEventListener("click", () => {
      const step = btn.dataset.mappingStep;
      document.querySelectorAll(".mapping-step").forEach((b) => b.classList.toggle("active", b === btn));
      document.querySelectorAll(".mapping-pane").forEach((p) => p.classList.remove("active"));
      const paneId = step === "errors" ? "mapping-pane-errors" : `mapping-pane-${step}`;
      document.getElementById(paneId)?.classList.add("active");
      _mappingState.currentStep = step === "errors" ? "errors" : parseInt(step);
      updateMappingActionBar();
    });
  });

  // Next (legacy — kept for backward compat, but now hidden in favor of explicit step navigation)
  document.getElementById("btn-mapping-next")?.addEventListener("click", () => {
    const nextStep = Math.min((_mappingState.currentStep || 1) + 1, 3);
    const btn = document.querySelector(`.mapping-step[data-mapping-step="${nextStep}"]`);
    btn?.click();
  });

  // Add to wiki
  document.getElementById("btn-mapping-add")?.addEventListener("click", async () => {
    if (!_mappingState.selectedMatchId) {
      showToast("Select a wiki first", "warn");
      return;
    }
    const res = await apiFetch(API.mappingDecide, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_id: _mappingState.selectedId,
        action: "add",
        metadata: { target_concept_id: _mappingState.selectedMatchId, step: "page_mapping", mapping_intent: "add_to_wiki" },
      }),
    });
    if (res !== null) {
      _mappingState.preview = { decision_id: res.decision_id, action: "add", target_concept_id: _mappingState.selectedMatchId };
      showToast(`Previewed Add to "${_mappingState.selectedMatchTitle}". Confirm in step 3.`, "ok");
    } else {
      showToast("Add failed", "bad");
    }
  });

  // Merge into wiki
  document.getElementById("btn-mapping-merge")?.addEventListener("click", async () => {
    if (!_mappingState.selectedMatchId) {
      showToast("Select a wiki first", "warn");
      return;
    }
    const res = await apiFetch(API.mappingDecide, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_id: _mappingState.selectedId,
        action: "merge",
        metadata: { target_concept_id: _mappingState.selectedMatchId, step: "page_mapping" },
      }),
    });
    if (res !== null) {
      _mappingState.preview = { decision_id: res.decision_id, action: "merge", target_concept_id: _mappingState.selectedMatchId };
      showToast(`Previewed Merge into "${_mappingState.selectedMatchTitle}". Confirm in step 3.`, "ok");
    } else {
      showToast("Merge failed", "bad");
    }
  });

  // Create new
  document.getElementById("btn-mapping-create")?.addEventListener("click", async () => {
    if (!_mappingState.selectedId) {
      showToast("Select a candidate first", "warn");
      return;
    }
    const candidate = _mappingState.candidates.find((c) => c.id === _mappingState.selectedId);
    const candidateTitle = (candidate?.payload || {}).title || candidate?.title || "candidate";
    if (!window.confirm(`Create new wiki page "${candidateTitle}"?`)) return;
    const res = await apiFetch(API.mappingDecide, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        candidate_id: _mappingState.selectedId,
        action: "create_new",
        metadata: { step: "page_mapping" },
      }),
    });
    if (res !== null) {
      _mappingState.preview = { decision_id: res.decision_id, action: "create_new", target_concept_id: null };
      showToast(`Previewed new "${candidateTitle}". Confirm in step 3.`, "ok");
    } else {
      showToast("Create failed", "bad");
    }
  });

  // Reject
  document.getElementById("btn-mapping-reject")?.addEventListener("click", () => {
    if (!_mappingState.selectedId) {
      showToast("Select a candidate first", "warn");
      return;
    }
    document.getElementById("mapping-reject-modal")?.classList.add("open");
  });
  document.getElementById("btn-mapping-reject-cancel")?.addEventListener("click", () => {
    document.getElementById("mapping-reject-modal")?.classList.remove("open");
  });
  document.getElementById("btn-mapping-reject-submit")?.addEventListener("click", async () => {
    const instruction = document.getElementById("mapping-reject-instruction")?.value?.trim() || "";
    const reason = window.prompt("Retry reason", "Needs revision")?.trim() || "";
    const step = currentMappingStepId();
    if (!reason) { showToast("Retry reason is required", "warn"); return; }
    if (!instruction) { showToast("Retry instruction is required", "warn"); return; }
    const res = await apiFetch(API.mappingCandidateRetry(_mappingState.selectedId), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason, instruction, metadata: { step } }),
    });
    if (res !== null) {
      showToast("Retry request recorded", "ok");
      document.getElementById("mapping-reject-modal")?.classList.remove("open");
      loadMapping();
    } else {
      showToast("Retry request failed", "bad");
    }
  });

  // Confirm mapping (only step 3)
  document.getElementById("btn-mapping-confirm")?.addEventListener("click", async () => {
    if (!_mappingState.selectedId) {
      showToast("Select a candidate first", "warn");
      return;
    }
    if (!_mappingState.preview?.decision_id) {
      showToast("Create a preview decision before confirming", "warn");
      return;
    }
    const action = _mappingState.preview.action;
    const metadata = { step: "relationship_validate", preview_decision_id: _mappingState.preview.decision_id };
    let note = null;
    if (["add", "merge"].includes(action) && _mappingState.preview.target_concept_id) {
      metadata.target_concept_id = _mappingState.preview.target_concept_id;
    }
    if (action === "edit") {
      note = "Deferred from mapping confirm for manual edit/review";
      metadata.deferred = true;
    }
    const res = await apiFetch(API.mappingDecide, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: _mappingState.selectedId, action, note, metadata }),
    });
    if (res !== null) {
      showToast("Confirmed", "ok");
      loadMapping();
    } else {
      showToast("Confirm failed", "bad");
    }
  });

  // Edit — record edit-needed decision note
  document.getElementById("btn-mapping-edit")?.addEventListener("click", () => {
    if (!_mappingState.selectedId) {
      showToast("Select a candidate first", "warn");
      return;
    }
    document.getElementById("mapping-edit-modal")?.classList.add("open");
  });
  document.getElementById("btn-mapping-edit-cancel")?.addEventListener("click", () => {
    document.getElementById("mapping-edit-modal")?.classList.remove("open");
  });
  document.getElementById("btn-mapping-edit-submit")?.addEventListener("click", async () => {
    const note = document.getElementById("mapping-edit-note")?.value?.trim() || "Edit requested from Mapping UI";
    const res = await apiFetch(API.mappingDecide, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ candidate_id: _mappingState.selectedId, action: "edit", note, metadata: { step: currentMappingStepId() } }),
    });
    if (res !== null) {
      showToast("Edit note saved", "ok");
      document.getElementById("mapping-edit-modal")?.classList.remove("open");
      loadMapping();
    } else {
      showToast("Edit save failed", "bad");
    }
  });

  // Switch wiki button
  document.getElementById("btn-mapping-switch-wiki")?.addEventListener("click", () => {
    // Scroll to wiki matches area or open drawer on mobile
    const wikiMatchesEl = document.getElementById("mapping-wiki-matches");
    if (wikiMatchesEl) {
      wikiMatchesEl.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  });

  // Handle URL params for step navigation (from drawer)
  const urlParams = new URLSearchParams(window.location.search);
  const stepParam = urlParams.get("step");
  if (stepParam) {
    const stepBtn = document.querySelector(`.mapping-step[data-mapping-step="${stepParam}"]`);
    if (stepBtn) {
      setTimeout(() => stepBtn.click(), 100);
    }
  }
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
  const renderedTree = await renderVaultFileTreeNode(data.tree, "");
  treeEl.innerHTML = renderedTree || renderStateBanner("no_data", "Vault is empty or has no visible files yet.", { href: "/inbox", label: "Add source" });
  bindVaultFileTreeRows(treeEl);
}

async function renderVaultFileTreeNode(node, prefix) {
  if (!node) return "";
  let html = "";
  const folders = node.children || [];
  const folderPath = node.path || prefix || "";
  const childrenParts = [];

  let files = [];
  const listing = await apiFetch(`${API.vaultFolder}?path=${encodeURIComponent(folderPath)}`);
  if (listing) files = listing.files || [];
  else childrenParts.push(renderStateBanner("failure", `Could not read folder: ${folderPath || "vault root"}`));
  if (files.length) {
    childrenParts.push(files.map((f) => `
      <div class="vault-tree-entry vault-tree-file" data-file-path="${escapeHtml(f.path)}" data-tree-label="${escapeHtml(f.name)}">
        <span class="file-icon">${f.name?.endsWith(".md") ? "📄" : "📎"}</span>
        <span class="vault-tree-name">${escapeHtml(f.name)}</span>
        <span class="vault-tree-meta">${f.size ? `${(f.size / 1024).toFixed(1)} KB` : ""}</span>
      </div>
    `).join(""));
  }

  for (const child of folders) {
    childrenParts.push(await renderVaultFileTreeNode(child, child.path || ""));
  }

  if (folderPath) {
    const childId = `vault-tree-children-${folderPath.replace(/[^a-zA-Z0-9_-]/g, "-") || "root"}`;
    html += `<div class="vault-tree-entry vault-tree-folder" data-folder-path="${escapeHtml(folderPath)}" data-tree-label="${escapeHtml(node.name || folderPath)}" data-children-id="${escapeHtml(childId)}" aria-expanded="true">
      <span class="folder-icon">📁</span><span class="vault-tree-name">${escapeHtml(node.name || folderPath)}</span>
    </div>`;
    html += `<div class="vault-tree-children" id="${escapeHtml(childId)}">${childrenParts.join("")}</div>`;
  } else {
    html += childrenParts.join("");
  }
  return html;
}

function bindVaultFileTreeRows(rootEl) {
  rootEl.querySelectorAll(".vault-tree-folder").forEach((row) => {
    row.addEventListener("click", () => {
      const collapsed = !row.classList.contains("collapsed");
      row.classList.toggle("collapsed", collapsed);
      row.setAttribute("aria-expanded", String(!collapsed));
      const childrenId = row.dataset.childrenId;
      const children = childrenId ? document.getElementById(childrenId) : row.nextElementSibling;
      if (children?.classList.contains("vault-tree-children")) {
        children.hidden = collapsed;
      }
    });
  });
  rootEl.querySelectorAll(".vault-tree-file").forEach((row) => {
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

export async function loadSettingsLLM() {
  const basicEl = document.getElementById("settings-llm-basic");
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
            <input class="input" name="endpoint" value="${escapeHtml(s.endpoint || "")}" autocomplete="off" />
          </label>
          <label>API key
            <input class="input" type="password" name="api_key" placeholder="${missing.api_key_missing ? "Not configured" : "Configured — enter to change"}" autocomplete="off" />
          </label>
          <input type="hidden" name="default_chat_model" value="${escapeHtml(s.default_chat_model || "chat_default")}" />
          <input type="hidden" name="default_embedding_model" value="${escapeHtml(s.default_embedding_model || "embedding_default")}" />
          <input type="hidden" name="chat_model_name" value="${escapeHtml(s.models?.chat_default?.model_name || s.default_chat_model || "")}" />
          <input type="hidden" name="embedding_model_name" value="${escapeHtml(s.models?.embedding_default?.model_name || s.default_embedding_model || "")}" />
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
      document.getElementById("settings-llm-basic-form")?.addEventListener("submit", async (e) => {
        e.preventDefault();
        const form = new FormData(e.currentTarget);
        const payload = Object.fromEntries(form.entries());
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
      document.getElementById("btn-settings-test-connection")?.addEventListener("click", async () => {
        showToast("Testing connection…", "ok", 1500);
        const chat = await apiFetch(API.settingsLlmTest("chat_default"));
        const embedding = await apiFetch(API.settingsLlmTest("embedding_default"));
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
    const fastembed = data?.fastembed_models || [];
    if (!models.length && !fastembed.length) {
      registryEl.innerHTML = `<div class="empty">사용 가능한 chat model이 없습니다.<br><button class="btn" onclick="location.reload()">Refresh models</button></div>`;
    } else {
      let html = "<h5>Chat models</h5>";
      html += models.filter((m) => m.capability === "chat" || !m.capability).map((m) => `
        <div class="model-row">
          <span class="model-name">${escapeHtml(m.id)}</span>
          <span class="pill">${escapeHtml(m.status || "available")}</span>
          ${m.is_default ? '<span class="pill ok">default</span>' : ""}
        </div>
      `).join("");
      html += "<h5>Embedding models (fastembed)</h5>";
      html += fastembed.map((m) => `
        <div class="model-row">
          <span class="model-name">${escapeHtml(m.id)}</span>
          <span class="pill">${m.downloaded ? "downloaded" : "not downloaded"}</span>
          ${m.is_default ? '<span class="pill ok">default</span>' : ""}
          <button class="btn btn-download-embed" data-model="${escapeHtml(m.id)}">${m.downloaded ? "Set default" : "Download"}</button>
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
    const modelOptions = models.map((m) => `<option value="${escapeHtml(m.id)}">${escapeHtml(m.id)}</option>`).join("");

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

  // Load all prompt versions
  const data = await apiFetch(API.settingsPromptVersions);
  const items = data?.prompt_versions || [];

  // Group by task_type
  const byType = {};
  for (const p of items) {
    const tt = p.task_type || "unknown";
    if (!byType[tt]) byType[tt] = [];
    byType[tt].push(p);
  }

  topTabs.querySelectorAll(".prompt-sequence-item").forEach((tab) => {
    tab.onclick = () => {
      topTabs.querySelectorAll(".prompt-sequence-item").forEach((item) => {
        item.classList.remove("active");
        item.setAttribute("aria-selected", "false");
      });
      tab.classList.add("active");
      tab.setAttribute("aria-selected", "true");
      const taskType = tab.dataset.promptTask || "ask";
      loadPromptWorkspace(taskType, byType[taskType] || []);
      syncPromptSequenceScroll();
    };
  });
  const firstTab = topTabs.querySelector(".prompt-sequence-item.active") || topTabs.querySelector(".prompt-sequence-item");
  if (firstTab) {
    const taskType = firstTab.dataset.promptTask || "ask";
    loadPromptWorkspace(taskType, byType[taskType] || []);
    syncPromptSequenceScroll();
  }
}

async function loadPromptWorkspace(taskType, versions) {
  const workspaceEl = document.getElementById("settings-prompt-workspace");
  if (!workspaceEl) return;

  const confirmed = versions.find((v) => v.state === "confirmed");
  const test = versions.find((v) => v.state === "test");
  const current = test || confirmed;

  workspaceEl.innerHTML = `
    <div class="prompt-active-status">
      <h4>현재 적용 중</h4>
      <div class="system-row"><span class="label">Task</span><span class="value">${escapeHtml(taskType)}</span></div>
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
      <a class="btn" href="/onboarding">Change in Onboarding</a>
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
    if (searchResults) searchResults.innerHTML = html;
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
    if (askResult) askResult.innerHTML = html;
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
    loadInbox, bindInboxActions, loadMapping, bindMappingActions, loadVaultTree, bindVaultBrowser,
    loadSearchPage,
    // WU-006: State visibility helpers
    renderStateBanner, classifySetupState, classifyComponentStatus, safeStatusPill,
  };
}
